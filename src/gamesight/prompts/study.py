STUDY_SYNTHESIS_PROMPT = """You are analyzing aggregated playtest data from {session_count} gameplay sessions of {game_title}.

Your job: find 3-5 NON-OBVIOUS patterns that would be invisible from watching any single session.

Focus on:
- Recurring difficulty spikes that disproportionately cause session abandonment
- Churn tipping points: how many retries before most players quit?
- Mechanics or segments that players consistently praise across sessions
- Surprising tradeoffs: a beloved mechanic offsetting nearby frustration
- Comparisons between key segments (e.g., bridge vs combat, puzzle vs exploration)
- Correlations between positive features and player retention behavior

Rules:
- Every insight MUST cite specific statistics (percentages, session counts, averages) from the data below
- Reject weak or low-support patterns — only include patterns supported by 3+ sessions
- Prefer patterns that no one would see by watching a single session
- Turn the strongest patterns into concrete recommended_action lines

Aggregated study data:
{study_json}
"""

__all__ = ["STUDY_SYNTHESIS_PROMPT"]
