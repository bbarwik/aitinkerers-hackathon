WARMUP_PROMPT_TEMPLATE = """Review this gameplay segment together with the session context below.

Game: {game_title} ({game_genre})
Session context for this segment:
{timeline_context}

Reply with four short bullets:
- current gameplay situation
- whether player speech is present
- what looks most important to watch for
- whether any prior issue continues here

Do not perform specialized analysis yet.
"""

__all__ = ["WARMUP_PROMPT_TEMPLATE"]
