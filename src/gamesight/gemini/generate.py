import asyncio
from typing import Any, TypeVar

import google.genai as genai
from google.genai import errors, types
from pydantic import BaseModel

from gamesight.config import DEFAULT_MODEL_ID, LLM_RETRY_DELAYS_SECONDS
from gamesight.gemini.debug import log_interaction
from gamesight.schemas.video import ChunkInfo

ModelT = TypeVar("ModelT", bound=BaseModel)


class GeminiSafetyError(RuntimeError):
    pass


def _strip_json_fence(response_text: str) -> str:
    stripped = response_text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 2 or lines[-1].strip() != "```":
        return stripped
    return "\n".join(lines[1:-1]).strip()


def build_video_part(chunk: ChunkInfo, fps: int, file_ref: types.File | None = None) -> types.Part:
    if chunk.is_youtube:
        assert chunk.youtube_url is not None
        return types.Part(
            file_data=types.FileData(file_uri=chunk.youtube_url),
            video_metadata=types.VideoMetadata(
                start_offset=f"{int(chunk.start_seconds)}s",
                end_offset=f"{int(chunk.end_seconds)}s",
                fps=fps,
            ),
        )
    if file_ref is None:
        raise ValueError("Local chunks require an uploaded Gemini file reference.")
    file_uri = getattr(file_ref, "uri", None)
    if not file_uri:
        raise ValueError("Uploaded Gemini file reference is missing a file URI.")
    return types.Part(
        file_data=types.FileData(file_uri=file_uri, mime_type="video/mp4"),
        video_metadata=types.VideoMetadata(fps=fps),
    )


def _finish_reason_name(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return None
    return getattr(finish_reason, "name", None) or str(finish_reason)


def _build_generate_config(
    *,
    response_schema: type[ModelT] | None = None,
    cached_content: str | None = None,
    system_instruction: str | None = None,
    media_resolution: Any = None,
    thinking_level: str = "medium",
) -> types.GenerateContentConfig:
    config_kwargs: dict[str, Any] = {
        "thinking_config": types.ThinkingConfig(thinking_level=thinking_level),
    }
    if cached_content is not None:
        config_kwargs["cached_content"] = cached_content
    if system_instruction is not None:
        config_kwargs["system_instruction"] = system_instruction
    if media_resolution is not None:
        config_kwargs["media_resolution"] = media_resolution
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
    return types.GenerateContentConfig(**config_kwargs)


async def _generate_with_retry(
    client: genai.Client,
    *,
    contents: Any,
    response_schema: type[ModelT] | None = None,
    cached_content: str | None = None,
    system_instruction: str | None = None,
    media_resolution: Any = None,
    thinking_level: str = "medium",
    model: str = DEFAULT_MODEL_ID,
) -> Any:
    last_error: Exception | None = None
    retry_delays = LLM_RETRY_DELAYS_SECONDS

    for attempt_index in range(len(retry_delays) + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=_build_generate_config(
                    response_schema=response_schema,
                    cached_content=cached_content,
                    system_instruction=system_instruction,
                    media_resolution=media_resolution,
                    thinking_level=thinking_level,
                ),
            )
            finish_reason = _finish_reason_name(response)
            log_interaction(
                contents=contents,
                response=response,
                model=model,
                system_instruction=system_instruction,
                cached_content=cached_content,
                media_resolution=media_resolution,
                thinking_level=thinking_level,
                response_schema=response_schema,
            )
            if finish_reason == "SAFETY":
                raise GeminiSafetyError("Gemini blocked the response for safety reasons.")
            return response
        except errors.ServerError as exc:
            last_error = exc
        except errors.ClientError as exc:
            if exc.code == 429:
                last_error = exc
            elif exc.code == 400:
                raise
            else:
                raise

        if attempt_index >= len(retry_delays):
            break
        await asyncio.sleep(retry_delays[attempt_index])

    raise RuntimeError(f"Gemini generation failed after retries: {last_error}")


async def generate_text(
    client: genai.Client,
    contents: Any,
    *,
    cached_content: str | None = None,
    system_instruction: str | None = None,
    media_resolution: Any = None,
    thinking_level: str = "medium",
    model: str = DEFAULT_MODEL_ID,
) -> str:
    response = await _generate_with_retry(
        client,
        contents=contents,
        cached_content=cached_content,
        system_instruction=system_instruction,
        media_resolution=media_resolution,
        thinking_level=thinking_level,
        model=model,
    )
    response_text = getattr(response, "text", None)
    if not response_text:
        raise ValueError("Gemini returned an empty text response.")
    return response_text


async def generate_structured(
    client: genai.Client,
    contents: Any,
    response_schema: type[ModelT],
    *,
    cached_content: str | None = None,
    system_instruction: str | None = None,
    media_resolution: Any = None,
    thinking_level: str = "medium",
    model: str = DEFAULT_MODEL_ID,
) -> ModelT:
    response = await _generate_with_retry(
        client,
        contents=contents,
        response_schema=response_schema,
        cached_content=cached_content,
        system_instruction=system_instruction,
        media_resolution=media_resolution,
        thinking_level=thinking_level,
        model=model,
    )
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, response_schema):
            return parsed
        return response_schema.model_validate(parsed)
    response_text = getattr(response, "text", None)
    if not response_text:
        raise ValueError("Gemini returned empty structured output and response.parsed was None.")
    return response_schema.model_validate_json(_strip_json_fence(response_text))


__all__ = ["GeminiSafetyError", "build_video_part", "generate_structured", "generate_text"]
