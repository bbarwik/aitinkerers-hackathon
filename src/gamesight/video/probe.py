from fractions import Fraction
from pathlib import Path

import asyncio
import ffmpeg
from pydantic import BaseModel, ConfigDict


class VideoProbeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    duration_seconds: float
    width: int
    height: int
    codec: str | None
    fps: float | None
    audio_codec: str | None
    file_size_bytes: int


def _probe_sync(input_path: str) -> VideoProbeResult:
    try:
        probe = ffmpeg.probe(input_path)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffprobe is not installed or not on PATH. Install ffmpeg/ffprobe before running analysis."
        ) from exc
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"ffprobe failed for {input_path}: {stderr}") from exc

    fmt = probe["format"]
    video_stream = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    fps = None
    if video_stream and video_stream.get("r_frame_rate"):
        try:
            fps = float(Fraction(video_stream["r_frame_rate"]))
        except (ValueError, ZeroDivisionError):
            fps = None

    return VideoProbeResult(
        duration_seconds=float(fmt["duration"]),
        width=int(video_stream["width"]) if video_stream else 0,
        height=int(video_stream["height"]) if video_stream else 0,
        codec=video_stream.get("codec_name") if video_stream else None,
        fps=fps,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        file_size_bytes=int(fmt.get("size", 0)),
    )


async def probe_video(input_path: str | Path) -> VideoProbeResult:
    return await asyncio.to_thread(_probe_sync, str(input_path))


__all__ = ["VideoProbeResult", "probe_video"]
