import asyncio
import logging
import re
from collections import Counter
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone

from .models import DiscoveredVideo, DiscoveryResult
from .query_generator import QueryGenerator
from .twitch_provider import TwitchProvider
from .youtube_provider import YouTubeProvider

logger = logging.getLogger(__name__)

EXCLUDE_TITLE_PATTERN = re.compile(r"\b(compilation|montage|trailer|teaser|shorts|soundtrack|cinematic)\b", re.IGNORECASE)

# Type alias for progress callback: async function that takes a status message
ProgressCallback = Callable[[str], Coroutine]


class ResearchDiscoverer:
    def __init__(
        self,
        *,
        query_generator: QueryGenerator,
        youtube: YouTubeProvider,
        twitch: TwitchProvider | None = None,
        min_duration: int = 600,
        max_duration: int = 7200,
        popular_limit: int = 10,
        recent_limit: int = 10,
    ) -> None:
        self.query_generator = query_generator
        self.youtube = youtube
        self.twitch = twitch
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.popular_limit = popular_limit
        self.recent_limit = recent_limit
        self._cache: dict[str, DiscoveryResult] = {}

    async def discover(
        self,
        game_name: str,
        *,
        refresh: bool = False,
        period: str = "month",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DiscoveryResult:
        async def progress(msg: str) -> None:
            logger.info(msg)
            if on_progress:
                await on_progress(msg)

        # Resolve effective date range — custom dates override period
        if date_from or date_to:
            eff_from = date_from
            eff_to = date_to
            twitch_period = "all"
        else:
            eff_from = self._period_cutoff(period)
            eff_to = None
            twitch_period = period

        cache_key = game_name.strip().casefold()
        if not refresh and cache_key in self._cache:
            await progress(f"Cache hit for '{game_name}'")
            result = self._cache[cache_key]
            return result.model_copy(update={"cached": True})

        warnings: list[str] = []
        partial = False

        # Step 1: Gemini builds game context with Google Search grounding
        await progress(f"Researching '{game_name}' with Gemini + Google Search...")
        try:
            game_context, queries = await self.query_generator.generate(game_name)
            # Always include the plain game name — platforms have good search engines
            if game_name.casefold() not in {q.casefold() for q in queries}:
                queries.insert(0, game_name)
            await progress(f"Generated {len(queries)} search queries: {queries}")
        except Exception as e:
            logger.warning("Query generation failed entirely for '%s': %s", game_name, e)
            game_context = ""
            queries = [game_name, f"{game_name} gameplay"]
            partial = True
            warnings.append(f"Query generation failed: {e}")
            await progress("Query generation failed, using fallback query")

        # Step 2: YouTube + Twitch in parallel
        sources = ["YouTube"]
        if self.twitch:
            sources.append("Twitch")
        await progress(f"Searching {' + '.join(sources)} in parallel...")

        tasks: list[asyncio.Task] = []
        tasks.append(asyncio.create_task(asyncio.to_thread(self.youtube.search, queries, eff_from, eff_to)))
        if self.twitch:
            tasks.append(asyncio.create_task(self.twitch.search(game_name, period=twitch_period)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process YouTube result
        yt_videos: list[DiscoveredVideo] = []
        if isinstance(results[0], BaseException):
            logger.warning("YouTube search failed: %s", results[0])
            warnings.append(f"YouTube search failed: {results[0]}")
            partial = True
            await progress(f"YouTube search failed: {results[0]}")
        else:
            yt_videos = results[0]
            await progress(f"YouTube: found {len(yt_videos)} videos")

        # Process Twitch result
        twitch_videos: list[DiscoveredVideo] = []
        if self.twitch and len(results) > 1:
            if isinstance(results[1], BaseException):
                logger.warning("Twitch search failed: %s", results[1])
                warnings.append(f"Twitch search failed: {results[1]}")
                partial = True
                await progress(f"Twitch search failed: {results[1]}")
            else:
                twitch_videos = results[1]
                await progress(f"Twitch: found {len(twitch_videos)} VODs")

        all_videos = yt_videos + twitch_videos
        if not all_videos and partial:
            raise RuntimeError(f"All discovery sources failed for '{game_name}'")

        # Dedupe, filter, rank
        await progress(f"Processing {len(all_videos)} total candidates...")
        deduped = self._deduplicate(all_videos)
        filtered = self._filter(deduped, date_from=eff_from, date_to=eff_to)
        await progress(f"After filtering: {len(filtered)} videos (from {len(deduped)} unique)")

        popular = sorted(filtered, key=lambda v: v.view_count or 0, reverse=True)[: self.popular_limit]
        recent = sorted(filtered, key=lambda v: v.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[: self.recent_limit]

        source_counts = Counter(v.platform.value for v in filtered)

        result = DiscoveryResult(
            game_name=game_name,
            game_context=game_context,
            queries=queries,
            total_found=len(filtered),
            popular=popular,
            recent=recent,
            source_breakdown=dict(source_counts),
            partial=partial,
            warnings=warnings,
            generated_at=datetime.now(timezone.utc),
        )

        self._cache[cache_key] = result
        await progress(f"Done! {len(popular)} popular + {len(recent)} recent videos")
        return result

    def _deduplicate(self, videos: list[DiscoveredVideo]) -> list[DiscoveredVideo]:
        seen: set[tuple[str, str]] = set()
        result: list[DiscoveredVideo] = []
        for v in videos:
            key = (v.platform.value, v.video_id)
            if key not in seen:
                seen.add(key)
                result.append(v)
        return result

    def _filter(
        self, videos: list[DiscoveredVideo], date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> list[DiscoveredVideo]:
        result: list[DiscoveredVideo] = []
        for v in videos:
            if v.duration_seconds is not None and not (self.min_duration <= v.duration_seconds <= self.max_duration):
                continue
            if EXCLUDE_TITLE_PATTERN.search(v.title):
                continue
            if date_from and v.published_at and v.published_at < date_from:
                continue
            if date_to and v.published_at and v.published_at > date_to:
                continue
            result.append(v)
        return result

    @staticmethod
    def _period_cutoff(period: str) -> datetime | None:
        if period == "all":
            return None
        deltas = {"day": timedelta(days=1), "week": timedelta(weeks=1), "month": timedelta(days=30)}
        delta = deltas.get(period)
        return datetime.now(timezone.utc) - delta if delta else None
