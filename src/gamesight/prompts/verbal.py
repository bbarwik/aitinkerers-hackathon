VERBAL_AGENT_PROMPT = """Extract and classify ALL notable verbal feedback from the player in this chunk.

The full session timeline and all previous specialist findings are attached as context.
Use them for continuity and pattern detection, but cite evidence only from the current chunk.

Listen carefully for:
- COMPLAINTS about game mechanics, difficulty, controls, or design
- PRAISE for features, visuals, mechanics, or moments
- QUESTIONS revealing confusion ("where do I go?", "what does this do?")
- STRATEGY NARRATION ("let me try jumping from the left", "maybe if I use the shield...")
- SUGGESTIONS for improvement ("they should add a checkpoint here")
- EMOTIONAL REACTIONS — exclamations, laughter, sighs, cursing, gasps
- SOCIAL comments directed at stream or friends about the game experience

For each verbal moment:
- Capture the exact quote as closely as possible
- Note the voice tone (angry, frustrated, confused, neutral, amused, excited, sarcastic, resigned)
- Rate sentiment from -5 (very negative) to +5 (very positive)
- State the gameplay context
- Flag quotes that are actionable for designers — where the player's words directly imply a design change
- If actionable, write one concise actionable_insight

Ignore NPC dialogue, soundtrack lyrics, and non-player speech unless the player directly responds to it.
If no player speech is audible in the entire chunk, set has_player_audio=false and return an empty moments list.
"""

__all__ = ["VERBAL_AGENT_PROMPT"]
