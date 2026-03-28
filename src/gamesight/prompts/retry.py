RETRY_AGENT_PROMPT = """Analyze this chunk for RETRY PATTERNS — moments where the player attempts the same challenge multiple times.

The full session timeline and all previous specialist findings are attached as context.
Use them for continuity and pattern detection, but cite evidence only from the current chunk.

A retry sequence is any situation where:
- The player dies and respawns at the same checkpoint or area
- The player fails a jump, puzzle, or combat encounter and tries it again
- The player's character is returned to a previous position after failing
- The player manually reloads a save or restarts a section

For each retry sequence:
1. Name the challenge using a short snake_case label matching segment_label names from the timeline context (e.g. 'bridge_jump', 'boss_phase_2')
2. Number each individual attempt sequentially
3. Track the duration and outcome of each attempt
4. Note whether the player changes strategy between attempts
5. Observe how frustration evolves across attempts (watch facial expressions, voice tone, body language)
6. Record whether the player shows quit signals (pausing for long periods, sighing, saying they want to stop, checking phone)

Also count total deaths or failures even if they don't form multi-attempt retry sequences. Track first-attempt successes separately — a section cleared on the first try is valuable data about good difficulty tuning.

A single death with immediate success on retry is minor. Three or more attempts at the same obstacle is a critical game design signal. Flag quit_signal=true only when evidence clearly suggests the player is considering stopping entirely.
"""

__all__ = ["RETRY_AGENT_PROMPT"]
