"""Curate the top N most significant moments into a highlight reel."""

from gamesight.schemas.highlights import HighlightMoment, HighlightReel
from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses
from gamesight.schemas.video import VideoInfo

AGENT_WEIGHTS: dict[str, float] = {
    "friction": 1.2,
    "clarity": 1.0,
    "delight": 0.8,
    "quality": 1.1,
    "sentiment": 0.7,
    "retry": 1.3,
    "verbal": 0.9,
}

CATEGORY_MAP: dict[str, str] = {
    "friction": "critical_friction",
    "clarity": "clarity_failure",
    "delight": "player_delight",
    "quality": "bug",
    "sentiment": "sentiment_swing",
    "retry": "retry_loop",
    "verbal": "player_feedback",
}

CLUSTER_WINDOW_SECONDS: float = 30.0
MAX_HIGHLIGHTS: int = 10


def _all_moments(deduplicated: DeduplicatedAnalyses) -> list[CanonicalMoment]:
    return [
        *deduplicated.friction_moments,
        *deduplicated.clarity_moments,
        *deduplicated.delight_moments,
        *deduplicated.quality_issues,
        *deduplicated.sentiment_moments,
        *deduplicated.retry_moments,
        *deduplicated.verbal_moments,
    ]


def _importance(moment: CanonicalMoment) -> float:
    weight = AGENT_WEIGHTS.get(moment.agent_kind.value, 1.0)
    corroboration_bonus = 1.0 + 0.3 * len(moment.corroborating_agents)
    return moment.severity_numeric * weight * corroboration_bonus


def build_highlight_reel(video: VideoInfo, deduplicated: DeduplicatedAnalyses) -> HighlightReel:
    all_m = _all_moments(deduplicated)
    if not all_m:
        return HighlightReel(
            video_id=video.video_id,
            total_moments_analyzed=0,
            highlights=[],
            one_line_verdict="No significant moments detected.",
        )

    scored = sorted(all_m, key=_importance, reverse=True)

    selected: list[CanonicalMoment] = []
    for moment in scored:
        if len(selected) >= MAX_HIGHLIGHTS:
            break
        if any(abs(s.absolute_seconds - moment.absolute_seconds) < CLUSTER_WINDOW_SECONDS for s in selected):
            continue
        selected.append(moment)

    highlights: list[HighlightMoment] = []
    for rank, moment in enumerate(selected, 1):
        highlights.append(
            HighlightMoment(
                rank=rank,
                absolute_timestamp=moment.absolute_timestamp,
                absolute_seconds=moment.absolute_seconds,
                clip_start_seconds=max(0.0, moment.absolute_seconds - 10.0),
                clip_end_seconds=min(video.duration_seconds, moment.absolute_seconds + 10.0),
                category=CATEGORY_MAP.get(moment.agent_kind.value, "other"),
                headline=moment.summary[:120],
                why_important=f"Severity {moment.severity_numeric}/10, confidence {moment.confidence_score:.0%}",
                evidence=moment.evidence[:5],
                importance_score=round(_importance(moment), 2),
                corroborating_agents=moment.corroborating_agents,
            )
        )

    top = selected[0] if selected else None
    verdict = top.summary[:200] if top else "Session analysis complete."

    return HighlightReel(
        video_id=video.video_id,
        total_moments_analyzed=len(all_m),
        highlights=highlights,
        one_line_verdict=verdict,
    )


__all__ = ["build_highlight_reel"]
