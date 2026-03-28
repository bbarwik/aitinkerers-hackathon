import asyncio
import logging
from typing import TypeVar

import google.genai as genai
from google.genai import errors, types
from pydantic import BaseModel

from gamesight.config import (
    AnalysisConfig,
    CACHE_TTL_SECONDS,
    DEFAULT_MODEL_ID,
    MIN_CACHEABLE_CHUNK_SECONDS,
    SPECIALIST_FPS,
)
from gamesight.gemini.generate import GeminiSafetyError, build_video_part, generate_structured, generate_text
from gamesight.prompts import (
    CLARITY_AGENT_PROMPT,
    DELIGHT_AGENT_PROMPT,
    FRICTION_AGENT_PROMPT,
    QUALITY_AGENT_PROMPT,
    SHARED_SYSTEM_PROMPT,
    WARMUP_PROMPT_TEMPLATE,
)
from gamesight.schemas.clarity import ClarityChunkAnalysis
from gamesight.schemas.delight import DelightChunkAnalysis
from gamesight.schemas.friction import FrictionChunkAnalysis
from gamesight.schemas.quality import QualityChunkAnalysis
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo, VideoTimeline
from gamesight.pipeline.timeline_pass import render_chunk_timeline_context

SPECIALIST_MEDIA_RESOLUTION = types.MediaResolution.MEDIA_RESOLUTION_HIGH
logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


def _build_specialist_prompt(
    *,
    game_title: str,
    game_genre: str,
    timeline_context: str,
    agent_prompt: str,
) -> str:
    return (
        f"Game: {game_title} ({game_genre})\n"
        f"Session context for this segment:\n{timeline_context}\n\n"
        "Proceed with the specialized analysis below.\n\n"
        f"{agent_prompt}"
    )


def _conversation_with_prompt(conversation: list[types.Content], prompt: str) -> list[types.Content]:
    return [*conversation, types.Content(role="user", parts=[types.Part(text=prompt)])]


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


async def run_cached_specialist_pass(
    client: genai.Client,
    *,
    chunk: ChunkInfo,
    file_ref: types.File,
    timeline_context: str,
    game_title: str,
    game_genre: str,
) -> ChunkAnalysisBundle:
    video_part = build_video_part(chunk, SPECIALIST_FPS, file_ref)
    warmup_prompt = WARMUP_PROMPT_TEMPLATE.format(
        game_title=game_title,
        game_genre=game_genre,
        timeline_context=timeline_context,
    )
    cache = await client.aio.caches.create(
        model=f"models/{DEFAULT_MODEL_ID}",
        config=types.CreateCachedContentConfig(
            system_instruction=SHARED_SYSTEM_PROMPT,
            contents=[types.Content(role="user", parts=[video_part])],
            ttl=f"{CACHE_TTL_SECONDS}s",
        ),
    )
    try:
        warmup_response = await generate_text(
            client,
            contents=warmup_prompt,
            cached_content=cache.name,
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
                cache_name=cache.name,
                conversation=warmup_conversation,
                prompt=FRICTION_AGENT_PROMPT,
                response_schema=FrictionChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache.name,
                conversation=warmup_conversation,
                prompt=CLARITY_AGENT_PROMPT,
                response_schema=ClarityChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache.name,
                conversation=warmup_conversation,
                prompt=DELIGHT_AGENT_PROMPT,
                response_schema=DelightChunkAnalysis,
            ),
            _run_cached_agent(
                client,
                cache_name=cache.name,
                conversation=warmup_conversation,
                prompt=QUALITY_AGENT_PROMPT,
                response_schema=QualityChunkAnalysis,
            ),
        )
        return ChunkAnalysisBundle(
            chunk_index=chunk.index,
            friction=friction,
            clarity=clarity,
            delight=delight,
            quality=quality,
        )
    finally:
        await client.aio.caches.delete(name=cache.name)


