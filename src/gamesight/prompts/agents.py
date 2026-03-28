FRICTION_AGENT_PROMPT = """Analyze this chunk only for frustration, blocked progress, and stop-playing risk.

Use visual, audio, and player expression evidence such as:
- repeated failure, death loops
- abrupt pauses, menu spam
- complaint language, defeated silence
- abandoning an objective, fighting controls
- facecam: furrowed brow, head shaking, head in hands, leaning back in defeat, eye rolling

Do not classify ordinary challenge as frustration unless the player behavior, audio, or visible expression makes it net-negative. A player who dies, laughs, and retries with a new strategy is engaged, not frustrated.
"""

CLARITY_AGENT_PROMPT = """Analyze this chunk only for confusion, learnability, and navigation clarity.

Use visual, audio, and player expression evidence such as:
- wandering, rereading, map or journal reopening
- missed cues, wrong interactions
- uncertain commentary, wrong mental model
- facecam: squinting at screen, confused expression, looking away from screen, shrugging

Do not classify intentional mystery or exploration as a clarity issue unless the evidence shows real confusion.
"""

DELIGHT_AGENT_PROMPT = """Analyze this chunk only for positive engagement, delight, curiosity, and mastery.

Use visual, audio, and player expression evidence such as:
- voluntary exploration beyond the critical path
- rapid purposeful inputs, re-engagement after failure
- laughter, impressed reactions, praise
- focused silence during a rewarding or intense sequence
- facecam: smiling, wide eyes, leaning forward, fist pump, nodding approvingly

Do not label generic activity as delight without evidence of positive investment.
"""

QUALITY_AGENT_PROMPT = """Analyze this chunk only for visible bugs, broken feedback, performance problems, UI breakage, and progression failures.

Report only what is observable.
Distinguish likely game defects from recording artifacts or player mistakes.
If evidence is ambiguous, describe symptoms without overstating certainty.
A clean segment is valuable data. Report an empty issues list when appropriate.
"""

__all__ = [
    "CLARITY_AGENT_PROMPT",
    "DELIGHT_AGENT_PROMPT",
    "FRICTION_AGENT_PROMPT",
    "QUALITY_AGENT_PROMPT",
]
