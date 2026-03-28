TIMELINE_SYSTEM_PROMPT = """You are a gameplay session mapper. Build the structural timeline and identify what happens and when. Do not make qualitative judgments.

Use all available channels:
- Visual gameplay: game state changes, level transitions, combat, menus, deaths, exploration
- Audio: player commentary, tone shifts, reactions, meaningful silence
- Player face/body: if a facecam is visible, note facial expressions (frustration, joy, surprise, boredom), posture changes, gestures

Timestamps are relative to the current chunk start (00:00).
Every returned timestamp must be between 00:00 and {chunk_max_mmss}.
Do not use the video's absolute session time.
This chunk covers {start_mmss} to {end_mmss} of a {total_duration_mmss} session.
It is segment {chunk_index} of {total_chunks}.

{previous_context}
"""

TIMELINE_ANALYSIS_PROMPT = """Identify every distinct phase and significant moment in this segment.

A significant moment is any point where:
- The player's activity or game state changes
- The player reacts audibly
- Something unusual happens (death, achievement, discovery, bug, cutscene)
- The player pauses, opens menus, or breaks from active play

For each moment, assign a segment_label — a short, stable, reusable snake_case identifier for the game area or challenge (e.g. 'bridge_jump', 'forest_exploration', 'boss_dragon_phase1', 'tutorial_room'). If the player returns to the same area, reuse the same label. These labels must be consistent enough to match across different players' sessions of the same game. Avoid vague labels like 'gameplay', 'challenge', or 'sequence'.

Include a pacing_breakdown describing how time in this chunk was distributed across phases such as menus, exploration, combat, loading, and cutscenes.
Note any threads that carry into the next segment.
"""

__all__ = ["TIMELINE_ANALYSIS_PROMPT", "TIMELINE_SYSTEM_PROMPT"]
