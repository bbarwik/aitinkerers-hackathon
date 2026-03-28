import asyncio
import json
import logging
from typing import TypeVar

import google.genai as genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from gamesight.config import (
    AnalysisConfig,
    CACHE_TTL_SECONDS,
    DEFAULT_MODEL_ID,
    MIN_CACHEABLE_CHUNK_SECONDS,
    SENTIMENT_SCORE_MAX,
    SENTIMENT_SCORE_MIN,
    SPECIALIST_FPS,
    VERBAL_SENTIMENT_MAX,
    VERBAL_SENTIMENT_MIN,
    clamp,
    validate_relative_timestamp,
)
from gamesight.gemini.generate import GeminiSafetyError, build_video_part, generate_structured, generate_text
from gamesight.prompts import (
    CLARITY_AGENT_PROMPT,
    DELIGHT_AGENT_PROMPT,
    FRICTION_AGENT_PROMPT,
    QUALITY_AGENT_PROMPT,
    RETRY_AGENT_PROMPT,
    SENTIMENT_AGENT_PROMPT,
    SHARED_SYSTEM_PROMPT,
    VERBAL_AGENT_PROMPT,
    WARMUP_PROMPT_TEMPLATE,
)
from gamesight.schemas.clarity import ClarityChunkAnalysis
from gamesight.schemas.delight import DelightChunkAnalysis
from gamesight.schemas.friction import FrictionChunkAnalysis
from gamesight.schemas.quality import QualityChunkAnalysis
from gamesight.schemas.retry import RetryChunkAnalysis
from gamesight.schemas.sentiment import SentimentChunkAnalysis
from gamesight.schemas.verbal import VerbalChunkAnalysis
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo, VideoTimeline

SPECIALIST_MEDIA_RESOLUTION = types.MediaResolution.MEDIA_RESOLUTION_HIGH
logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


def render_full_timeline_context(timeline: VideoTimeline, chunk_index: int) -> str:
    # Only include session_arc lines up to and including the current chunk
    arc_lines = timeline.session_arc.split("\n")
    arc_through_current = "\n".join(arc_lines[: chunk_index + 1])

    # Only include threads from chunks up to the current one
    thread_names_so_far: set[str] = set()
    for record in timeline.thread_records:
        if record.source_chunk_index <= chunk_index:
            if record.current_status != "resolved":
                thread_names_so_far.add(record.thread_name)
            else:
                thread_names_so_far.discard(record.thread_name)

    payload = {
        "video_id": timeline.video_id,
        "game_title": timeline.game_title,
        "session_arc": arc_through_current,
        "chunk_summaries": timeline.chunk_summaries[: chunk_index + 1],
        "objectives": timeline.objectives[: chunk_index + 1],
        "active_threads": sorted(thread_names_so_far),
        "events": [
            event.model_dump(mode="json") for event in timeline.events if event.source_chunk_index <= chunk_index
        ],
        "thread_records": [
            thread.model_dump(mode="json")
            for thread in timeline.thread_records
            if thread.source_chunk_index <= chunk_index
        ],
        "chunks": [timeline.chunks[index].model_dump(mode="json") for index in range(chunk_index + 1)],
    }
    return f"Full timeline through current chunk (raw JSON):\n```json\n{json.dumps(payload, indent=2)}\n```"


def _render_prior_findings_context(prior_findings: list[ChunkAnalysisBundle]) -> str:
    payload = [finding.model_dump(mode="json") for finding in prior_findings]
    return f"Full prior specialist findings (raw JSON):\n```json\n{json.dumps(payload, indent=2)}\n```"


def _build_specialist_prompt(
    *,
    timeline: VideoTimeline,
    current_chunk_index: int,
    prior_findings: list[ChunkAnalysisBundle],
    game_title: str,
    game_genre: str,
    agent_prompt: str,
) -> str:
    session_metadata = {
        "video_id": timeline.video_id,
        "game_title": game_title,
        "game_genre": game_genre,
        "current_chunk_index": current_chunk_index,
        "current_chunk_number": current_chunk_index + 1,
        "total_chunks": len(timeline.chunks),
    }
    current_chunk_payload = timeline.chunks[current_chunk_index].model_dump(mode="json")
    sections = [
        "Session metadata (raw JSON):",
        f"```json\n{json.dumps(session_metadata, indent=2)}\n```",
        render_full_timeline_context(timeline, current_chunk_index),
        _render_prior_findings_context(prior_findings),
        "Current chunk timeline record (raw JSON):",
        f"```json\n{json.dumps(current_chunk_payload, indent=2)}\n```",
        "Use all prior context for continuity. Analyze only the current chunk for evidence, but interpret it in the context of the full session.",
    ]
    if agent_prompt:
        sections.append(agent_prompt)
    return "\n\n".join(sections)


