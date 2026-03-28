from urllib.parse import urlparse

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


__all__ = ["YouTubeMetadata", "fetch_youtube_metadata", "is_youtube_url"]
