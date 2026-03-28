from pathlib import Path

import asyncio
import ffmpeg

from gamesight.config import CHUNK_DURATION_SECONDS, CHUNK_OVERLAP_SECONDS
from gamesight.schemas.video import ChunkInfo


def compute_chunks(
    duration_seconds: float,
    *,
    source_path: str | Path | None = None,
    youtube_url: str | None = None,
    output_dir: str | Path | None = None,
    chunk_duration_seconds: int = CHUNK_DURATION_SECONDS,
    overlap_seconds: int = CHUNK_OVERLAP_SECONDS,
) -> list[ChunkInfo]:
    if duration_seconds <= 0:
        return []

    step_seconds = chunk_duration_seconds - overlap_seconds
    chunks: list[ChunkInfo] = []
    start_seconds = 0.0
    chunk_index = 0
    resolved_output_dir = Path(output_dir) if output_dir is not None else None

    while start_seconds < duration_seconds:
        end_seconds = min(start_seconds + chunk_duration_seconds, duration_seconds)
        owns_from = 0.0 if chunk_index == 0 else start_seconds + overlap_seconds / 2
        owns_until = duration_seconds if end_seconds >= duration_seconds else end_seconds - overlap_seconds / 2
        if resolved_output_dir is not None:
            file_path = str(resolved_output_dir / f"chunk_{chunk_index:03d}.mp4")
        else:
            file_path = str(source_path) if source_path is not None else None
        chunks.append(
            ChunkInfo(
                index=chunk_index,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                file_path=file_path,
                youtube_url=youtube_url,
                owns_from=owns_from,
                owns_until=max(owns_until, owns_from),
            )
        )
        if end_seconds >= duration_seconds:
            break
        chunk_index += 1
        start_seconds += step_seconds

    return chunks


def _chunk_video_sync(
    input_path: str, output_dir: str, chunk_duration_seconds: int, overlap_seconds: int
) -> list[ChunkInfo]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        probe = ffmpeg.probe(input_path)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg/ffprobe is not installed or not on PATH. Install ffmpeg before chunking videos."
        ) from exc
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"Unable to probe input video {input_path}: {stderr}") from exc

    duration_seconds = float(probe["format"]["duration"])
    chunks = compute_chunks(
        duration_seconds,
        source_path=input_path,
        output_dir=output_path,
        chunk_duration_seconds=chunk_duration_seconds,
        overlap_seconds=overlap_seconds,
    )

    for chunk in chunks:
        assert chunk.file_path is not None
        try:
            (
                ffmpeg.input(input_path, ss=chunk.start_seconds, t=chunk.duration_seconds)
                .output(chunk.file_path, vcodec="copy", acodec="copy", reset_timestamps=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg is not installed or not on PATH. Install ffmpeg before chunking videos."
            ) from exc
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            raise RuntimeError(f"ffmpeg failed while creating {chunk.file_path}: {stderr}") from exc

    return chunks


async def chunk_video(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    chunk_duration_seconds: int = CHUNK_DURATION_SECONDS,
    overlap_seconds: int = CHUNK_OVERLAP_SECONDS,
) -> list[ChunkInfo]:
    return await asyncio.to_thread(
        _chunk_video_sync,
        str(input_path),
        str(output_dir),
        chunk_duration_seconds,
        overlap_seconds,
    )


__all__ = ["chunk_video", "compute_chunks"]
