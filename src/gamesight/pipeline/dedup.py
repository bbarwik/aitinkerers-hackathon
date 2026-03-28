from gamesight.config import (
    BUG_SEVERITY_MAP,
    CLARITY_SEVERITY_MAP,
    DELIGHT_STRENGTH_MAP,
    FRICTION_SEVERITY_MAP,
    MAX_SEVERITY_NUMERIC,
    RETRY_ATTEMPT_SEVERITY_WEIGHT,
    RETRY_QUIT_SIGNAL_SEVERITY_BONUS,
    SENTIMENT_SCORE_MAX,
    SENTIMENT_SCORE_MIN,
    VERBAL_SENTIMENT_MAX,
    VERBAL_SENTIMENT_MIN,
    VERBAL_SEVERITY_WEIGHT,
    clamp,
    normalize_segment_label,
    parse_mmss,
    relative_to_absolute,
    validate_relative_timestamp,
)
from gamesight.schemas.enums import AgentKind
from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo, VideoTimeline


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


def _nearest_segment_label(absolute_seconds: float, timeline: VideoTimeline, max_distance: float = 30.0) -> str | None:
    best_label: str | None = None
    best_distance = max_distance + 1.0
    for event in timeline.events:
        distance = abs(event.absolute_seconds - absolute_seconds)
        if distance < best_distance:
            best_distance = distance
            best_label = event.segment_label
    if best_label is None or best_distance > max_distance:
        return None
    return normalize_segment_label(best_label)


def _canonical_from_friction(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.friction.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        seg_label = _nearest_segment_label(absolute_seconds, timeline)
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
                segment_label=seg_label,
            )
        )
    return moments


def _canonical_from_clarity(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.clarity.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        seg_label = _nearest_segment_label(absolute_seconds, timeline)
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
                segment_label=seg_label,
            )
        )
    return moments


def _canonical_from_delight(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    for moment in analysis.delight.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        seg_label = _nearest_segment_label(absolute_seconds, timeline)
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
                segment_label=seg_label,
            )
        )
    return moments


def _canonical_from_quality(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    issues: list[CanonicalMoment] = []
    for issue in analysis.quality.issues:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(issue.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        seg_label = _nearest_segment_label(absolute_seconds, timeline)
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
                segment_label=seg_label,
            )
        )
    return issues


def _canonical_from_sentiment(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.sentiment:
        return moments
    for moment in analysis.sentiment.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        raw_score = int(clamp(moment.sentiment_score, SENTIMENT_SCORE_MIN, SENTIMENT_SCORE_MAX))
        evidence = [f"Trigger: {moment.trigger}", f"Visual: {moment.visual_basis}", f"Audio: {moment.audio_basis}"]
        if moment.facecam_basis:
            evidence.append(f"Expression: {moment.facecam_basis}")
        if moment.silence_type:
            evidence.append(f"Silence type: {moment.silence_type.value}")
        segment_label = _nearest_segment_label(absolute_seconds, timeline)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.SENTIMENT,
                source_label=moment.dominant_emotion.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.trigger,
                game_context=moment.visual_basis,
                evidence=evidence,
                severity_numeric=abs(raw_score),
                source_chunk_index=chunk.index,
                segment_label=segment_label,
                sentiment_raw_score=raw_score,
            )
        )
    return moments


def _canonical_from_retry(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.retry:
        return moments
    for seq in analysis.retry.retry_sequences:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(seq.first_attempt_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [f"Attempt {a.attempt_number}: {a.outcome} ({a.player_reaction})" for a in seq.attempts]
        evidence.append(f"Frustration: {seq.frustration_escalation}")
        if seq.quit_signal:
            evidence.append("QUIT SIGNAL DETECTED")
        severity = min(
            seq.total_attempts * RETRY_ATTEMPT_SEVERITY_WEIGHT
            + (RETRY_QUIT_SIGNAL_SEVERITY_BONUS if seq.quit_signal else 0),
            MAX_SEVERITY_NUMERIC,
        )
        segment_label = normalize_segment_label(seq.challenge_name) or _nearest_segment_label(
            absolute_seconds, timeline
        )
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.RETRY,
                source_label=seq.challenge_name,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=f"{seq.total_attempts} attempts at {seq.challenge_name}, outcome: {seq.final_outcome.value}",
                game_context=seq.challenge_location,
                evidence=evidence,
                severity_numeric=severity,
                source_chunk_index=chunk.index,
                segment_label=segment_label,
                retry_total_attempts=seq.total_attempts,
                retry_quit_signal=seq.quit_signal,
                retry_final_outcome=seq.final_outcome.value,
            )
        )
    return moments


