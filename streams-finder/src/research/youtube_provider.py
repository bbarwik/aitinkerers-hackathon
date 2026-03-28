import logging
import os
from datetime import datetime, timezone

import httpx
import yt_dlp

from .models import DiscoveredVideo, Platform

logger = logging.getLogger(__name__)

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeProvider:
    """YouTube video search. Tries yt-dlp first, falls back to YouTube Data API v3."""

    def __init__(self, *, results_per_query: int = 10, cookies_path: str | None = None) -> None:
        self.results_per_query = results_per_query
        self.cookies_path = cookies_path
        self.youtube_api_key = os.environ.get("YOUTUBE_API_KEY")

        self.ydl_opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ignoreerrors": "only_download",
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        if cookies_path and os.path.isfile(cookies_path):
            self.ydl_opts["cookiefile"] = cookies_path
            logger.info("YouTube cookies loaded from %s", cookies_path)

    def search(self, queries: list[str]) -> list[DiscoveredVideo]:
        """Search YouTube for each query. Synchronous — caller wraps in asyncio.to_thread()."""
        videos: list[DiscoveredVideo] = []
        seen_ids: set[str] = set()
        ytdlp_failed = False

        for query in queries:
            results: list[DiscoveredVideo] = []
            if not ytdlp_failed:
                try:
                    results = self._search_ytdlp(query)
                except Exception as e:
                    err_msg = str(e)
                    if "Sign in to confirm" in err_msg or "bot" in err_msg.lower():
                        logger.warning("yt-dlp bot detection hit, switching to YouTube Data API for remaining queries")
                        ytdlp_failed = True
                    else:
                        logger.warning("yt-dlp search failed for query '%s': %s", query, e)

            if not results and self.youtube_api_key:
                try:
                    results = self._search_api(query)
                except Exception as e:
                    logger.warning("YouTube API search failed for query '%s': %s", query, e)

            if not results:
                logger.warning("No results for query '%s' from any source", query)

            for video in results:
                if video.video_id not in seen_ids:
                    seen_ids.add(video.video_id)
                    videos.append(video)

        return videos

    # --- yt-dlp search ---

    def _search_ytdlp(self, query: str) -> list[DiscoveredVideo]:
        search_url = f"ytsearch{self.results_per_query}:{query}"
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)

        entries = (info or {}).get("entries") or []
        return [v for entry in entries if entry and (v := self._normalize_ytdlp(entry, query))]

    def _normalize_ytdlp(self, entry: dict, source_query: str) -> DiscoveredVideo | None:
        video_id = entry.get("id")
        title = entry.get("title")
        if not video_id or not title:
            return None

        published_at = None
        upload_date = entry.get("upload_date")
        if upload_date and len(upload_date) == 8:
            try:
                published_at = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        duration = entry.get("duration")
        view_count = entry.get("view_count")

        return DiscoveredVideo(
            platform=Platform.YOUTUBE,
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
            channel_name=entry.get("uploader"),
            description=(entry.get("description") or "")[:500] or None,
            duration_seconds=int(duration) if duration else None,
            view_count=int(view_count) if view_count else None,
            published_at=published_at,
            thumbnail_url=entry.get("thumbnail"),
            source_query=source_query,
        )

    # --- YouTube Data API v3 fallback ---

    def _search_api(self, query: str) -> list[DiscoveredVideo]:
        """Search via YouTube Data API v3. Costs 100 quota units per call."""
        # Step 1: search for video IDs
        search_resp = httpx.get(
            f"{YOUTUBE_API_URL}/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(self.results_per_query, 50),
                "key": self.youtube_api_key,
            },
            timeout=15,
        )
        search_resp.raise_for_status()
        items = search_resp.json().get("items") or []

        if not items:
            return []

        # Step 2: get video details (duration, view count) — costs 1 unit
        video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        details_map: dict[str, dict] = {}
        if video_ids:
            details_resp = httpx.get(
                f"{YOUTUBE_API_URL}/videos",
                params={
                    "part": "contentDetails,statistics",
                    "id": ",".join(video_ids),
                    "key": self.youtube_api_key,
                },
                timeout=15,
            )
            details_resp.raise_for_status()
            for d in details_resp.json().get("items") or []:
                details_map[d["id"]] = d

        videos: list[DiscoveredVideo] = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            details = details_map.get(video_id, {})

            videos.append(
                DiscoveredVideo(
                    platform=Platform.YOUTUBE,
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=snippet.get("title", ""),
                    channel_name=snippet.get("channelTitle"),
                    description=(snippet.get("description") or "")[:500] or None,
                    duration_seconds=_parse_iso_duration(details.get("contentDetails", {}).get("duration")),
                    view_count=_parse_int(details.get("statistics", {}).get("viewCount")),
                    published_at=_parse_iso_datetime(snippet.get("publishedAt")),
                    thumbnail_url=snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                    source_query=query,
                )
            )

        return videos


def _parse_iso_duration(duration: str | None) -> int | None:
    """Parse ISO 8601 duration like PT1H23M45S into seconds."""
    if not duration:
        return None
    import re

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return None
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def _parse_int(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_iso_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None
