"""Cross-video study aggregation.

Collects completed VideoReports from multiple sessions and produces
a StudyReport with segment-level fingerprints, stop-risk cohorts,
and LLM-synthesized cross-session insights.
"""

import json
from collections import Counter
from dataclasses import dataclass, field

import google.genai as genai

from gamesight.config import normalize_segment_label
from gamesight.gemini.generate import generate_structured
from gamesight.prompts.study import STUDY_SYNTHESIS_PROMPT
from gamesight.schemas.report import VideoReport
from gamesight.schemas.study import (
    CrossVideoSynthesis,
    SegmentFingerprint,
    StopRiskCohort,
    StudyReport,
)


@dataclass
class _SegmentAccumulator:
    sessions: set[str] = field(default_factory=set)
    friction_sessions: set[str] = field(default_factory=set)
    delight_sessions: set[str] = field(default_factory=set)
    friction_severities: list[float] = field(default_factory=list)
    friction_sources: list[str] = field(default_factory=list)
    delight_drivers: list[str] = field(default_factory=list)
    sentiment_scores: list[int] = field(default_factory=list)
    retry_attempts: list[int] = field(default_factory=list)
    quit_signals: int = 0
    first_attempt_failures: int = 0
    retry_sessions: int = 0
    quotes: list[str] = field(default_factory=list)


def _report_has_agent_coverage(report: VideoReport, agent_name: str) -> bool:
    if report.agent_coverage:
        return any(getattr(coverage, agent_name) for coverage in report.agent_coverage)
    fallback_map = {
        "sentiment": report.sentiment_moments,
        "retry": report.retry_moments,
        "verbal": report.verbal_moments,
    }
    fallback_moments = fallback_map.get(agent_name)
    return bool(fallback_moments)


def _build_segment_fingerprints(reports: list[VideoReport]) -> list[SegmentFingerprint]:
    """Group all canonical moments by segment_label across all reports."""
    seg_data: dict[str, _SegmentAccumulator] = {}

    def _get(label: str) -> _SegmentAccumulator:
        if label not in seg_data:
            seg_data[label] = _SegmentAccumulator()
        return seg_data[label]

    for report in reports:
        session_id = report.video_id
        has_sentiment = _report_has_agent_coverage(report, "sentiment")
        has_retry = _report_has_agent_coverage(report, "retry")
        has_verbal = _report_has_agent_coverage(report, "verbal")
        for segment_label in report.segments_encountered:
            label = normalize_segment_label(segment_label)
            if label:
                _get(label).sessions.add(session_id)
        for m in report.friction_moments:
            label = normalize_segment_label(m.segment_label)
            if label:
                d = _get(label)
                d.sessions.add(session_id)
                d.friction_sessions.add(session_id)
                d.friction_severities.append(m.severity_numeric)
                d.friction_sources.append(m.source_label)
        for m in report.delight_moments:
            label = normalize_segment_label(m.segment_label)
            if label:
                d = _get(label)
                d.sessions.add(session_id)
                d.delight_sessions.add(session_id)
                d.delight_drivers.append(m.source_label)
        if has_sentiment:
            for m in report.sentiment_moments:
                label = normalize_segment_label(m.segment_label)
                if label is None or m.sentiment_raw_score is None:
                    continue
                d = _get(label)
                d.sessions.add(session_id)
                d.sentiment_scores.append(m.sentiment_raw_score)
        if has_retry:
            for m in report.retry_moments:
                label = normalize_segment_label(m.segment_label or m.source_label)
                if label:
                    d = _get(label)
                    d.sessions.add(session_id)
                    d.retry_sessions += 1
                    if m.retry_total_attempts is not None:
                        d.retry_attempts.append(m.retry_total_attempts)
                        if m.retry_total_attempts > 1:
                            d.first_attempt_failures += 1
                    if m.retry_quit_signal:
                        d.quit_signals += 1
        if has_verbal:
            for m in report.verbal_moments:
                label = normalize_segment_label(m.segment_label)
                if label and m.verbal_quote:
                    acc = _get(label)
                    acc.sessions.add(session_id)
                    acc.quotes.append(m.verbal_quote)

    fingerprints: list[SegmentFingerprint] = []
    for label, d in seg_data.items():
        sessions_enc = len(d.sessions)
        if sessions_enc < 1:
            continue
        friction_count = len(d.friction_sessions)
        delight_count = len(d.delight_sessions)
        friction_sources = Counter(d.friction_sources)
        delight_drivers = Counter(d.delight_drivers)

        fingerprints.append(
            SegmentFingerprint(
                segment_label=label,
                sessions_encountered=sessions_enc,
                sessions_with_friction=friction_count,
                friction_rate=round(friction_count / sessions_enc, 3) if sessions_enc else 0.0,
                avg_friction_severity=round(sum(d.friction_severities) / len(d.friction_severities), 2)
                if d.friction_severities
                else 0.0,
                sessions_with_delight=delight_count,
                delight_rate=round(delight_count / sessions_enc, 3) if sessions_enc else 0.0,
                dominant_friction_source=friction_sources.most_common(1)[0][0] if friction_sources else None,
                dominant_delight_driver=delight_drivers.most_common(1)[0][0] if delight_drivers else None,
                avg_sentiment=round(sum(d.sentiment_scores) / len(d.sentiment_scores), 2)
                if d.sentiment_scores
                else None,
                positive_sentiment_rate=round(sum(1 for s in d.sentiment_scores if s > 0) / len(d.sentiment_scores), 3)
                if d.sentiment_scores
                else None,
                first_attempt_failure_rate=round(d.first_attempt_failures / d.retry_sessions, 3)
                if d.retry_sessions
                else None,
                avg_retry_attempts=round(sum(d.retry_attempts) / len(d.retry_attempts), 2)
                if d.retry_attempts
                else None,
                quit_signal_rate=round(d.quit_signals / d.retry_sessions, 3) if d.retry_sessions else None,
                representative_quotes=d.quotes[:5],
            )
        )

    fingerprints.sort(key=lambda f: f.sessions_encountered, reverse=True)
    return fingerprints


