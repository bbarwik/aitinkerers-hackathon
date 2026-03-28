import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

CONTEXT_PROMPT = """Research the video game '{game_name}'.

Provide a comprehensive but concise overview:
- Genre, sub-genre, gameplay style
- Developer and publisher
- Platforms and release date
- Key features and mechanics
- Any DLC, expansions, major updates
- Notable bosses, levels, characters, locations
- Popular community terms, slang, abbreviations
- Current state of the game (active updates? competitive scene? speedrun community?)

This context will be used to generate smart YouTube search queries for finding gameplay videos."""

QUERY_PROMPT = """Based on this game context:

{game_context}

Generate {num_queries} diverse YouTube search queries for finding videos of people ACTUALLY PLAYING "{game_name}".
The primary goal is streams, playthroughs, and let's plays — real gameplay with or without commentary.

Target content types (in priority order):
- Streams: stream VODs, live gameplay, archived broadcasts, streaming highlights
- Gameplay: full playthroughs, walkthroughs, boss fights, challenge runs, speedruns
- Commentary: let's plays, blind/first-time reactions, commentary playthroughs
- Reviews: game reviews, first impressions (secondary — include 1 query max)

Requirements:
- Use concrete game terms from the context: bosses, modes, DLC names, locations, community slang.
- Include intent words: gameplay, playthrough, walkthrough, let's play, stream, VOD, live, full game.
- Prefer queries that surface full-length videos (30min+), not clips.

Coverage:
- At least 3 gameplay / playthrough / stream / VOD queries
- At least 1 let's play or blind playthrough query
- At least 1 query using a specific in-game term (boss name, DLC, mode) + gameplay intent
- At most 1 review query

DO NOT generate queries for: trailers, compilations, music/OST, news, patch notes, tier lists, YouTube Shorts, lore/theory videos, or "top 10" lists."""


class QueryGenerator:
    def __init__(self, *, client: genai.Client, model: str = "gemini-3-flash-preview") -> None:
        self.client = client
        self.model = model

    async def build_game_context(self, game_name: str) -> str:
        """Step 1: Use Gemini with Google Search grounding to build rich game context (free text)."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=CONTEXT_PROMPT.format(game_name=game_name),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            return response.text or f"{game_name} is a video game."
        except Exception as e:
            logger.warning("Game context generation failed for '%s': %s", game_name, e)
            return f"{game_name} is a video game."

    async def generate_queries(self, game_name: str, game_context: str, num_queries: int = 6) -> list[str]:
        """Step 2: Use Gemini with structured output (no tools) to generate search queries."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=QUERY_PROMPT.format(game_name=game_name, game_context=game_context, num_queries=num_queries),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[str],
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            queries = response.parsed
            if queries is None:
                queries = json.loads(response.text)

            # Normalize: strip, dedupe case-insensitively, drop empties
            seen: set[str] = set()
            result: list[str] = []
            for q in queries:
                q = q.strip()
                if q and q.casefold() not in seen:
                    seen.add(q.casefold())
                    result.append(q)
            return result or [f"{game_name} gameplay"]

        except Exception as e:
            logger.warning("Query generation failed for '%s': %s", game_name, e)
            return [f"{game_name} gameplay"]

    async def generate(self, game_name: str) -> tuple[str, list[str]]:
        """Run both steps: build context, then generate queries."""
        game_context = await self.build_game_context(game_name)
        queries = await self.generate_queries(game_name, game_context)
        return game_context, queries