def _canonical_from_verbal(
    chunk: ChunkInfo,
    analysis: ChunkAnalysisBundle,
    timeline: VideoTimeline,
) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.verbal or not analysis.verbal.has_player_audio:
        return moments
    for moment in analysis.verbal.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        raw_score = int(clamp(moment.sentiment_score, VERBAL_SENTIMENT_MIN, VERBAL_SENTIMENT_MAX))
        evidence = [f"Tone: {moment.voice_tone}", f"Category: {moment.category.value}"]
        if moment.is_actionable and moment.actionable_insight:
            evidence.append(f"Actionable: {moment.actionable_insight}")
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.VERBAL,
                source_label=moment.category.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.quote,
                game_context=moment.game_context,
                evidence=evidence,
                severity_numeric=min(abs(raw_score) * VERBAL_SEVERITY_WEIGHT, MAX_SEVERITY_NUMERIC),
                source_chunk_index=chunk.index,
                segment_label=_nearest_segment_label(absolute_seconds, timeline),
                verbal_is_actionable=moment.is_actionable,
                verbal_quote=moment.quote,
            )
        )
    return moments


def deduplicate_moments(
    chunks: list[ChunkInfo],
    analyses: list[ChunkAnalysisBundle],
    timeline: VideoTimeline,
) -> DeduplicatedAnalyses:
    chunk_map = {chunk.index: chunk for chunk in chunks}
    friction_moments: list[CanonicalMoment] = []
    clarity_moments: list[CanonicalMoment] = []
    delight_moments: list[CanonicalMoment] = []
    quality_issues: list[CanonicalMoment] = []
    sentiment_moments: list[CanonicalMoment] = []
    retry_moments: list[CanonicalMoment] = []
    verbal_moments: list[CanonicalMoment] = []

    for analysis in analyses:
        chunk = chunk_map[analysis.chunk_index]
        friction_moments.extend(_canonical_from_friction(chunk, analysis, timeline))
        clarity_moments.extend(_canonical_from_clarity(chunk, analysis, timeline))
        delight_moments.extend(_canonical_from_delight(chunk, analysis, timeline))
        quality_issues.extend(_canonical_from_quality(chunk, analysis, timeline))
        sentiment_moments.extend(_canonical_from_sentiment(chunk, analysis, timeline))
        retry_moments.extend(_canonical_from_retry(chunk, analysis, timeline))
        verbal_moments.extend(_canonical_from_verbal(chunk, analysis, timeline))

    friction_moments.sort(key=lambda item: item.absolute_seconds)
    clarity_moments.sort(key=lambda item: item.absolute_seconds)
    delight_moments.sort(key=lambda item: item.absolute_seconds)
    quality_issues.sort(key=lambda item: item.absolute_seconds)
    sentiment_moments.sort(key=lambda item: item.absolute_seconds)
    retry_moments.sort(key=lambda item: item.absolute_seconds)
    verbal_moments.sort(key=lambda item: item.absolute_seconds)

    return DeduplicatedAnalyses(
        friction_moments=friction_moments,
        clarity_moments=clarity_moments,
        delight_moments=delight_moments,
        quality_issues=quality_issues,
        sentiment_moments=sentiment_moments,
        retry_moments=retry_moments,
        verbal_moments=verbal_moments,
    )


__all__ = ["deduplicate_moments", "is_owned"]