def _build_stop_risk_cohorts(
    reports: list[VideoReport], fingerprints: list[SegmentFingerprint]
) -> list[StopRiskCohort]:
    """Identify segments with high stop-risk patterns."""
    total = len(reports)
    cohorts: list[StopRiskCohort] = []
    for fp in fingerprints:
        if fp.friction_rate >= 0.3 and fp.sessions_encountered >= 2:
            cohorts.append(
                StopRiskCohort(
                    trigger_segment=fp.segment_label,
                    sessions_affected=fp.sessions_with_friction,
                    total_sessions=total,
                    percentage=round(fp.sessions_with_friction / total * 100, 1) if total else 0.0,
                    common_pattern=f"Friction rate {fp.friction_rate:.0%}, avg severity {fp.avg_friction_severity:.1f}/10"
                    + (f", {fp.quit_signal_rate:.0%} quit signal rate" if fp.quit_signal_rate else ""),
                    representative_quotes=fp.representative_quotes,
                )
            )
    cohorts.sort(key=lambda c: c.percentage, reverse=True)
    return cohorts[:5]


async def build_study_report(
    client: genai.Client,
    reports: list[VideoReport],
    game_key: str,
) -> StudyReport:
    """Aggregate multiple VideoReports into a cross-session StudyReport."""
    game_title = reports[0].game_title if reports else game_key
    fingerprints = _build_segment_fingerprints(reports)
    cohorts = _build_stop_risk_cohorts(reports, fingerprints)
    total_duration = sum(r.duration_seconds for r in reports) / 60.0

    stats_payload = {
        "game_key": game_key,
        "game_title": game_title,
        "total_sessions": len(reports),
        "total_duration_minutes": round(total_duration, 1),
        "segment_fingerprints": [fp.model_dump(mode="json") for fp in fingerprints],
        "stop_risk_cohorts": [c.model_dump() for c in cohorts],
        "full_session_reports": [report.model_dump(mode="json") for report in reports],
    }

    prompt = STUDY_SYNTHESIS_PROMPT.format(
        session_count=len(reports),
        game_title=game_title,
        study_json=json.dumps(stats_payload, indent=2),
    )
    synthesis = await generate_structured(
        client,
        contents=prompt,
        response_schema=CrossVideoSynthesis,
        thinking_level="medium",
    )

    return StudyReport(
        game_key=game_key,
        game_title=game_title,
        total_sessions=len(reports),
        total_duration_minutes=round(total_duration, 1),
        segment_fingerprints=fingerprints,
        stop_risk_cohorts=cohorts,
        insights=synthesis.insights,
        top_priorities=synthesis.top_priorities,
        executive_summary=synthesis.executive_summary,
    )


__all__ = ["build_study_report"]
