SENTIMENT_AGENT_PROMPT = """Analyze this chunk for player EMOTIONAL SENTIMENT, producing a quantified sentiment curve.

The full session timeline and all previous specialist findings are attached as context.
Use them for continuity and pattern detection, but cite evidence only from the current chunk.

Sample the player's emotional state at roughly 20-30 second intervals throughout the chunk. For each sample, observe all three evidence channels simultaneously:
- VISUAL GAMEPLAY: success, failure, discovery, stalling, progress, death
- AUDIO: player voice tone, volume, word choice, breathing, laughter, sighs, silence
- FACECAM (if visible): facial expression, posture shifts, gestures, eye movement

Score sentiment from -10 to +10:
  -10 to -7: Active frustration — cursing, head in hands, threatening to quit, rage
  -6 to -4: Negative — struggling, losing patience, confused and annoyed
  -3 to -1: Mildly negative — minor setbacks, slight annoyance
  0: Neutral — focused, engaged, neither positive nor negative
  +1 to +3: Mildly positive — steady progress, mild satisfaction
  +4 to +6: Positive — enjoying the experience, voluntary exploration, smiling
  +7 to +10: Peak positive — laughing, celebrating, exclaiming, fist pump, triumph

Critical distinctions:
- A player who dies but laughs and retries is POSITIVE (+2 to +4), not negative
- Focused silence during intense gameplay is NEUTRAL (0) or POSITIVE (+1 to +2), not negative
- Resigned silence after repeated failure is NEGATIVE (-3 to -6)
- Idle menu browsing with no engagement signals is NEUTRAL to NEGATIVE (-1 to -2)

When the player is silent, classify the silence type to justify your sentiment score.
Be precise and evidence-based. Do not inflate or deflate scores without observable evidence.
"""

__all__ = ["SENTIMENT_AGENT_PROMPT"]
