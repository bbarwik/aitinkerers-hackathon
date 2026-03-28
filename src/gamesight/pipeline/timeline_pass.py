import google.genai as genai
from google.genai import types

from gamesight.config import (
    AnalysisConfig,
    TIMELINE_FPS,
    normalize_segment_label,
    parse_mmss,
    relative_to_absolute,
    to_mmss,
    validate_relative_timestamp,
)
from gamesight.gemini.generate import build_video_part, generate_structured
from gamesight.pipeline.dedup import is_owned
from gamesight.prompts import TIMELINE_ANALYSIS_PROMPT, TIMELINE_SYSTEM_PROMPT
from gamesight.schemas.timeline import TimelineChunkResult
from gamesight.schemas.video import (
    ChunkInfo,
    TimelineChunkRecord,
    TimelineEvent,
    TimelineThreadRecord,
    VideoInfo,
    VideoTimeline,
)


def render_accumulated_context(previous_results: list[TimelineChunkResult]) -> str:
    if not previous_results:
        return "No previous segment context."

    sections: list[str] = ["Previous segments:"]
    for index, result in enumerate(previous_results, start=1):
        thread_lines = (
            ", ".join(f"{thread.thread_name} ({thread.current_status})" for thread in result.carryover_threads)
            or "None"
        )
        sections.append(f"Segment {index} summary: {result.chunk_summary}")
        sections.append(f"Segment {index} objective: {result.player_objective}")
        sections.append(f"Segment {index} emotional trajectory: {result.emotional_trajectory}")
        sections.append(f"Segment {index} pacing breakdown: {result.pacing_breakdown}")
        sections.append(f"Segment {index} carryover threads: {thread_lines}")
    return "\n".join(sections)


def render_chunk_timeline_context(timeline: VideoTimeline, chunk_index: int) -> str:
    chunk_record = timeline.chunks[chunk_index]
    result = chunk_record.result
    event_lines = [
        f"{moment.relative_timestamp} {moment.phase_kind.value}: {moment.event_description}" for moment in result.events
    ]
    thread_lines = [
        f"{thread.thread_name} ({thread.current_status}): {thread.evidence}" for thread in result.carryover_threads
    ]
    parts = [
        f"Summary: {result.chunk_summary}",
        f"Objective: {result.player_objective}",
        f"Emotional trajectory: {result.emotional_trajectory}",
        f"Pacing breakdown: {result.pacing_breakdown}",
        "Key timeline moments:",
        "\n".join(f"- {line}" for line in event_lines) if event_lines else "- None recorded",
        "Carryover threads:",
        "\n".join(f"- {line}" for line in thread_lines) if thread_lines else "- None recorded",
    ]
    return "\n".join(parts)


async def run_timeline_pass(
    client: genai.Client,
    video: VideoInfo,
    chunks: list[ChunkInfo],
    file_refs: dict[int, types.File],
    analysis_config: AnalysisConfig,
) -> VideoTimeline:
    chunk_records: list[TimelineChunkRecord] = []
    events: list[TimelineEvent] = []
    thread_records: list[TimelineThreadRecord] = []
    previous_results: list[TimelineChunkResult] = []
    total_chunks = len(chunks)

    for chunk in chunks:
        video_part = build_video_part(chunk, TIMELINE_FPS, file_refs.get(chunk.index))
        system_prompt = TIMELINE_SYSTEM_PROMPT.format(
            start_mmss=to_mmss(chunk.start_seconds),
            end_mmss=to_mmss(chunk.end_seconds),
            total_duration_mmss=to_mmss(video.duration_seconds),
            chunk_max_mmss=to_mmss(chunk.duration_seconds),
            chunk_index=chunk.index + 1,
            total_chunks=total_chunks,
            previous_context=render_accumulated_context(previous_results),
        )
        result = await generate_structured(
            client,
            contents=[types.Content(role="user", parts=[video_part, types.Part(text=TIMELINE_ANALYSIS_PROMPT)])],
            response_schema=TimelineChunkResult,
            system_instruction=system_prompt,
            thinking_level="low",
        )
        for event in result.events:
            event.relative_timestamp = validate_relative_timestamp(
                event.relative_timestamp,
                chunk.start_seconds,
                chunk.duration_seconds,
            )
            event.segment_label = normalize_segment_label(event.segment_label) or "unknown"
        chunk_records.append(
            TimelineChunkRecord(
                chunk_index=chunk.index,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                result=result,
            )
        )
        for event in result.events:
            if not is_owned(parse_mmss(event.relative_timestamp), chunk):
                continue
            absolute_seconds, absolute_timestamp = relative_to_absolute(event.relative_timestamp, chunk.start_seconds)
            events.append(
                TimelineEvent(
                    source_chunk_index=chunk.index,
                    absolute_seconds=absolute_seconds,
                    absolute_timestamp=absolute_timestamp,
                    relative_timestamp=event.relative_timestamp,
                    visual_observation=event.visual_observation,
                    audio_observation=event.audio_observation,
                    player_expression=event.player_expression,
                    event_description=event.event_description,
                    phase_kind=event.phase_kind,
                    significance=event.significance,
                    segment_label=event.segment_label,
                )
            )
        for thread in result.carryover_threads:
            thread_records.append(
                TimelineThreadRecord(
                    source_chunk_index=chunk.index,
                    thread_name=thread.thread_name,
                    evidence=thread.evidence,
                    current_status=thread.current_status,
                )
            )
        previous_results.append(result)

    events.sort(key=lambda item: item.absolute_seconds)
    thread_states: dict[str, str] = {}
    for thread_record in thread_records:
        thread_states[thread_record.thread_name] = thread_record.current_status
    active_threads = [name for name, status in thread_states.items() if status != "resolved"]
    session_arc = "\n".join(
        f"[{to_mmss(record.start_seconds)}-{to_mmss(record.end_seconds)}] {record.result.emotional_trajectory}"
        for record in chunk_records
    )

    return VideoTimeline(
        video_id=video.video_id,
        game_title=analysis_config.resolved_game_title(video.title),
        session_arc=session_arc,
        chunk_summaries=[record.result.chunk_summary for record in chunk_records],
        objectives=[record.result.player_objective for record in chunk_records],
        active_threads=active_threads,
        events=events,
        thread_records=thread_records,
        chunks=chunk_records,
    )


__all__ = ["render_accumulated_context", "render_chunk_timeline_context", "run_timeline_pass"]
