from collections import Counter
from typing import Final

from gamesight.schemas.report import ChunkAgentCoverage, DeduplicatedAnalyses, VideoReport
from gamesight.schemas.video import ChunkAnalysisBundle, VideoInfo, VideoTimeline

STOP_RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
FRICTION_ORDER = {"minor": 0, "moderate": 1, "major": 2, "severe": 3}
ENGAGEMENT_ORDER = {"light": 0, "clear": 1, "strong": 2, "signature": 3}
FRICTION_SOURCE_LABELS: Final[dict[str, str]] = {
    "difficulty_spike": "difficulty spikes",
    "unclear_objective": "unclear objectives",
    "controls": "control issues",
    "camera": "camera problems",
    "bug": "technical bugs",
    "repetition": "repetitive gameplay",
    "unfair_mechanic": "perceived unfair mechanics",
    "ui_confusion": "UI confusion",
    "other": "miscellaneous friction sources",
}


def _order_value(ordering: dict[str, int], value: str) -> int:
    return ordering.get(value, -1)


def _top_items(counter: Counter[str], *, limit: int = 5) -> list[str]:
    return [item for item, _ in counter.most_common(limit)]


def _build_recommendations(
    *,
    stop_risk_drivers: list[str],
    clarity_fixes: list[str],
    praised_features: list[str],
    bug_count: int,
) -> list[str]:
    recommendations: list[str] = []
    for driver in stop_risk_drivers[:2]:
        label = FRICTION_SOURCE_LABELS.get(driver, driver.replace("_", " "))
        recommendations.append(f"Reduce {label} in the highest-risk gameplay beats.")
    for clarity_fix in clarity_fixes[:2]:
        fix_text = clarity_fix.rstrip(".")
        recommendations.append(f"Prioritize this communication fix: {fix_text}.")
    if bug_count > 0:
        recommendations.append(f"Triage the {bug_count} visible technical issues surfaced during the session.")
    if praised_features:
        recommendations.append(f"Protect and expand the strongest positives: {', '.join(praised_features[:3])}.")
    if not recommendations:
        recommendations.append("The session was relatively stable; preserve the current onboarding and pacing.")
    return recommendations


def build_video_report(
    *,
    video: VideoInfo,
    timeline: VideoTimeline,
    analyses: list[ChunkAnalysisBundle],
    deduplicated: DeduplicatedAnalyses,
) -> VideoReport:
    stop_risk_counter: Counter[str] = Counter()
    praised_feature_counter: Counter[str] = Counter()
    clarity_fix_counter: Counter[str] = Counter()
    highest_stop_risk = "none"
    highest_friction = "minor"
    highest_engagement = "light"

    for analysis in analyses:
        highest_stop_risk = max(
            highest_stop_risk,
            analysis.friction.overall_stop_risk.value,
            key=lambda value: _order_value(STOP_RISK_ORDER, value),
        )
        highest_friction = max(
            highest_friction,
            analysis.friction.overall_severity.value,
            key=lambda value: _order_value(FRICTION_ORDER, value),
        )
        highest_engagement = max(
            highest_engagement,
            analysis.delight.overall_engagement.value,
            key=lambda value: _order_value(ENGAGEMENT_ORDER, value),
        )
    for moment in deduplicated.friction_moments:
        stop_risk_counter[moment.source_label] += 1
    for moment in deduplicated.delight_moments:
        praised_feature_counter[moment.source_label] += 1
    for moment in deduplicated.clarity_moments:
        clarity_fix_counter[moment.summary] += 1

    top_stop_risk_drivers = _top_items(stop_risk_counter)
    top_praised_features = _top_items(praised_feature_counter)
    top_clarity_fixes = _top_items(clarity_fix_counter)
    bug_count = len(deduplicated.quality_issues)
    recommendations = _build_recommendations(
        stop_risk_drivers=top_stop_risk_drivers,
        clarity_fixes=top_clarity_fixes,
        praised_features=top_praised_features,
        bug_count=bug_count,
    )

    avg_sentiment: float | None = None
    sentiment_by_segment: dict[str, float] = {}
    if deduplicated.sentiment_moments:
        signed_scores: list[int] = []
        seg_scores: dict[str, list[int]] = {}
        for m in deduplicated.sentiment_moments:
            if m.sentiment_raw_score is None:
                continue
            signed_scores.append(m.sentiment_raw_score)
            if m.segment_label:
                seg_scores.setdefault(m.segment_label, []).append(m.sentiment_raw_score)
        avg_sentiment = round(sum(signed_scores) / len(signed_scores), 2) if signed_scores else None
        sentiment_by_segment = {seg: round(sum(scores) / len(scores), 2) for seg, scores in seg_scores.items()}

    total_retry_sequences = len(deduplicated.retry_moments)
    first_attempt_failure_count = sum(
        1 for m in deduplicated.retry_moments if m.retry_total_attempts is not None and m.retry_total_attempts > 1
    )

    actionable_verbal = [m for m in deduplicated.verbal_moments if m.verbal_is_actionable]
    top_verbal = sorted(deduplicated.verbal_moments, key=lambda m: m.severity_numeric, reverse=True)
    notable_quotes = [m.verbal_quote for m in (actionable_verbal or top_verbal)[:5] if m.verbal_quote]
    segments_encountered = sorted({event.segment_label for event in timeline.events if event.segment_label})

    agent_coverage = [
        ChunkAgentCoverage(
            chunk_index=analysis.chunk_index,
            friction=True,
            clarity=True,
            delight=True,
            quality=True,
            sentiment=analysis.sentiment is not None,
            retry=analysis.retry is not None,
            verbal=analysis.verbal is not None,
        )
        for analysis in analyses
    ]

    return VideoReport(
        video_id=video.video_id,
        filename=video.filename,
        duration_seconds=video.duration_seconds,
        chunk_count=len(analyses),
        game_title=timeline.game_title,
        game_key=video.game_key,
        session_arc=timeline.session_arc,
        friction_moments=deduplicated.friction_moments,
        clarity_moments=deduplicated.clarity_moments,
        delight_moments=deduplicated.delight_moments,
        quality_issues=deduplicated.quality_issues,
        sentiment_moments=deduplicated.sentiment_moments,
        retry_moments=deduplicated.retry_moments,
        verbal_moments=deduplicated.verbal_moments,
        top_stop_risk_drivers=top_stop_risk_drivers,
        top_praised_features=top_praised_features,
        top_clarity_fixes=top_clarity_fixes,
        bug_count=bug_count,
        overall_friction=highest_friction,
        overall_engagement=highest_engagement,
        overall_stop_risk=highest_stop_risk,
        recommendations=recommendations,
        avg_sentiment=avg_sentiment,
        sentiment_by_segment=sentiment_by_segment,
        total_retry_sequences=total_retry_sequences,
        first_attempt_failure_count=first_attempt_failure_count,
        notable_quotes=notable_quotes,
        segments_encountered=segments_encountered,
        highlights=None,
        executive=None,
        agent_coverage=agent_coverage,
    )


__all__ = ["build_video_report"]