def _conversation_with_prompt(conversation: list[types.Content], prompt: str) -> list[types.Content]:
    return [*conversation, types.Content(role="user", parts=[types.Part(text=prompt)])]


def _clamp_sentiment_analysis(result: SentimentChunkAnalysis) -> SentimentChunkAnalysis:
    for moment in result.moments:
        moment.sentiment_score = int(clamp(moment.sentiment_score, SENTIMENT_SCORE_MIN, SENTIMENT_SCORE_MAX))
    result.average_sentiment = float(
        clamp(result.average_sentiment, float(SENTIMENT_SCORE_MIN), float(SENTIMENT_SCORE_MAX))
    )
    return result


def _clamp_verbal_analysis(result: VerbalChunkAnalysis) -> VerbalChunkAnalysis:
    for moment in result.moments:
        moment.sentiment_score = int(clamp(moment.sentiment_score, VERBAL_SENTIMENT_MIN, VERBAL_SENTIMENT_MAX))
    return result


def _normalize_specialist_timestamps(
    chunk: ChunkInfo,
    *,
    friction: FrictionChunkAnalysis,
    clarity: ClarityChunkAnalysis,
    delight: DelightChunkAnalysis,
    quality: QualityChunkAnalysis,
    sentiment: SentimentChunkAnalysis | None = None,
    retry: RetryChunkAnalysis | None = None,
    verbal: VerbalChunkAnalysis | None = None,
) -> tuple[SentimentChunkAnalysis | None, RetryChunkAnalysis | None, VerbalChunkAnalysis | None]:
    for moment in friction.moments:
        moment.relative_timestamp = validate_relative_timestamp(
            moment.relative_timestamp,
            chunk.start_seconds,
            chunk.duration_seconds,
        )
    for moment in clarity.moments:
        moment.relative_timestamp = validate_relative_timestamp(
            moment.relative_timestamp,
            chunk.start_seconds,
            chunk.duration_seconds,
        )
    for moment in delight.moments:
        moment.relative_timestamp = validate_relative_timestamp(
            moment.relative_timestamp,
            chunk.start_seconds,
            chunk.duration_seconds,
        )
    for issue in quality.issues:
        issue.relative_timestamp = validate_relative_timestamp(
            issue.relative_timestamp,
            chunk.start_seconds,
            chunk.duration_seconds,
        )
    if sentiment:
        try:
            for moment in sentiment.moments:
                moment.relative_timestamp = validate_relative_timestamp(
                    moment.relative_timestamp,
                    chunk.start_seconds,
                    chunk.duration_seconds,
                )
        except ValueError as exc:
            logger.warning("Discarding sentiment analysis for chunk %s due to invalid timestamps: %s", chunk.index, exc)
            sentiment = None
    if retry:
        try:
            for seq in retry.retry_sequences:
                seq.first_attempt_timestamp = validate_relative_timestamp(
                    seq.first_attempt_timestamp,
                    chunk.start_seconds,
                    chunk.duration_seconds,
                )
                for attempt in seq.attempts:
                    attempt.relative_timestamp = validate_relative_timestamp(
                        attempt.relative_timestamp,
                        chunk.start_seconds,
                        chunk.duration_seconds,
                    )
        except ValueError as exc:
            logger.warning("Discarding retry analysis for chunk %s due to invalid timestamps: %s", chunk.index, exc)
            retry = None
    if verbal:
        try:
            for moment in verbal.moments:
                moment.relative_timestamp = validate_relative_timestamp(
                    moment.relative_timestamp,
                    chunk.start_seconds,
                    chunk.duration_seconds,
                )
        except ValueError as exc:
            logger.warning("Discarding verbal analysis for chunk %s due to invalid timestamps: %s", chunk.index, exc)
            verbal = None

    return sentiment, retry, verbal


async def _run_cached_agent(
    client: genai.Client,
    *,
    cache_name: str,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
) -> ModelT:
    return await generate_structured(
        client,
        contents=_conversation_with_prompt(conversation, prompt),
        response_schema=response_schema,
        cached_content=cache_name,
        media_resolution=SPECIALIST_MEDIA_RESOLUTION,
        thinking_level="medium",
    )


async def _run_direct_agent(
    client: genai.Client,
    *,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
    media_resolution: types.MediaResolution | None,
) -> ModelT:
    return await generate_structured(
        client,
        contents=_conversation_with_prompt(conversation, prompt),
        response_schema=response_schema,
        system_instruction=SHARED_SYSTEM_PROMPT,
        media_resolution=media_resolution,
        thinking_level="medium",
    )


