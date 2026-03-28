import asyncio
import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .models import DiscoveredVideo

logger = logging.getLogger(__name__)

BATCH_SIZE = 100

VERIFY_PROMPT = """You are classifying candidate videos for a game video discovery tool.
The tool's primary goal is to find videos where people are ACTUALLY PLAYING the game — streams, playthroughs, let's plays with commentary. Reviews are acceptable but secondary.

Game: {game_name}

For each candidate, decide whether to KEEP or REJECT it.

KEEP — content types in priority order (assign the best match):
- "stream" — stream VODs, live stream recordings, archived broadcasts of someone playing the game
- "gameplay" — full playthroughs, walkthroughs, boss fights, speedruns, challenge runs, someone actually playing
- "commentary" — let's plays with commentary, reaction playthroughs, blind/first-time playthroughs
- "review" — game reviews, critiques, first impressions (lower priority but still keep)

REJECT (verdict = "reject", content_type = "rejected"):
- Trailers, teasers, cinematics, official announcements
- Compilations, montages, highlight reels, meme edits
- Music, soundtracks, OST, ambient music
- News, patch notes, update summaries, developer interviews
- Tier lists, rankings, "top 10" lists, "things you didn't know"
- Lore videos, theory/speculation, story explainers without gameplay
- YouTube Shorts or clips under 60 seconds
- Content not about this specific game
- Videos that only TALK ABOUT the game without showing real gameplay (e.g. talking head analysis, podcast discussions)

Rules:
- The key question is: does this video show someone actually playing the game?
- Twitch VODs are almost always real gameplay — classify as "stream".
- Long duration (>30 min) + gaming channel = likely real gameplay even if title is vague.
- "Review" that shows actual gameplay footage = "review" (keep).
- "Review" that is just talking head with no gameplay = reject.
- Ambiguous → KEEP (false negatives are worse than false positives).
- Content may be in any language.

Videos to classify:
{videos_json}

Classify every video. Return one entry per video."""


class VideoVerdict(BaseModel):
    video_id: str
    platform: str
    verdict: str = Field(description="keep or reject")
    content_type: str = Field(description="gameplay, review, stream, commentary, or rejected")
    reason: str = Field(description="Brief reason, max 20 words")


class VerificationResponse(BaseModel):
    classifications: list[VideoVerdict]


class VideoVerifier:
    def __init__(self, *, client: genai.Client, model: str = "gemini-3-flash-preview") -> None:
        self.client = client
        self.model = model

    async def verify_batch(self, game_name: str, videos: list[DiscoveredVideo]) -> list[DiscoveredVideo]:
        """Classify videos via Gemini and return only those marked 'keep', with content_type set."""
        if not videos:
            return []

        batches = [videos[i : i + BATCH_SIZE] for i in range(0, len(videos), BATCH_SIZE)]
        results = await asyncio.gather(
            *(self._verify_single_batch(game_name, batch) for batch in batches),
            return_exceptions=True,
        )

        verdicts: dict[tuple[str, str], VideoVerdict] = {}
        any_success = False
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("Verification batch failed: %s", result)
                continue
            any_success = True
            for v in result:
                verdicts[(v.platform, v.video_id)] = v

        if not any_success:
            logger.warning("All verification batches failed — keeping all %d videos", len(videos))
            return videos

        kept: list[DiscoveredVideo] = []
        for video in videos:
            key = (video.platform.value, video.video_id)
            verdict = verdicts.get(key)
            if verdict is None:
                video.content_type = "unknown"
                kept.append(video)
            elif verdict.verdict == "keep":
                video.content_type = verdict.content_type
                kept.append(video)

        # Safety valve: if everything rejected, likely a classification bug
        if not kept and videos:
            logger.warning("Gemini rejected ALL %d videos — keeping all as fallback", len(videos))
            return videos

        return kept

    async def _verify_single_batch(self, game_name: str, videos: list[DiscoveredVideo]) -> list[VideoVerdict]:
        videos_json = json.dumps(
            [
                {
                    "video_id": v.video_id,
                    "platform": v.platform.value,
                    "title": v.title,
                    "channel_name": v.channel_name or "(unknown)",
                    "description": (v.description or "(no description)")[:300],
                    "duration_seconds": v.duration_seconds,
                }
                for v in videos
            ],
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=VERIFY_PROMPT.format(game_name=game_name, videos_json=videos_json),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VerificationResponse,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )

        parsed = response.parsed
        if parsed is None:
            parsed = VerificationResponse.model_validate_json(response.text)

        return parsed.classifications
