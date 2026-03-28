import asyncio
from pathlib import Path

import google.genai as genai
from google.genai import types

from gamesight.schemas.video import ChunkInfo

POLL_INTERVAL_SECONDS = 5


async def upload_file(client: genai.Client, file_path: str | Path) -> types.File:
    return await client.aio.files.upload(file=str(file_path))


async def poll_file_until_active(
    client: genai.Client,
    file_ref: types.File,
    *,
    poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
) -> types.File:
    current_file = file_ref
    while True:
        state = getattr(current_file, "state", None)
        state_name = getattr(state, "name", None) if state is not None else None
        if state_name == "ACTIVE":
            return current_file
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed for {current_file.name}: {current_file.error}")
        await asyncio.sleep(poll_interval_seconds)
        current_file_name = current_file.name
        if not current_file_name:
            raise ValueError("Gemini file polling requires a file name, but the file reference did not include one.")
        current_file = await client.aio.files.get(name=current_file_name)


async def delete_file(client: genai.Client, file_ref: types.File | str | None) -> None:
    if file_ref is None:
        return
    file_name = file_ref if isinstance(file_ref, str) else file_ref.name
    if not file_name:
        raise ValueError("Gemini file deletion requires a file name, but the file reference did not include one.")
    await client.aio.files.delete(name=file_name)


async def upload_chunks(
    client: genai.Client,
    chunks: list[ChunkInfo],
    *,
    concurrency: int,
) -> dict[int, types.File]:
    semaphore = asyncio.Semaphore(concurrency)
    uploaded: dict[int, types.File] = {}

    async def _upload_chunk(chunk: ChunkInfo) -> None:
        if chunk.file_path is None:
            raise ValueError("Local chunk uploads require file_path to be set.")
        async with semaphore:
            file_ref = await upload_file(client, chunk.file_path)
            uploaded[chunk.index] = await poll_file_until_active(client, file_ref)

    await asyncio.gather(*(_upload_chunk(chunk) for chunk in chunks))
    return uploaded


__all__ = ["delete_file", "poll_file_until_active", "upload_chunks", "upload_file"]
