import logging
from datetime import datetime, timezone

import yt_dlp

from .models import DiscoveredVideo, Platform

logger = logging.getLogger(__name__)


class YouTubeProvider:
    def __init__(self, *, results_per_query: int = 10) -> None:
        self.results_per_query = results_per_query
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ignoreerrors": "only_download",
        }

    def search(self, queries: list[str]) -> list[DiscoveredVideo]:
        """Search YouTube for each query via yt-dlp. Synchronous — caller wraps in asyncio.to_thread()."""
        videos: list[DiscoveredVideo] = []
        seen_ids: set[str] = set()

        for query in queries:
            try:
                results = self._search_query(query)
                for video in results:
                    if video.video_id not in seen_ids:
                        seen_ids.add(video.video_id)
                        videos.append(video)
            except Exception as e:
                logger.warning("YouTube search failed for query '%s': %s", query, e)

        return videos

    def _search_query(self, query: str) -> list[DiscoveredVideo]:
        search_url = f"ytsearch{self.results_per_query}:{query}"
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)

        entries = (info or {}).get("entries") or []
        videos: list[DiscoveredVideo] = []

        for entry in entries:
            if not entry:
                continue
            video = self._normalize_entry(entry, query)
            if video:
                videos.append(video)

        return videos

    def _normalize_entry(self, entry: dict, source_query: str) -> DiscoveredVideo | None:
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