async def _safe_cached_agent(
    client: genai.Client,
    *,
    cache_name: str,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
) -> ModelT | None:
    try:
        return await _run_cached_agent(
            client,
            cache_name=cache_name,
            conversation=conversation,
            prompt=prompt,
            response_schema=response_schema,
        )
    except (GeminiSafetyError, ValidationError, ValueError) as exc:
        logger.warning("Optional cached agent %s failed with recoverable error: %s", response_schema.__name__, exc)
        return None


async def _safe_direct_agent(
    client: genai.Client,
    *,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
    media_resolution: types.MediaResolution | None,
) -> ModelT | None:
    try:
        return await _run_direct_agent(
            client,
            conversation=conversation,
            prompt=prompt,
            response_schema=response_schema,
            media_resolution=media_resolution,
        )
    except (GeminiSafetyError, ValidationError, ValueError) as exc:
        logger.warning("Optional direct agent %s failed with recoverable error: %s", response_schema.__name__, exc)
        return None


async def run_cached_specialist_pass(
    client: genai.Client,
    *,
    chunk: ChunkInfo,
    file_ref: types.File,
    timeline: VideoTimeline,
    prior_findings: list[ChunkAnalysisBundle],
    game_title: str,
    game_genre: str,
) -> ChunkAnalysisBundle:
    video_part = build_video_part(chunk, SPECIALIST_FPS, file_ref)
    shared_context_prompt = _build_specialist_prompt(
        timeline=timeline,
        current_chunk_index=chunk.index,
        prior_findings=prior_findings,
        game_title=game_title,
        game_genre=game_genre,
        agent_prompt="",
    )
    warmup_prompt = f"{shared_context_prompt}\n\n{WARMUP_PROMPT_TEMPLATE}"
    cache = await client.aio.caches.create(
        model=f"models/{DEFAULT_MODEL_ID}",
        config=types.CreateCachedContentConfig(
            system_instruction=SHARED_SYSTEM_PROMPT,
            contents=[types.Content(role="user", parts=[video_part])],
            ttl=f"{CACHE_TTL_SECONDS}s",
        ),
    )
    cache_name = cache.name
    if not cache_name:
        raise ValueError("Gemini cache creation returned no cache name, so specialist warmup cannot continue.")
    try:
        warmup_response = await generate_text(
            client,
            contents=warmup_prompt,
            cached_content=cache_name,
            media_resolution=SPECIALIST_MEDIA_RESOLUTION,
            thinking_level="low",
        )
        warmup_conversation = [
            types.Content(role="user", parts=[types.Part(text=warmup_prompt)]),
            types.Content(role="model", parts=[types.Part(text=warmup_response)]),
        ]
        friction, clarity, delight, quality = await asyncio.gather(
            _run_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=FRICTION_AGENT_PROMPT,
                response_schema=FrictionChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=CLARITY_AGENT_PROMPT,
                response_schema=ClarityChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=DELIGHT_AGENT_PROMPT,
                response_schema=DelightChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=QUALITY_AGENT_PROMPT,
                response_schema=QualityChunkAnalysis,
            ),
        )
        sentiment, retry, verbal = await asyncio.gather(
            _safe_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=SENTIMENT_AGENT_PROMPT,
                response_schema=SentimentChunkAnalysis,
            ),
            _safe_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=RETRY_AGENT_PROMPT,
                response_schema=RetryChunkAnalysis,
            ),
            _safe_cached_agent(
                client,
                cache_name=cache_name,
                conversation=warmup_conversation,
                prompt=VERBAL_AGENT_PROMPT,
                response_schema=VerbalChunkAnalysis,
            ),
        )
        if sentiment is not None:
            sentiment = _clamp_sentiment_analysis(sentiment)
        if verbal is not None:
            verbal = _clamp_verbal_analysis(verbal)
    finally:
        await client.aio.caches.delete(name=cache_name)

    sentiment, retry, verbal = _normalize_specialist_timestamps(
        chunk,
        friction=friction,
        clarity=clarity,
        delight=delight,
        quality=quality,
        sentiment=sentiment,
        retry=retry,
        verbal=verbal,
    )
    return ChunkAnalysisBundle(
        chunk_index=chunk.index,
        friction=friction,
        clarity=clarity,
        delight=delight,
        quality=quality,
        sentiment=sentiment,
        retry=retry,
        verbal=verbal,
    )


