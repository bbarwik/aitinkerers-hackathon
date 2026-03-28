import logging
import re
from datetime import datetime

import httpx

from .models import DiscoveredVideo, Platform

logger = logging.getLogger(__name__)

DURATION_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def parse_twitch_duration(duration_str: str) -> int | None:
    """Parse Twitch duration format like '3h8m33s', '45m12s', '30s' into seconds."""
    match = DURATION_RE.fullmatch(duration_str)
    if not match or not any(match.groups()):
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


class TwitchProvider:
    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.twitch.tv/helix"
        self.token_url = "https://id.twitch.tv/oauth2/token"
        self._access_token: str | None = None

    async def search(self, game_name: str) -> list[DiscoveredVideo]:
        """Search Twitch for VODs of a game. Returns empty list on any error (non-fatal)."""
        try:
            return await self._search_impl(game_name)
        except Exception as e:
            logger.warning("Twitch search failed for '%s': %s", game_name, e)
            return []

    async def _search_impl(self, game_name: str) -> list[DiscoveredVideo]:
        async with httpx.AsyncClient(timeout=15.0) as http:
            token = await self._get_token(http)
            headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {token}"}

            # Step 1: resolve game name to game_id
            game_id = await self._resolve_game(http, headers, game_name)
            if not game_id:
                logger.info("Game '%s' not found on Twitch", game_name)
                return []

            # Step 2: fetch VODs sorted by time (most recent first)
            resp = await http.get(
                f"{self.base_url}/videos",
                headers=headers,
                params={"game_id": game_id, "type": "archive", "sort": "time", "first": "100"},
            )
            resp.raise_for_status()
            vods = resp.json().get("data") or []

            return [v for entry in vods if (v := self._normalize_vod(entry, game_name))]

    async def _resolve_game(self, http: httpx.AsyncClient, headers: dict, game_name: str) -> str | None:
        resp = await http.get(f"{self.base_url}/search/categories", headers=headers, params={"query": game_name, "first": "5"})
        resp.raise_for_status()
        categories = resp.json().get("data") or []

        for cat in categories:
            if cat.get("name", "").casefold() == game_name.casefold():
                return cat["id"]

        # No exact match — use first result if available
        return categories[0]["id"] if categories else None

    async def _get_token(self, http: httpx.AsyncClient) -> str:
        if self._access_token:
            return self._access_token

        resp = await http.post(
            self.token_url,
            params={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _normalize_vod(self, vod: dict, game_name: str) -> DiscoveredVideo | None:
        vod_id = vod.get("id")
        title = vod.get("title")
        if not vod_id or not title:
            return None

        published_at = None
        created_at = vod.get("created_at")
        if created_at:
            try:
                published_at = datetime.fromisoformat(created_at)
            except ValueError:
                pass

        thumbnail = vod.get("thumbnail_url") or ""
        thumbnail = thumbnail.replace("%{width}", "320").replace("%{height}", "180") if thumbnail else None

        return DiscoveredVideo(
            platform=Platform.TWITCH,
            video_id=vod_id,
            url=vod.get("url") or f"https://www.twitch.tv/videos/{vod_id}",
            title=title,
            channel_name=vod.get("user_name"),
            description=(vod.get("description") or "")[:500] or None,
            duration_seconds=parse_twitch_duration(vod.get("duration") or ""),
            view_count=vod.get("view_count"),
            published_at=published_at,
            thumbnail_url=thumbnail,
            source_query=f"twitch:{game_name}",
        )
