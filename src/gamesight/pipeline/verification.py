"""Cross-agent evidence verification via temporal proximity matching.

For each CanonicalMoment, checks how many OTHER agent types flagged a moment
within a configurable time window. Moments corroborated by multiple independent
agents receive higher confidence scores.
"""

from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses

CORROBORATION_WINDOW_SECONDS: float = 15.0


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


def _same_segment_or_unknown(left: CanonicalMoment, right: CanonicalMoment) -> bool:
    if left.segment_label and right.segment_label:
        return left.segment_label == right.segment_label
    return True


def _verify_single(moment: CanonicalMoment, all_moments: list[CanonicalMoment]) -> CanonicalMoment:
    corroborating: set[str] = set()
    for other in all_moments:
        if other.agent_kind == moment.agent_kind:
            continue
        if not _same_segment_or_unknown(moment, other):
            continue
        if abs(other.absolute_seconds - moment.absolute_seconds) <= CORROBORATION_WINDOW_SECONDS:
            corroborating.add(other.agent_kind.value)

    base_confidence = 0.5
    confidence = base_confidence + 0.15 * len(corroborating)
    has_quote = moment.verbal_quote is not None
    if has_quote:
        confidence += 0.1
    confidence = min(confidence, 1.0)

    return CanonicalMoment(
        agent_kind=moment.agent_kind,
        source_label=moment.source_label,
        absolute_seconds=moment.absolute_seconds,
        absolute_timestamp=moment.absolute_timestamp,
        summary=moment.summary,
        game_context=moment.game_context,
        evidence=moment.evidence,
        severity_numeric=moment.severity_numeric,
        source_chunk_index=moment.source_chunk_index,
        segment_label=moment.segment_label,
        confidence_score=round(confidence, 2),
        corroborating_agents=sorted(corroborating),
        sentiment_raw_score=moment.sentiment_raw_score,
        retry_total_attempts=moment.retry_total_attempts,
        retry_quit_signal=moment.retry_quit_signal,
        retry_final_outcome=moment.retry_final_outcome,
        verbal_is_actionable=moment.verbal_is_actionable,
        verbal_quote=moment.verbal_quote,
    )


def verify_moments(deduplicated: DeduplicatedAnalyses) -> DeduplicatedAnalyses:
    all_m = _all_moments(deduplicated)
    return DeduplicatedAnalyses(
        friction_moments=[_verify_single(m, all_m) for m in deduplicated.friction_moments],
        clarity_moments=[_verify_single(m, all_m) for m in deduplicated.clarity_moments],
        delight_moments=[_verify_single(m, all_m) for m in deduplicated.delight_moments],
        quality_issues=[_verify_single(m, all_m) for m in deduplicated.quality_issues],
        sentiment_moments=[_verify_single(m, all_m) for m in deduplicated.sentiment_moments],
        retry_moments=[_verify_single(m, all_m) for m in deduplicated.retry_moments],
        verbal_moments=[_verify_single(m, all_m) for m in deduplicated.verbal_moments],
    )


__all__ = ["verify_moments"]
