from collections import Counter

from gamesight.schemas.report import DeduplicatedAnalyses, VideoReport
from gamesight.schemas.video import ChunkAnalysisBundle, VideoInfo, VideoTimeline

STOP_RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
FRICTION_ORDER = {"minor": 0, "moderate": 1, "major": 2, "severe": 3}
ENGAGEMENT_ORDER = {"light": 0, "clear": 1, "strong": 2, "signature": 3}


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
        recommendations.append(f"Reduce {driver.replace('_', ' ')} friction in the highest-risk gameplay beats.")
    for clarity_fix in clarity_fixes[:2]:
        recommendations.append(f"Prioritize this communication fix: {clarity_fix}.")
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

    return VideoReport(
        video_id=video.video_id,
        filename=video.filename,
        duration_seconds=video.duration_seconds,
        chunk_count=len(analyses),
        game_title=timeline.game_title,
        session_arc=timeline.session_arc,
        friction_moments=deduplicated.friction_moments,
        clarity_moments=deduplicated.clarity_moments,
        delight_moments=deduplicated.delight_moments,
        quality_issues=deduplicated.quality_issues,
        top_stop_risk_drivers=top_stop_risk_drivers,
        top_praised_features=top_praised_features,
        top_clarity_fixes=top_clarity_fixes,
        bug_count=bug_count,
        overall_friction=highest_friction,
        overall_engagement=highest_engagement,
        overall_stop_risk=highest_stop_risk,
        recommendations=recommendations,
    )


__all__ = ["build_video_report"]
