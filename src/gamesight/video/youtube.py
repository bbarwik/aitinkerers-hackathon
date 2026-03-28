from urllib.parse import parse_qs, urlparse

import asyncio
import yt_dlp
from pydantic import BaseModel, ConfigDict


class YouTubeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: str
    title: str
    uploader: str | None
    duration_seconds: float
    url: str


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def extract_youtube_video_id(url: str) -> str:
    if not is_youtube_url(url):
        raise ValueError("youtube_url must be a valid YouTube watch or share URL.")
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id
    query_video_id = parse_qs(parsed.query).get("v", [])
    if query_video_id and query_video_id[0]:
        return query_video_id[0]
    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts[:1] in (["shorts"], ["live"]) and len(path_parts) >= 2:
        return path_parts[1]
    raise ValueError(
        "Could not extract a YouTube video ID from the provided URL. "
        "Use a standard watch, share, shorts, or live YouTube URL."
    )


def _extract_metadata_sync(url: str) -> YouTubeMetadata:
    if not is_youtube_url(url):
        raise ValueError("youtube_url must be a valid YouTube watch or share URL.")
    with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as downloader:
        info = downloader.extract_info(url, download=False)
    duration_seconds = float(info.get("duration") or 0)
    if duration_seconds <= 0:
        raise ValueError("yt-dlp could not determine the YouTube video duration.")
    return YouTubeMetadata(
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or "Unknown YouTube Video"),
        uploader=info.get("uploader"),
        duration_seconds=duration_seconds,
        url=url,
    )


async def fetch_youtube_metadata(url: str) -> YouTubeMetadata:
    return await asyncio.to_thread(_extract_metadata_sync, url)


async def resolve_youtube_metadata(
    url: str,
    *,
    duration_seconds_override: float | None,
) -> YouTubeMetadata:
    override_duration = duration_seconds_override
    metadata: YouTubeMetadata | None = None

    try:
        metadata = await fetch_youtube_metadata(url)
    except Exception as exc:
        if override_duration is None:
            raise RuntimeError(
                "Could not determine YouTube duration. "
                "Pass duration_seconds explicitly or make sure yt-dlp can read the video metadata."
            ) from exc

    if metadata is None:
        video_id = extract_youtube_video_id(url)
        if override_duration is None:
            raise RuntimeError(
                "Could not determine YouTube duration. Pass duration_seconds explicitly or make sure yt-dlp can read the video metadata."
            )
        return YouTubeMetadata(
            video_id=video_id,
            title="Unknown YouTube Video",
            uploader=None,
            duration_seconds=override_duration,
            url=url,
        )

    if override_duration is not None:
        return metadata.model_copy(update={"duration_seconds": override_duration})
    return metadata


__all__ = [
    "YouTubeMetadata",
    "extract_youtube_video_id",
    "fetch_youtube_metadata",
    "is_youtube_url",
    "resolve_youtube_metadata",
]