async def _run_direct_agent(
    client: genai.Client,
    *,
    chunk: ChunkInfo,
    file_ref: types.File | None,
    prompt: str,
    response_schema: type[ModelT],
    media_resolution: types.MediaResolution | None,
) -> ModelT:
    video_part = build_video_part(chunk, SPECIALIST_FPS, file_ref)
    return await generate_structured(
        client,
        contents=[types.Content(role="user", parts=[video_part, types.Part(text=prompt)])],
        response_schema=response_schema,
        system_instruction=SHARED_SYSTEM_PROMPT,
        media_resolution=media_resolution,
        thinking_level="medium",
    )


async def run_direct_specialist_pass(
    client: genai.Client,
    *,
    chunk: ChunkInfo,
    file_ref: types.File | None,
    timeline_context: str,
    game_title: str,
    game_genre: str,
) -> ChunkAnalysisBundle:
    media_resolution = None if chunk.is_youtube else SPECIALIST_MEDIA_RESOLUTION
    friction_prompt = _build_specialist_prompt(
        game_title=game_title,
        game_genre=game_genre,
        timeline_context=timeline_context,
        agent_prompt=FRICTION_AGENT_PROMPT,
    )
    clarity_prompt = _build_specialist_prompt(
        game_title=game_title,
        game_genre=game_genre,
        timeline_context=timeline_context,
        agent_prompt=CLARITY_AGENT_PROMPT,
    )
    delight_prompt = _build_specialist_prompt(
        game_title=game_title,
        game_genre=game_genre,
        timeline_context=timeline_context,
        agent_prompt=DELIGHT_AGENT_PROMPT,
    )
    quality_prompt = _build_specialist_prompt(
        game_title=game_title,
        game_genre=game_genre,
        timeline_context=timeline_context,
        agent_prompt=QUALITY_AGENT_PROMPT,
    )
    friction, clarity, delight, quality = await asyncio.gather(
        _run_direct_agent(
            client,
            chunk=chunk,
            file_ref=file_ref,
            prompt=friction_prompt,
            response_schema=FrictionChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            chunk=chunk,
            file_ref=file_ref,
            prompt=clarity_prompt,
            response_schema=ClarityChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            chunk=chunk,
            file_ref=file_ref,
            prompt=delight_prompt,
            response_schema=DelightChunkAnalysis,
            media_resolution=media_resolution,
        ),
        _run_direct_agent(
            client,
            chunk=chunk,
            file_ref=file_ref,
            prompt=quality_prompt,
            response_schema=QualityChunkAnalysis,
            media_resolution=media_resolution,
        ),
    )
    return ChunkAnalysisBundle(
        chunk_index=chunk.index,
        friction=friction,
        clarity=clarity,
        delight=delight,
        quality=quality,
    )


async def run_chunk_agents(
    client: genai.Client,
    chunks: list[ChunkInfo],
    file_refs: dict[int, types.File],
    timeline: VideoTimeline,
    analysis_config: AnalysisConfig,
) -> list[ChunkAnalysisBundle]:
    semaphore = asyncio.Semaphore(analysis_config.chunk_concurrency)
    results: dict[int, ChunkAnalysisBundle] = {}
    game_title = timeline.game_title

    async def _run_for_chunk(chunk: ChunkInfo) -> None:
        timeline_context = render_chunk_timeline_context(timeline, chunk.index)
        file_ref = file_refs.get(chunk.index)
        try:
            async with semaphore:
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
                            timeline_context=timeline_context,
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
                            timeline_context=timeline_context,
                            game_title=game_title,
                            game_genre=analysis_config.game_genre,
                        )
                else:
                    result = await run_direct_specialist_pass(
                        client,
                        chunk=chunk,
                        file_ref=file_ref,
                        timeline_context=timeline_context,
                        game_title=game_title,
                        game_genre=analysis_config.game_genre,
                    )
                results[chunk.index] = result
        except GeminiSafetyError:
            logger.warning("Skipping chunk %s because Gemini blocked it for safety.", chunk.index)

    await asyncio.gather(*(_run_for_chunk(chunk) for chunk in chunks))
    return [results[index] for index in sorted(results)]


__all__ = ["run_cached_specialist_pass", "run_chunk_agents", "run_direct_specialist_pass"]
