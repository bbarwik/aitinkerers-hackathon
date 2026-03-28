from gamesight.config import (
    BUG_SEVERITY_MAP,
    CLARITY_SEVERITY_MAP,
    DELIGHT_STRENGTH_MAP,
    FRICTION_SEVERITY_MAP,
    parse_mmss,
    relative_to_absolute,
    validate_relative_timestamp,
)
from gamesight.schemas.enums import AgentKind
from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo


def is_owned(relative_seconds: float, chunk: ChunkInfo) -> bool:
    absolute_seconds = chunk.start_seconds + relative_seconds
    return chunk.owns_from <= absolute_seconds < chunk.owns_until


def _validated_relative_seconds(raw_timestamp: str, chunk: ChunkInfo) -> tuple[str, float]:
    corrected_timestamp = validate_relative_timestamp(
        raw_timestamp,
        chunk.start_seconds,
        chunk.duration_seconds,
    )
    return corrected_timestamp, parse_mmss(corrected_timestamp)


def _canonical_from_friction(chunk: ChunkInfo, analysis: ChunkAnalysisBundle) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.friction.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [*moment.visual_signals, *moment.audio_signals]
        evidence.append(f"Scene: {moment.scene_description}")
        if moment.player_expression:
            evidence.append(f"Expression: {moment.player_expression}")
        evidence.extend(f"Quote: {feedback}" for feedback in moment.verbal_feedback)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.FRICTION,
                source_label=moment.source.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.root_cause,
                game_context=moment.game_context,
                evidence=evidence,
                severity_numeric=FRICTION_SEVERITY_MAP[moment.severity.value],
                source_chunk_index=chunk.index,
            )
        )
    return moments


def _canonical_from_clarity(chunk: ChunkInfo, analysis: ChunkAnalysisBundle) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.clarity.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [*moment.visual_signals, *moment.audio_signals]
        evidence.append(f"Scene: {moment.scene_description}")
        if moment.player_expression:
            evidence.append(f"Expression: {moment.player_expression}")
        evidence.extend(f"Quote: {feedback}" for feedback in moment.verbal_feedback)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.CLARITY,
                source_label=moment.issue_type.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.missing_cue,
                game_context=moment.intended_behavior,
                evidence=evidence,
                severity_numeric=CLARITY_SEVERITY_MAP[moment.severity.value],
                source_chunk_index=chunk.index,
            )
        )
    return moments


def _canonical_from_delight(chunk: ChunkInfo, analysis: ChunkAnalysisBundle) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.delight.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [*moment.visual_signals, *moment.audio_signals]
        evidence.append(f"Scene: {moment.scene_description}")
        if moment.player_expression:
            evidence.append(f"Expression: {moment.player_expression}")
        evidence.extend(f"Quote: {feedback}" for feedback in moment.verbal_feedback)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.DELIGHT,
                source_label=moment.driver.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.why_it_works,
                game_context=moment.game_context,
                evidence=evidence,
                severity_numeric=DELIGHT_STRENGTH_MAP[moment.strength.value],
                source_chunk_index=chunk.index,
            )
        )
    return moments


def _canonical_from_quality(chunk: ChunkInfo, analysis: ChunkAnalysisBundle) -> list[CanonicalMoment]:
    issues: list[CanonicalMoment] = []
    for issue in analysis.quality.issues:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(issue.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [*issue.visual_symptoms, *issue.audio_symptoms, f"Player reaction: {issue.player_reaction}"]
        evidence.append(f"Scene: {issue.scene_description}")
        evidence.extend(f"Quote: {feedback}" for feedback in issue.verbal_feedback)
        symptom_summary = ", ".join(issue.visual_symptoms) if issue.visual_symptoms else "visible issue"
        summary = f"{issue.category.value.replace('_', ' ')} issue: {symptom_summary}"
        if issue.reproduction_context:
            summary = f"{summary} during {issue.reproduction_context}"
        issues.append(
            CanonicalMoment(
                agent_kind=AgentKind.QUALITY,
                source_label=issue.category.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=summary,
                game_context=issue.reproduction_context,
                evidence=evidence,
                severity_numeric=BUG_SEVERITY_MAP[issue.severity.value],
                source_chunk_index=chunk.index,
            )
        )
    return issues


def deduplicate_moments(chunks: list[ChunkInfo], analyses: list[ChunkAnalysisBundle]) -> DeduplicatedAnalyses:
    chunk_map = {chunk.index: chunk for chunk in chunks}
    friction_moments: list[CanonicalMoment] = []
    clarity_moments: list[CanonicalMoment] = []
    delight_moments: list[CanonicalMoment] = []
    quality_issues: list[CanonicalMoment] = []

    for analysis in analyses:
        chunk = chunk_map[analysis.chunk_index]
        friction_moments.extend(_canonical_from_friction(chunk, analysis))
        clarity_moments.extend(_canonical_from_clarity(chunk, analysis))
        delight_moments.extend(_canonical_from_delight(chunk, analysis))
        quality_issues.extend(_canonical_from_quality(chunk, analysis))

    friction_moments.sort(key=lambda item: item.absolute_seconds)
    clarity_moments.sort(key=lambda item: item.absolute_seconds)
    delight_moments.sort(key=lambda item: item.absolute_seconds)
    quality_issues.sort(key=lambda item: item.absolute_seconds)

    return DeduplicatedAnalyses(
        friction_moments=friction_moments,
        clarity_moments=clarity_moments,
        delight_moments=delight_moments,
        quality_issues=quality_issues,
    )


__all__ = ["deduplicate_moments", "is_owned"]
