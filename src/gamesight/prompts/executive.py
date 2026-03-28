EXECUTIVE_SUMMARY_PROMPT = """You are writing an executive QA summary for a game development team.

Game: {game_title} ({game_genre})
Session duration: {duration_minutes:.1f} minutes
Chunks analyzed: {chunk_count}

Below is the structured analysis data from a multimodal AI analysis of this playtest session. Every finding is timestamped and evidence-backed.

Write:
1. session_health_score (0-100): 100 = flawless player experience, 50 = significant issues, 0 = unplayable
2. executive_summary: Three SHORT paragraphs:
   - Paragraph 1: What happened in this session (factual overview)
   - Paragraph 2: The critical issues that need immediate attention
   - Paragraph 3: The strengths that should be protected and expanded
3. key_findings (3-5): Prioritized findings. Each MUST cite specific timestamps and evidence from the data below. Prioritize findings that CROSS analysis dimensions — e.g., a clarity issue at one timestamp that causes friction nearby that triggers a retry loop and quit signal.
4. priority_actions: Ranked list of what the dev team should do, most urgent first. Be concrete: "add checkpoint before bridge" not "improve difficulty curve."
5. cross_dimensional_insight: One NON-OBVIOUS pattern connecting multiple analysis dimensions. Example: "Players who expressed delight at the combat system at 12:30 showed higher tolerance for the bridge failures at 15:00, suggesting combat satisfaction acts as a frustration buffer."

Rules:
- Every claim must reference timestamps from the data
- Prioritize by player impact, not by frequency
- Be direct. No hedging. No filler.
- If retry data shows repeated failures, cite the attempt counts
- If sentiment data shows a pattern, cite the average scores

Analysis data:
{report_json}
"""

__all__ = ["EXECUTIVE_SUMMARY_PROMPT"]
