"""LLM-powered executive summary generation.

Single text-only Gemini call that synthesizes the complete VideoReport
into a narrative executive summary with session health score and key findings.
"""

import google.genai as genai

from gamesight.config import HEALTH_SCORE_MAX, HEALTH_SCORE_MIN, clamp
from gamesight.gemini.generate import generate_structured
from gamesight.prompts.executive import EXECUTIVE_SUMMARY_PROMPT
from gamesight.schemas.executive import ExecutiveSummary
from gamesight.schemas.report import VideoReport


async def generate_executive_summary(
    client: genai.Client,
    report: VideoReport,
    game_genre: str,
) -> ExecutiveSummary:
    prompt = EXECUTIVE_SUMMARY_PROMPT.format(
        game_title=report.game_title,
        game_genre=game_genre,
        duration_minutes=report.duration_seconds / 60.0,
        chunk_count=report.chunk_count,
        report_json=report.model_dump_json(),
    )
    result = await generate_structured(
        client,
        contents=prompt,
        response_schema=ExecutiveSummary,
        thinking_level="medium",
    )
    clamped_score = int(clamp(result.session_health_score, HEALTH_SCORE_MIN, HEALTH_SCORE_MAX))
    if clamped_score != result.session_health_score:
        result = result.model_copy(update={"session_health_score": clamped_score})
    return result


__all__ = ["generate_executive_summary"]