async def run_direct_specialist_pass(
    client: genai.Client,
    *,
    chunk: ChunkInfo,
    file_ref: types.File | None,
    timeline: VideoTimeline,
    prior_findings: list[ChunkAnalysisBundle],
    game_title: str,
    game_genre: str,
) -> ChunkAnalysisBundle:
    media_resolution = None if chunk.is_youtube else SPECIALIST_MEDIA_RESOLUTION
    video_part = build_video_part(chunk, SPECIALIST_FPS, file_ref)
    shared_context_prompt = _build_specialist_prompt(
        timeline=timeline,
        current_chunk_index=chunk.index,
        prior_findings=prior_findings,
        game_title=game_title,
        game_genre=game_genre,
        agent_prompt="",
    )
    warmup_prompt = f"{shared_context_prompt}\n\n{WARMUP_PROMPT_TEMPLATE}"
    warmup_contents = [types.Content(role="user", parts=[video_part, types.Part(text=warmup_prompt)])]
    warmup_response = await generate_text(
        client,
        contents=warmup_contents,
        system_instruction=SHARED_SYSTEM_PROMPT,
        media_resolution=media_resolution,
        thinking_level="low",
    )
    warmup_conversation = [
        types.Content(role="user", parts=[video_part, types.Part(text=warmup_prompt)]),
        types.Content(role="model", parts=[types.Part(text=warmup_response)]),
    ]
    friction, clarity, delight, quality = await asyncio.gather(
        _run_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=FRICTION_AGENT_PROMPT,
            response_schema=FrictionChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=CLARITY_AGENT_PROMPT,
            response_schema=ClarityChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=DELIGHT_AGENT_PROMPT,
            response_schema=DelightChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=QUALITY_AGENT_PROMPT,
            response_schema=QualityChunkAnalysis,
            media_resolution=media_resolution,
        ),
    )
    sentiment, retry, verbal = await asyncio.gather(
        _safe_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=SENTIMENT_AGENT_PROMPT,
            response_schema=SentimentChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _safe_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=RETRY_AGENT_PROMPT,
            response_schema=RetryChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _safe_direct_agent(
            client,
            conversation=warmup_conversation,
            prompt=VERBAL_AGENT_PROMPT,
            response_schema=VerbalChunkAnalysis,
            media_resolution=media_resolution,
        ),
    )
    if sentiment is not None:
        sentiment = _clamp_sentiment_analysis(sentiment)
    if verbal is not None:
        verbal = _clamp_verbal_analysis(verbal)
    sentiment, retry, verbal = _normalize_specialist_timestamps(
        chunk,
        friction=friction,
        clarity=clarity,
        delight=delight,
        quality=quality,
        sentiment=sentiment,
        retry=retry,
        verbal=verbal,
    )
    return ChunkAnalysisBundle(
        chunk_index=chunk.index,
        friction=friction,
        clarity=clarity,
        delight=delight,
        quality=quality,
        sentiment=sentiment,
        retry=retry,
        verbal=verbal,
    )


async def run_chunk_agents(
    client: genai.Client,
    chunks: list[ChunkInfo],
    file_refs: dict[int, types.File],
    timeline: VideoTimeline,
    analysis_config: AnalysisConfig,
) -> list[ChunkAnalysisBundle]:
    results: list[ChunkAnalysisBundle] = []
    game_title = timeline.game_title

    for chunk in chunks:
        file_ref = file_refs.get(chunk.index)
        try:
            if (
                not chunk.is_youtube
                and analysis_config.use_caching
                and chunk.duration_seconds >= MIN_CACHEABLE_CHUNK_SECONDS
            ):
                if file_ref is None:
                    raise ValueError(f"Missing uploaded Gemini file for chunk {chunk.index}.")
                try:
                    result = await run_cached_specialist_pass(
                        client,
                        chunk=chunk,
                        file_ref=file_ref,
                        timeline=timeline,
                        prior_findings=results,
                        game_title=game_title,
                        game_genre=analysis_config.game_genre,
                    )
                except errors.ClientError as exc:
                    if exc.code != 400:
                        raise
                    result = await run_direct_specialist_pass(
                        client,
                        chunk=chunk,
                        file_ref=file_ref,
                        timeline=timeline,
                        prior_findings=results,
                        game_title=game_title,
                        game_genre=analysis_config.game_genre,
                    )
            else:
                result = await run_direct_specialist_pass(
                    client,
                    chunk=chunk,
                    file_ref=file_ref,
                    timeline=timeline,
                    prior_findings=results,
                    game_title=game_title,
                    game_genre=analysis_config.game_genre,
                )
            results.append(result)
        except GeminiSafetyError:
            logger.warning("Skipping chunk %s because Gemini blocked it for safety.", chunk.index)

    return results


__all__ = [
    "render_full_timeline_context",
    "run_cached_specialist_pass",
    "run_chunk_agents",
    "run_direct_specialist_pass",
]
