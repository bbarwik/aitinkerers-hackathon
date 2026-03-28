# FINAL IMPLEMENTATION PLAN

## Conflict Resolution Summary

| Disagreement | Decision | Rationale |
|---|---|---|
| **EvidencePacket on all schemas** (GPT-5) vs. **leave existing schemas alone** (Opus) | **Leave existing schemas alone.** Add `confidence_score` and `corroborating_agents` on `CanonicalMoment` via post-processing. | Existing schemas already have `scene_description`, `verbal_feedback`, `visual_signals`, `audio_signals`. Modifying 4 working LLM output schemas risks validation failures for zero demo gain. |
| **Retry: specialist agent** (Opus) vs. **post-processing text pass** (GPT-5) | **Specialist agent.** It must see the video to detect respawns, checkpoint reloads, and count precise attempts. | Text-based post-processing can infer retries from timeline events but misses visual details. The timeline only captures 3-8 events/chunk; many death/respawn cycles won't be in there. |
| **Merged affect agent** (GPT-5/Gemini) vs. **separate sentiment + verbal** (Opus) | **Separate agents.** Sentiment produces a numeric curve; verbal extracts player quotes. Separate prompts produce cleaner outputs. | A combined agent splitting attention between numeric scoring and verbatim transcription produces lower quality on both. Each agent has one clear job. |
| **Refinement pass** (GPT-5) | **Cut.** | Requires microclip extraction, re-upload, re-analysis at 10 FPS. Complex, adds latency. The existing 5 FPS specialist pass is already HIGH resolution. Marginal evidence improvement doesn't justify hackathon time. |
| **segment_label on all moment schemas** (GPT-5) vs. **on TimelineMoment only** (Opus/Gemini) | **TimelineMoment only.** Assign `segment_label` to `CanonicalMoment` in dedup by temporal proximity to timeline events. | Avoids modifying 4 LLM output schemas. Specialists already receive full timeline context so they inherently understand game areas. |
| **Executive summary** (Opus) vs. **insight miner + action pack** (GPT-5) | **Merge into one LLM pass** that produces key findings, priority actions, health score, AND a cross-dimensional insight. One call, richer output schema. | Two separate passes add latency for minimal incremental value. One well-prompted call produces everything. |
| **Highlight reel** (Opus only) | **Keep.** | Pure code (zero LLM cost), 30 minutes to implement, directly enables the demo beat "jump to this moment." |
| **Pacing agent** (Opus only) | **Cut.** | Timeline pass already has `pacing_breakdown`. Lower priority vs. sentiment, retry, verbal. |
| **Chunk processing is now sequential** (codebase change) | **Acknowledged.** New agents run in the per-chunk `asyncio.gather` alongside existing 4. No concurrency model changes needed. | Each chunk already gets full prior context. New agents benefit from this automatically. |

---

## Selected Features (7 total)

| # | Feature | Type | LLM Cost | Demo Beat |
|:-:|---|---|---|---|
| 1 | `segment_label` + new enums + new schemas | Foundation | 0 | Enables all cross-video stats |
| 2 | Sentiment Agent | Specialist (video) | 1 cached call/chunk | "91% positive combat sentiment" |
| 3 | Retry Agent | Specialist (video) | 1 cached call/chunk | "68% failure rate", "40% quit after 3" |
| 4 | Verbal Agent | Specialist (video) | 1 cached call/chunk | Player quotes, Gemini audio showcase |
| 5 | Evidence Verification | Post-processing (code) | 0 | "Verified by 3 agents, confidence 95%" |
| 6 | Highlights + Executive Summary | Post-processing (code+LLM) | 1 text-only call | Health score, key findings, top moments |
| 7 | Cross-Video Study | Aggregation (code+LLM) | 1 text-only call | "53 sessions", cross-session patterns |

### LLM Schema Rules

These rules apply to every schema used as a Gemini `response_schema`:

- Use `ConfigDict()` only. Do **not** use `ConfigDict(extra="forbid")` on LLM-facing schemas.
- Put observation / evidence / decomposition fields before decision fields.
- Do **not** use `ge` / `le` constraints on LLM-facing numeric fields.
- Clamp numeric values post-call with named constants.
- Runtime-only schemas may still use `ConfigDict(extra="forbid")`.

---

## PHASE 1: Foundation

All subsequent features depend on these changes.

### Step 1.1 — Modify `src/gamesight/schemas/enums.py`

Add these enums after the existing `VideoSourceType` class, before `__all__`:

```python
class EmotionLabel(str, enum.Enum):
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    BORED = "bored"
    NEUTRAL = "neutral"
    FOCUSED = "focused"
    AMUSED = "amused"
    EXCITED = "excited"
    TRIUMPHANT = "triumphant"


class SilenceType(str, enum.Enum):
    FOCUSED = "focused"
    RESIGNED = "resigned"
    CONFUSED = "confused"
    TENSE = "tense"
    IDLE = "idle"


class VerbalCategory(str, enum.Enum):
    COMPLAINT = "complaint"
    PRAISE = "praise"
    QUESTION = "question"
    NARRATION = "narration"
    STRATEGY = "strategy"
    SUGGESTION = "suggestion"
    REACTION = "reaction"


class RetryOutcome(str, enum.Enum):
    SUCCEEDED = "succeeded"
    ABANDONED = "abandoned"
    STILL_TRYING = "still_trying"


class InsightConfidence(str, enum.Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    SUGGESTIVE = "suggestive"
```

Add to `AgentKind`:
```python
    SENTIMENT = "sentiment"
    RETRY = "retry"
    VERBAL = "verbal"
```

Update `__all__` to include all new enum names.

### Step 1.1a — Modify `src/gamesight/config.py`

Add shared normalization helpers and named constants used by dedup, aggregation, executive clamping, and study grouping:

```python
import re as _re
from typing import Final

SENTIMENT_SCORE_MIN: Final[int] = -10
SENTIMENT_SCORE_MAX: Final[int] = 10
VERBAL_SENTIMENT_MIN: Final[int] = -5
VERBAL_SENTIMENT_MAX: Final[int] = 5
HEALTH_SCORE_MIN: Final[int] = 0
HEALTH_SCORE_MAX: Final[int] = 100

RETRY_ATTEMPT_SEVERITY_WEIGHT: Final[int] = 2
RETRY_QUIT_SIGNAL_SEVERITY_BONUS: Final[int] = 3
VERBAL_SEVERITY_WEIGHT: Final[int] = 2
MAX_SEVERITY_NUMERIC: Final[int] = 10


def clamp(value: int | float, min_val: int | float, max_val: int | float) -> int | float:
    return max(min_val, min(max_val, value))


def normalize_segment_label(label: str | None) -> str | None:
    if label is None:
        return None
    lowered = label.strip().lower()
    normalized = _re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or None


def normalize_game_key(title: str) -> str:
    lowered = title.strip().lower()
    normalized = _re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not normalized:
        raise ValueError("Game title cannot be normalized into a valid game_key.")
    return normalized
```

### Step 1.2 — Modify `src/gamesight/schemas/timeline.py`

Add `segment_label` field to `TimelineMoment`, after `significance`:

```python
    segment_label: str = Field(
        description="Short reusable snake_case label for the game area or challenge, e.g. 'bridge_jump', 'boss_dragon', 'tutorial_movement'. Reuse the same label if the player returns to the same area."
    )
```

### Step 1.3 — Modify `src/gamesight/prompts/timeline.py`

Replace `TIMELINE_ANALYSIS_PROMPT` with:

```python
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
```

### Step 1.4 — Modify `src/gamesight/schemas/video.py`

Add `segment_label` to `TimelineEvent`, after `significance`:

```python
    segment_label: str
```

Add `game_key` to `VideoInfo`, after `title`:

```python
    game_key: str
```

Add imports at top of file:

```python
from gamesight.schemas.sentiment import SentimentChunkAnalysis
from gamesight.schemas.retry import RetryChunkAnalysis
from gamesight.schemas.verbal import VerbalChunkAnalysis
```

Add optional fields to `ChunkAnalysisBundle`:

```python
class ChunkAnalysisBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int
    friction: FrictionChunkAnalysis
    clarity: ClarityChunkAnalysis
    delight: DelightChunkAnalysis
    quality: QualityChunkAnalysis
    sentiment: SentimentChunkAnalysis | None = None
    retry: RetryChunkAnalysis | None = None
    verbal: VerbalChunkAnalysis | None = None
```

Update `__all__` to include `"SentimentChunkAnalysis"`, `"RetryChunkAnalysis"`, `"VerbalChunkAnalysis"` if re-exported, or leave them in their own modules.

### Step 1.5 — Create `src/gamesight/schemas/sentiment.py`

```python
from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import EmotionLabel, SilenceType


class SentimentMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    trigger: str = Field(description="What caused this emotional state or shift")
    visual_basis: str = Field(description="Gameplay state informing this rating: success, failure, exploration, stalling")
    audio_basis: str = Field(description="Player voice tone, words, volume, breathing. 'Silent' if no player audio")
    facecam_basis: str | None = Field(description="Facial expression and posture. None if no facecam visible")
    silence_type: SilenceType | None = Field(
        description="If player is silent, classify the silence type. None if player is speaking"
    )
    confidence: str = Field(description="high, medium, or low based on evidence clarity")
    dominant_emotion: EmotionLabel
    sentiment_score: int = Field(description="Player sentiment from -10 (rage-quit) to +10 (peak delight)")


class SentimentChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What gameplay section this covers")
    moments: list[SentimentMoment] = Field(
        description="5-15 sentiment samples, roughly every 20-30 seconds through the chunk"
    )
    sentiment_curve: str = Field(description="Narrative: how player emotion evolves across this segment")
    lowest_point: str = Field(description="Timestamp and cause of the emotional low point")
    highest_point: str = Field(description="Timestamp and cause of the emotional high point")
    recovery_after_setback: str = Field(
        description="How quickly and fully the player recovers emotionally after negative events. 'No setbacks observed' if none"
    )
    dominant_emotion: EmotionLabel
    average_sentiment: float = Field(description="Mean sentiment score for this chunk")


__all__ = ["SentimentChunkAnalysis", "SentimentMoment"]
```

### Step 1.6 — Create `src/gamesight/schemas/retry.py`

```python
from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import RetryOutcome


class ChallengeAttempt(BaseModel):
    model_config = ConfigDict()

    attempt_number: int = Field(description="Sequential attempt number starting from 1")
    relative_timestamp: str = Field(description="MM:SS from chunk start when this attempt begins")
    duration_seconds: int = Field(description="Approximate seconds spent on this attempt")
    outcome: str = Field(description="'died', 'failed', 'succeeded', or 'abandoned'")
    player_reaction: str = Field(description="Observable player reaction after this attempt")
    strategy_change: str = Field(
        description="How the player changed approach from previous attempt, or 'same_strategy'"
    )


class RetrySequence(BaseModel):
    model_config = ConfigDict()

    challenge_name: str = Field(
        description="Short snake_case name matching segment_label from timeline, e.g. 'bridge_jump', 'boss_phase_2'"
    )
    challenge_location: str = Field(description="Where in the game this challenge occurs")
    first_attempt_timestamp: str = Field(description="MM:SS of the first attempt in this chunk")
    total_attempts: int = Field(description="Total number of attempts observed in this chunk")
    attempts: list[ChallengeAttempt] = Field(description="Each individual attempt, chronological")
    final_outcome: RetryOutcome
    total_time_seconds: int = Field(description="Total seconds spent across all attempts")
    frustration_escalation: str = Field(
        description="How frustration changed: escalating, stable, de-escalating, or mixed"
    )
    quit_signal: bool = Field(
        description="True if the player showed signs of wanting to stop playing entirely"
    )


class RetryChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What gameplay section this covers")
    retry_sequences: list[RetrySequence] = Field(description="0-3 retry sequences detected in this chunk")
    total_deaths_or_failures: int = Field(
        description="Total death/failure count including non-retry single failures"
    )
    first_attempt_successes: int = Field(description="Number of challenges cleared on the first try")
    progression_rate: str = Field(
        description="How efficiently the player progresses: smooth, moderate_friction, or heavily_blocked"
    )


__all__ = ["ChallengeAttempt", "RetryChunkAnalysis", "RetrySequence"]
```

### Step 1.7 — Create `src/gamesight/schemas/verbal.py`

```python
from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import VerbalCategory


class VerbalMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    quote: str = Field(description="Exact words spoken by the player, as close to verbatim as possible")
    voice_tone: str = Field(
        description="angry, frustrated, confused, neutral, amused, excited, sarcastic, or resigned"
    )
    game_context: str = Field(description="What was happening on screen when this was said")
    actionable_insight: str | None = Field(description="The design implication if actionable, else None")
    category: VerbalCategory
    sentiment_score: int = Field(description="-5 (very negative) to +5 (very positive)")
    is_actionable: bool = Field(description="True if this quote implies a specific design change the studio could make")


class VerbalChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    has_player_audio: bool = Field(description="Whether player speech was detected in this chunk")
    moments: list[VerbalMoment] = Field(
        description="All notable verbal feedback, chronological. Empty if no speech detected."
    )
    total_speech_segments: int = Field(description="Approximate count of distinct speech segments")
    talk_ratio: str = Field(
        description="What portion of the chunk has player speech: silent, occasional, frequent, or constant"
    )
    dominant_tone: str = Field(description="Overall tone of verbal feedback in this chunk")
    most_actionable_quote: str | None = Field(
        description="The single most design-relevant thing the player said, or None"
    )


__all__ = ["VerbalChunkAnalysis", "VerbalMoment"]
```

### Step 1.8 — Create `src/gamesight/schemas/executive.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class KeyFinding(BaseModel):
    model_config = ConfigDict()

    evidence_summary: str = Field(
        description="Specific timestamps, player quotes, and statistics that support this finding"
    )
    affected_timestamps: list[str] = Field(description="Absolute timestamps (MM:SS) where this finding manifests")
    finding: str = Field(description="The insight in one sentence")
    recommended_action: str = Field(description="What the development team should do about this")
    severity: str = Field(description="critical, important, or notable")


class ExecutiveSummary(BaseModel):
    model_config = ConfigDict()

    executive_summary: str = Field(
        description="Three short paragraphs: session overview, critical issues, strengths to protect"
    )
    key_findings: list[KeyFinding] = Field(description="3-5 prioritized findings, most impactful first")
    priority_actions: list[str] = Field(description="Ranked list of development actions, most urgent first")
    cross_dimensional_insight: str = Field(
        description="One non-obvious pattern that connects findings across multiple analysis dimensions"
    )
    session_health_score: int = Field(
        description="Overall session health from 0 (unplayable) to 100 (flawless)"
    )


__all__ = ["ExecutiveSummary", "KeyFinding"]
```

### Step 1.9 — Create `src/gamesight/schemas/highlights.py`

```python
from pydantic import BaseModel, ConfigDict


class HighlightMoment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int
    absolute_timestamp: str
    absolute_seconds: float
    clip_start_seconds: float
    clip_end_seconds: float
    category: str
    headline: str
    why_important: str
    evidence: list[str]
    importance_score: float
    corroborating_agents: list[str]


class HighlightReel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    total_moments_analyzed: int
    highlights: list[HighlightMoment]
    one_line_verdict: str


__all__ = ["HighlightMoment", "HighlightReel"]
```

### Step 1.10 — Create `src/gamesight/schemas/study.py`

```python
from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import InsightConfidence


class SegmentFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_label: str
    sessions_encountered: int
    sessions_with_friction: int
    friction_rate: float
    avg_friction_severity: float
    sessions_with_delight: int
    delight_rate: float
    dominant_friction_source: str | None
    dominant_delight_driver: str | None
    avg_sentiment: float | None
    positive_sentiment_rate: float | None
    first_attempt_failure_rate: float | None
    avg_retry_attempts: float | None
    quit_signal_rate: float | None
    representative_quotes: list[str]


class StopRiskCohort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_segment: str
    sessions_affected: int
    total_sessions: int
    percentage: float
    common_pattern: str
    representative_quotes: list[str]


class CrossVideoInsight(BaseModel):
    model_config = ConfigDict()

    title: str = Field(description="Short headline for the insight")
    insight: str = Field(description="A non-obvious pattern discovered across sessions")
    evidence_summary: str = Field(description="Statistics and session counts supporting this insight")
    sessions_supporting: int = Field(description="Number of sessions that exhibit this pattern")
    confidence: InsightConfidence
    recommended_action: str = Field(description="What the studio should do based on this insight")


class CrossVideoSynthesis(BaseModel):
    model_config = ConfigDict()

    insights: list[CrossVideoInsight] = Field(description="3-5 non-obvious cross-session patterns")
    top_priorities: list[str] = Field(description="Ranked action items for the studio")
    executive_summary: str = Field(description="3-paragraph summary of cross-session findings")


class StudyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_key: str
    game_title: str
    total_sessions: int
    total_duration_minutes: float
    segment_fingerprints: list[SegmentFingerprint]
    stop_risk_cohorts: list[StopRiskCohort]
    insights: list[CrossVideoInsight]
    top_priorities: list[str]
    executive_summary: str


__all__ = [
    "CrossVideoInsight",
    "CrossVideoSynthesis",
    "SegmentFingerprint",
    "StopRiskCohort",
    "StudyReport",
]
```

### Step 1.11 — Modify `src/gamesight/schemas/report.py`

Add imports at top:

```python
from pydantic import Field

from gamesight.schemas.executive import ExecutiveSummary
from gamesight.schemas.highlights import HighlightReel
```

Add typed enrichment fields to `CanonicalMoment` (after `source_chunk_index`):

```python
    segment_label: str | None = None
    confidence_score: float = 0.5
    corroborating_agents: list[str] = Field(default_factory=list)
    sentiment_raw_score: int | None = None
    retry_total_attempts: int | None = None
    retry_quit_signal: bool | None = None
    retry_final_outcome: str | None = None
    verbal_is_actionable: bool | None = None
    verbal_quote: str | None = None
```

Add a runtime-only coverage model:

```python
class ChunkAgentCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_index: int
    friction: bool
    clarity: bool
    delight: bool
    quality: bool
    sentiment: bool
    retry: bool
    verbal: bool
```

Add new default-valued fields to `DeduplicatedAnalyses`:

```python
    sentiment_moments: list[CanonicalMoment] = []
    retry_moments: list[CanonicalMoment] = []
    verbal_moments: list[CanonicalMoment] = []
```

Add new default-valued fields to `VideoReport`:

```python
    game_key: str
    sentiment_moments: list[CanonicalMoment] = []
    retry_moments: list[CanonicalMoment] = []
    verbal_moments: list[CanonicalMoment] = []
    avg_sentiment: float | None = None
    sentiment_by_segment: dict[str, float] = {}
    total_retry_sequences: int = 0
    first_attempt_failure_count: int = 0
    notable_quotes: list[str] = []
    highlights: HighlightReel | None = None
    executive: ExecutiveSummary | None = None
    agent_coverage: list[ChunkAgentCoverage] = Field(default_factory=list)
```

Update `__all__` to include `"ChunkAgentCoverage"`, `"ExecutiveSummary"`, `"HighlightReel"`.

### Step 1.12 — Update `src/gamesight/schemas/__init__.py`

Add imports for all new schema modules and their exported classes. Add them to `__all__`.

### Step 1.13 — Modify `src/gamesight/pipeline/timeline_pass.py`

Normalize `segment_label` immediately after timestamp validation, then carry it into `TimelineEvent`:

```python
from gamesight.config import normalize_segment_label

        for event in result.events:
            event.relative_timestamp = validate_relative_timestamp(
                event.relative_timestamp,
                chunk.start_seconds,
                chunk.duration_seconds,
            )
            event.segment_label = normalize_segment_label(event.segment_label) or "unknown"

            events.append(
                TimelineEvent(
                    source_chunk_index=chunk.index,
                    absolute_seconds=absolute_seconds,
                    absolute_timestamp=absolute_timestamp,
                    relative_timestamp=event.relative_timestamp,
                    visual_observation=event.visual_observation,
                    audio_observation=event.audio_observation,
                    player_expression=event.player_expression,
                    event_description=event.event_description,
                    phase_kind=event.phase_kind,
                    significance=event.significance,
                    segment_label=event.segment_label,
                )
            )
```

**Depends on:** Steps 1.2, 1.4, 1.1a

### Step 1.14 — Modify `src/gamesight/gemini/debug.py`

Update `_SCHEMA_LABELS`:

```python
_SCHEMA_LABELS: dict[str, str] = {
    "TimelineChunkResult": "timeline",
    "FrictionChunkAnalysis": "friction",
    "ClarityChunkAnalysis": "clarity",
    "DelightChunkAnalysis": "delight",
    "QualityChunkAnalysis": "quality",
    "SentimentChunkAnalysis": "sentiment",
    "RetryChunkAnalysis": "retry",
    "VerbalChunkAnalysis": "verbal",
    "ExecutiveSummary": "executive",
    "CrossVideoSynthesis": "study_synthesis",
}
```

---

## PHASE 2: New Specialist Agents

**Depends on:** Phase 1 complete.

### Step 2.1 — Create `src/gamesight/prompts/sentiment.py`

```python
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
```

### Step 2.2 — Create `src/gamesight/prompts/retry.py`

```python
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
```

### Step 2.3 — Create `src/gamesight/prompts/verbal.py`

```python
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
```

### Step 2.4 — Modify `src/gamesight/prompts/__init__.py`

Add imports and `__all__` entries:

```python
from gamesight.prompts.sentiment import SENTIMENT_AGENT_PROMPT
from gamesight.prompts.retry import RETRY_AGENT_PROMPT
from gamesight.prompts.verbal import VERBAL_AGENT_PROMPT
```

### Step 2.5 — Modify `src/gamesight/pipeline/chunk_pass.py`

**2.5a — Add imports:**

```python
from pydantic import ValidationError

from gamesight.config import (
    SENTIMENT_SCORE_MAX,
    SENTIMENT_SCORE_MIN,
    VERBAL_SENTIMENT_MAX,
    VERBAL_SENTIMENT_MIN,
    clamp,
)
from gamesight.gemini.generate import GeminiSafetyError
from gamesight.prompts.sentiment import SENTIMENT_AGENT_PROMPT
from gamesight.prompts.retry import RETRY_AGENT_PROMPT
from gamesight.prompts.verbal import VERBAL_AGENT_PROMPT
from gamesight.schemas.retry import RetryChunkAnalysis
from gamesight.schemas.sentiment import SentimentChunkAnalysis
from gamesight.schemas.verbal import VerbalChunkAnalysis
```

**2.5b — Add post-parse clamping helpers** for LLM-facing numeric fields:

```python
def _clamp_sentiment_analysis(result: SentimentChunkAnalysis) -> SentimentChunkAnalysis:
    for moment in result.moments:
        moment.sentiment_score = int(clamp(moment.sentiment_score, SENTIMENT_SCORE_MIN, SENTIMENT_SCORE_MAX))
    result.average_sentiment = float(
        clamp(result.average_sentiment, float(SENTIMENT_SCORE_MIN), float(SENTIMENT_SCORE_MAX))
    )
    return result


def _clamp_verbal_analysis(result: VerbalChunkAnalysis) -> VerbalChunkAnalysis:
    for moment in result.moments:
        moment.sentiment_score = int(clamp(moment.sentiment_score, VERBAL_SENTIMENT_MIN, VERBAL_SENTIMENT_MAX))
    return result
```

**2.5c — Add safe wrapper functions** (after the existing `_run_direct_agent`):

```python
async def _safe_cached_agent(
    client: genai.Client,
    *,
    cache_name: str,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
) -> ModelT | None:
    try:
        return await _run_cached_agent(
            client,
            cache_name=cache_name,
            conversation=conversation,
            prompt=prompt,
            response_schema=response_schema,
        )
    except (GeminiSafetyError, ValidationError, ValueError) as exc:
        logger.warning("Optional cached agent %s failed with recoverable error: %s", response_schema.__name__, exc)
        return None


async def _safe_direct_agent(
    client: genai.Client,
    *,
    conversation: list[types.Content],
    prompt: str,
    response_schema: type[ModelT],
    media_resolution: types.MediaResolution | None,
) -> ModelT | None:
    try:
        return await _run_direct_agent(
            client,
            conversation=conversation,
            prompt=prompt,
            response_schema=response_schema,
            media_resolution=media_resolution,
        )
    except (GeminiSafetyError, ValidationError, ValueError) as exc:
        logger.warning("Optional direct agent %s failed with recoverable error: %s", response_schema.__name__, exc)
        return None
```

**2.5d — Modify `_normalize_specialist_timestamps`:** Add optional kwargs for new agents:

```python
def _normalize_specialist_timestamps(
    chunk: ChunkInfo,
    *,
    friction: FrictionChunkAnalysis,
    clarity: ClarityChunkAnalysis,
    delight: DelightChunkAnalysis,
    quality: QualityChunkAnalysis,
    sentiment: SentimentChunkAnalysis | None = None,
    retry: RetryChunkAnalysis | None = None,
    verbal: VerbalChunkAnalysis | None = None,
) -> None:
    # ... existing code for friction, clarity, delight, quality unchanged ...
    if sentiment:
        for moment in sentiment.moments:
            moment.relative_timestamp = validate_relative_timestamp(
                moment.relative_timestamp, chunk.start_seconds, chunk.duration_seconds,
            )
    if retry:
        for seq in retry.retry_sequences:
            seq.first_attempt_timestamp = validate_relative_timestamp(
                seq.first_attempt_timestamp, chunk.start_seconds, chunk.duration_seconds,
            )
            for attempt in seq.attempts:
                attempt.relative_timestamp = validate_relative_timestamp(
                    attempt.relative_timestamp, chunk.start_seconds, chunk.duration_seconds,
                )
    if verbal:
        for moment in verbal.moments:
            moment.relative_timestamp = validate_relative_timestamp(
                moment.relative_timestamp, chunk.start_seconds, chunk.duration_seconds,
            )
```

**2.5e — Modify `run_cached_specialist_pass`:** After the existing 4-agent gather, add:

```python
        # Optional specialist agents — fail gracefully
        sentiment, retry, verbal = await asyncio.gather(
            _safe_cached_agent(
                client, cache_name=cache.name, conversation=warmup_conversation,
                prompt=_build_specialist_prompt(
                    timeline=timeline, current_chunk_index=chunk.index,
                    prior_findings=prior_findings, game_title=game_title,
                    game_genre=game_genre, agent_prompt=SENTIMENT_AGENT_PROMPT,
                ),
                response_schema=SentimentChunkAnalysis,
            ),
            _safe_cached_agent(
                client, cache_name=cache.name, conversation=warmup_conversation,
                prompt=_build_specialist_prompt(
                    timeline=timeline, current_chunk_index=chunk.index,
                    prior_findings=prior_findings, game_title=game_title,
                    game_genre=game_genre, agent_prompt=RETRY_AGENT_PROMPT,
                ),
                response_schema=RetryChunkAnalysis,
            ),
            _safe_cached_agent(
                client, cache_name=cache.name, conversation=warmup_conversation,
                prompt=_build_specialist_prompt(
                    timeline=timeline, current_chunk_index=chunk.index,
                    prior_findings=prior_findings, game_title=game_title,
                    game_genre=game_genre, agent_prompt=VERBAL_AGENT_PROMPT,
                ),
                response_schema=VerbalChunkAnalysis,
            ),
        )

        if sentiment is not None:
            sentiment = _clamp_sentiment_analysis(sentiment)
        if verbal is not None:
            verbal = _clamp_verbal_analysis(verbal)
```

Update the `_normalize_specialist_timestamps` call to include new agents:

```python
    _normalize_specialist_timestamps(
        chunk,
        friction=friction, clarity=clarity, delight=delight, quality=quality,
        sentiment=sentiment, retry=retry, verbal=verbal,
    )
```

Update the `ChunkAnalysisBundle` construction to include new fields:

```python
    return ChunkAnalysisBundle(
        chunk_index=chunk.index,
        friction=friction, clarity=clarity, delight=delight, quality=quality,
        sentiment=sentiment, retry=retry, verbal=verbal,
    )
```

**2.5f — Apply identical changes to `run_direct_specialist_pass`:** Same pattern — add a second `asyncio.gather` with `_safe_direct_agent` for the 3 new agents after the existing 4-agent gather, then clamp `sentiment` and `verbal`, then update `_normalize_specialist_timestamps` and `ChunkAnalysisBundle` construction.

### Step 2.6 — Modify `src/gamesight/pipeline/dedup.py`

**2.6a — Add imports:**

```python
from gamesight.config import (
    MAX_SEVERITY_NUMERIC,
    RETRY_ATTEMPT_SEVERITY_WEIGHT,
    RETRY_QUIT_SIGNAL_SEVERITY_BONUS,
    SENTIMENT_SCORE_MAX,
    SENTIMENT_SCORE_MIN,
    VERBAL_SENTIMENT_MAX,
    VERBAL_SENTIMENT_MIN,
    VERBAL_SEVERITY_WEIGHT,
    clamp,
    normalize_segment_label,
)
from gamesight.schemas.video import VideoTimeline
```

**2.6b — Add helper to find nearest segment_label from timeline:**

```python
def _nearest_segment_label(absolute_seconds: float, timeline: VideoTimeline, max_distance: float = 30.0) -> str | None:
    best_label: str | None = None
    best_distance = max_distance + 1.0
    for event in timeline.events:
        distance = abs(event.absolute_seconds - absolute_seconds)
        if distance < best_distance:
            best_distance = distance
            best_label = event.segment_label
    if best_label is None or best_distance > max_distance:
        return None
    return normalize_segment_label(best_label)
```

**2.6c — Modify all existing `_canonical_from_*` functions** to accept `timeline: VideoTimeline` as a parameter and populate `segment_label` on each `CanonicalMoment`:

In each function, after computing `absolute_seconds`, add:

```python
        seg_label = _nearest_segment_label(absolute_seconds, timeline)
```

And include `segment_label=seg_label` in each `CanonicalMoment(...)` construction.

**2.6d — Add new canonical conversion functions:**

```python
def _canonical_from_sentiment(chunk: ChunkInfo, analysis: ChunkAnalysisBundle, timeline: VideoTimeline) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.sentiment:
        return moments
    for moment in analysis.sentiment.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        raw_score = int(clamp(moment.sentiment_score, SENTIMENT_SCORE_MIN, SENTIMENT_SCORE_MAX))
        evidence = [f"Trigger: {moment.trigger}", f"Visual: {moment.visual_basis}", f"Audio: {moment.audio_basis}"]
        if moment.facecam_basis:
            evidence.append(f"Expression: {moment.facecam_basis}")
        if moment.silence_type:
            evidence.append(f"Silence type: {moment.silence_type.value}")
        segment_label = _nearest_segment_label(absolute_seconds, timeline)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.SENTIMENT,
                source_label=moment.dominant_emotion.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.trigger,
                game_context=moment.visual_basis,
                evidence=evidence,
                severity_numeric=abs(raw_score),
                source_chunk_index=chunk.index,
                segment_label=segment_label,
                sentiment_raw_score=raw_score,
            )
        )
    return moments


def _canonical_from_retry(chunk: ChunkInfo, analysis: ChunkAnalysisBundle, timeline: VideoTimeline) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.retry:
        return moments
    for seq in analysis.retry.retry_sequences:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(seq.first_attempt_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        evidence = [f"Attempt {a.attempt_number}: {a.outcome} ({a.player_reaction})" for a in seq.attempts]
        evidence.append(f"Frustration: {seq.frustration_escalation}")
        if seq.quit_signal:
            evidence.append("QUIT SIGNAL DETECTED")
        severity = min(
            seq.total_attempts * RETRY_ATTEMPT_SEVERITY_WEIGHT
            + (RETRY_QUIT_SIGNAL_SEVERITY_BONUS if seq.quit_signal else 0),
            MAX_SEVERITY_NUMERIC,
        )
        segment_label = normalize_segment_label(seq.challenge_name) or _nearest_segment_label(absolute_seconds, timeline)
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.RETRY,
                source_label=seq.challenge_name,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=f"{seq.total_attempts} attempts at {seq.challenge_name}, outcome: {seq.final_outcome.value}",
                game_context=seq.challenge_location,
                evidence=evidence,
                severity_numeric=severity,
                source_chunk_index=chunk.index,
                segment_label=segment_label,
                retry_total_attempts=seq.total_attempts,
                retry_quit_signal=seq.quit_signal,
                retry_final_outcome=seq.final_outcome.value,
            )
        )
    return moments


def _canonical_from_verbal(chunk: ChunkInfo, analysis: ChunkAnalysisBundle, timeline: VideoTimeline) -> list[CanonicalMoment]:
    moments: list[CanonicalMoment] = []
    if not analysis.verbal or not analysis.verbal.has_player_audio:
        return moments
    for moment in analysis.verbal.moments:
        corrected_timestamp, relative_seconds = _validated_relative_seconds(moment.relative_timestamp, chunk)
        if not is_owned(relative_seconds, chunk):
            continue
        absolute_seconds, absolute_timestamp = relative_to_absolute(corrected_timestamp, chunk.start_seconds)
        raw_score = int(clamp(moment.sentiment_score, VERBAL_SENTIMENT_MIN, VERBAL_SENTIMENT_MAX))
        evidence = [f"Tone: {moment.voice_tone}", f"Category: {moment.category.value}"]
        if moment.is_actionable and moment.actionable_insight:
            evidence.append(f"Actionable: {moment.actionable_insight}")
        moments.append(
            CanonicalMoment(
                agent_kind=AgentKind.VERBAL,
                source_label=moment.category.value,
                absolute_seconds=absolute_seconds,
                absolute_timestamp=absolute_timestamp,
                summary=moment.quote,
                game_context=moment.game_context,
                evidence=evidence,
                severity_numeric=min(abs(raw_score) * VERBAL_SEVERITY_WEIGHT, MAX_SEVERITY_NUMERIC),
                source_chunk_index=chunk.index,
                segment_label=_nearest_segment_label(absolute_seconds, timeline),
                verbal_is_actionable=moment.is_actionable,
                verbal_quote=moment.quote,
            )
        )
    return moments
```

**2.6e — Modify `deduplicate_moments` signature** to accept `timeline`:

```python
def deduplicate_moments(
    chunks: list[ChunkInfo],
    analyses: list[ChunkAnalysisBundle],
    timeline: VideoTimeline,
) -> DeduplicatedAnalyses:
```

Pass `timeline` to all `_canonical_from_*` calls. Add new lists:

```python
    sentiment_moments: list[CanonicalMoment] = []
    retry_moments: list[CanonicalMoment] = []
    verbal_moments: list[CanonicalMoment] = []

    for analysis in analyses:
        chunk = chunk_map[analysis.chunk_index]
        # ... existing 4 canonical_from calls, adding timeline param ...
        friction_moments.extend(_canonical_from_friction(chunk, analysis, timeline))
        clarity_moments.extend(_canonical_from_clarity(chunk, analysis, timeline))
        delight_moments.extend(_canonical_from_delight(chunk, analysis, timeline))
        quality_issues.extend(_canonical_from_quality(chunk, analysis, timeline))
        sentiment_moments.extend(_canonical_from_sentiment(chunk, analysis, timeline))
        retry_moments.extend(_canonical_from_retry(chunk, analysis, timeline))
        verbal_moments.extend(_canonical_from_verbal(chunk, analysis, timeline))

    # Sort all lists
    sentiment_moments.sort(key=lambda item: item.absolute_seconds)
    retry_moments.sort(key=lambda item: item.absolute_seconds)
    verbal_moments.sort(key=lambda item: item.absolute_seconds)

    return DeduplicatedAnalyses(
        friction_moments=friction_moments,
        clarity_moments=clarity_moments,
        delight_moments=delight_moments,
        quality_issues=quality_issues,
        sentiment_moments=sentiment_moments,
        retry_moments=retry_moments,
        verbal_moments=verbal_moments,
    )
```

---

## PHASE 3: Post-Processing Passes

**Depends on:** Phase 2 complete.

### Step 3.1 — Create `src/gamesight/pipeline/verification.py`

```python
"""Cross-agent evidence verification via temporal proximity matching.

For each CanonicalMoment, checks how many OTHER agent types flagged a moment
within a configurable time window. Moments corroborated by multiple independent
agents receive higher confidence scores.
"""

from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses

CORROBORATION_WINDOW_SECONDS: float = 15.0


def _all_moments(deduplicated: DeduplicatedAnalyses) -> list[CanonicalMoment]:
    return [
        *deduplicated.friction_moments,
        *deduplicated.clarity_moments,
        *deduplicated.delight_moments,
        *deduplicated.quality_issues,
        *deduplicated.sentiment_moments,
        *deduplicated.retry_moments,
        *deduplicated.verbal_moments,
    ]


def _same_segment_or_unknown(left: CanonicalMoment, right: CanonicalMoment) -> bool:
    if left.segment_label and right.segment_label:
        return left.segment_label == right.segment_label
    return True


def _verify_single(moment: CanonicalMoment, all_moments: list[CanonicalMoment]) -> CanonicalMoment:
    corroborating: set[str] = set()
    for other in all_moments:
        if other.agent_kind == moment.agent_kind:
            continue
        if not _same_segment_or_unknown(moment, other):
            continue
        if abs(other.absolute_seconds - moment.absolute_seconds) <= CORROBORATION_WINDOW_SECONDS:
            corroborating.add(other.agent_kind.value)

    base_confidence = 0.5
    confidence = base_confidence + 0.15 * len(corroborating)
    has_quote = moment.verbal_quote is not None
    if has_quote:
        confidence += 0.1
    confidence = min(confidence, 1.0)

    return CanonicalMoment(
        agent_kind=moment.agent_kind,
        source_label=moment.source_label,
        absolute_seconds=moment.absolute_seconds,
        absolute_timestamp=moment.absolute_timestamp,
        summary=moment.summary,
        game_context=moment.game_context,
        evidence=moment.evidence,
        severity_numeric=moment.severity_numeric,
        source_chunk_index=moment.source_chunk_index,
        segment_label=moment.segment_label,
        confidence_score=round(confidence, 2),
        corroborating_agents=sorted(corroborating),
        sentiment_raw_score=moment.sentiment_raw_score,
        retry_total_attempts=moment.retry_total_attempts,
        retry_quit_signal=moment.retry_quit_signal,
        retry_final_outcome=moment.retry_final_outcome,
        verbal_is_actionable=moment.verbal_is_actionable,
        verbal_quote=moment.verbal_quote,
    )


def verify_moments(deduplicated: DeduplicatedAnalyses) -> DeduplicatedAnalyses:
    all_m = _all_moments(deduplicated)
    return DeduplicatedAnalyses(
        friction_moments=[_verify_single(m, all_m) for m in deduplicated.friction_moments],
        clarity_moments=[_verify_single(m, all_m) for m in deduplicated.clarity_moments],
        delight_moments=[_verify_single(m, all_m) for m in deduplicated.delight_moments],
        quality_issues=[_verify_single(m, all_m) for m in deduplicated.quality_issues],
        sentiment_moments=[_verify_single(m, all_m) for m in deduplicated.sentiment_moments],
        retry_moments=[_verify_single(m, all_m) for m in deduplicated.retry_moments],
        verbal_moments=[_verify_single(m, all_m) for m in deduplicated.verbal_moments],
    )


__all__ = ["verify_moments"]
```

### Step 3.2 — Create `src/gamesight/pipeline/highlights.py`

```python
"""Curate the top N most significant moments into a highlight reel."""

from gamesight.schemas.highlights import HighlightMoment, HighlightReel
from gamesight.schemas.report import CanonicalMoment, DeduplicatedAnalyses
from gamesight.schemas.video import VideoInfo

AGENT_WEIGHTS: dict[str, float] = {
    "friction": 1.2,
    "clarity": 1.0,
    "delight": 0.8,
    "quality": 1.1,
    "sentiment": 0.7,
    "retry": 1.3,
    "verbal": 0.9,
}

CATEGORY_MAP: dict[str, str] = {
    "friction": "critical_friction",
    "clarity": "clarity_failure",
    "delight": "player_delight",
    "quality": "bug",
    "sentiment": "sentiment_swing",
    "retry": "retry_loop",
    "verbal": "player_feedback",
}

CLUSTER_WINDOW_SECONDS: float = 30.0
MAX_HIGHLIGHTS: int = 10


def _all_moments(deduplicated: DeduplicatedAnalyses) -> list[CanonicalMoment]:
    return [
        *deduplicated.friction_moments,
        *deduplicated.clarity_moments,
        *deduplicated.delight_moments,
        *deduplicated.quality_issues,
        *deduplicated.sentiment_moments,
        *deduplicated.retry_moments,
        *deduplicated.verbal_moments,
    ]


def _importance(moment: CanonicalMoment) -> float:
    weight = AGENT_WEIGHTS.get(moment.agent_kind.value, 1.0)
    corroboration_bonus = 1.0 + 0.3 * len(moment.corroborating_agents)
    return moment.severity_numeric * weight * corroboration_bonus


def build_highlight_reel(video: VideoInfo, deduplicated: DeduplicatedAnalyses) -> HighlightReel:
    all_m = _all_moments(deduplicated)
    if not all_m:
        return HighlightReel(
            video_id=video.video_id,
            total_moments_analyzed=0,
            highlights=[],
            one_line_verdict="No significant moments detected.",
        )

    scored = sorted(all_m, key=_importance, reverse=True)

    # Cluster: keep only the highest-scored moment per window
    selected: list[CanonicalMoment] = []
    for moment in scored:
        if len(selected) >= MAX_HIGHLIGHTS:
            break
        if any(abs(s.absolute_seconds - moment.absolute_seconds) < CLUSTER_WINDOW_SECONDS for s in selected):
            continue
        selected.append(moment)

    highlights: list[HighlightMoment] = []
    for rank, moment in enumerate(selected, 1):
        highlights.append(
            HighlightMoment(
                rank=rank,
                absolute_timestamp=moment.absolute_timestamp,
                absolute_seconds=moment.absolute_seconds,
                clip_start_seconds=max(0.0, moment.absolute_seconds - 10.0),
                clip_end_seconds=min(video.duration_seconds, moment.absolute_seconds + 10.0),
                category=CATEGORY_MAP.get(moment.agent_kind.value, "other"),
                headline=moment.summary[:120],
                why_important=f"Severity {moment.severity_numeric}/10, confidence {moment.confidence_score:.0%}",
                evidence=moment.evidence[:5],
                importance_score=round(_importance(moment), 2),
                corroborating_agents=moment.corroborating_agents,
            )
        )

    top = selected[0] if selected else None
    verdict = top.summary[:200] if top else "Session analysis complete."

    return HighlightReel(
        video_id=video.video_id,
        total_moments_analyzed=len(all_m),
        highlights=highlights,
        one_line_verdict=verdict,
    )


__all__ = ["build_highlight_reel"]
```

### Step 3.3 — Create `src/gamesight/prompts/executive.py`

```python
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
```

### Step 3.4 — Create `src/gamesight/pipeline/executive_pass.py`

```python
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
```

### Step 3.5 — Modify `src/gamesight/pipeline/aggregation.py`

**3.5a — Add imports:**

```python
from gamesight.schemas.report import ChunkAgentCoverage
from gamesight.schemas.highlights import HighlightReel
from gamesight.schemas.executive import ExecutiveSummary
```

**3.5b — Add new metric computations** inside `build_video_report()`, after existing code and before the return statement:

```python
    # --- New agent metrics ---
    # Sentiment aggregation using typed fields
    avg_sentiment: float | None = None
    sentiment_by_segment: dict[str, float] = {}
    if deduplicated.sentiment_moments:
        signed_scores: list[int] = []
        seg_scores: dict[str, list[int]] = {}
        for m in deduplicated.sentiment_moments:
            if m.sentiment_raw_score is None:
                continue
            signed_scores.append(m.sentiment_raw_score)
            if m.segment_label:
                seg_scores.setdefault(m.segment_label, []).append(m.sentiment_raw_score)
        avg_sentiment = round(sum(signed_scores) / len(signed_scores), 2) if signed_scores else None
        sentiment_by_segment = {
            seg: round(sum(scores) / len(scores), 2)
            for seg, scores in seg_scores.items()
        }

    # Retry aggregation using typed fields
    total_retry_sequences = len(deduplicated.retry_moments)
    first_attempt_failure_count = sum(
        1 for m in deduplicated.retry_moments
        if m.retry_total_attempts is not None and m.retry_total_attempts > 1
    )

    # Verbal: top 5 notable quotes using typed fields
    actionable_verbal = [m for m in deduplicated.verbal_moments if m.verbal_is_actionable]
    top_verbal = sorted(deduplicated.verbal_moments, key=lambda m: m.severity_numeric, reverse=True)
    notable_quotes = [m.verbal_quote for m in (actionable_verbal or top_verbal)[:5] if m.verbal_quote]

    # Per-chunk coverage for optional agents
    agent_coverage = [
        ChunkAgentCoverage(
            chunk_index=analysis.chunk_index,
            friction=True,
            clarity=True,
            delight=True,
            quality=True,
            sentiment=analysis.sentiment is not None,
            retry=analysis.retry is not None,
            verbal=analysis.verbal is not None,
        )
        for analysis in analyses
    ]
```

**3.5c — Add the new fields** to the `VideoReport(...)` construction:

```python
        game_key=video.game_key,
        sentiment_moments=deduplicated.sentiment_moments,
        retry_moments=deduplicated.retry_moments,
        verbal_moments=deduplicated.verbal_moments,
        avg_sentiment=avg_sentiment,
        sentiment_by_segment=sentiment_by_segment,
        total_retry_sequences=total_retry_sequences,
        first_attempt_failure_count=first_attempt_failure_count,
        notable_quotes=notable_quotes,
        agent_coverage=agent_coverage,
```

### Step 3.6 — Modify `src/gamesight/pipeline/orchestrator.py`

**3.6a — Add imports:**

```python
from gamesight.config import normalize_game_key
from gamesight.pipeline.verification import verify_moments
from gamesight.pipeline.highlights import build_highlight_reel
from gamesight.pipeline.executive_pass import generate_executive_summary
```

**3.6b — When constructing `VideoInfo`, compute and store `game_key`:**

```python
        resolved_game_title = resolved_config.resolved_game_title(
            metadata.title if is_youtube_url(source) else input_path.stem
        )
        game_key = normalize_game_key(resolved_game_title)

        video = VideoInfo(
            video_id=video_id,
            source_type=source_type,
            source=source,
            filename=filename,
            title=resolved_game_title,
            game_key=game_key,
            duration_seconds=duration_seconds,
        )
```

**3.6c — Modify `process_video()`** — replace the section from `deduplicate_moments` through `return ProcessedVideo`:

```python
        deduplicated = deduplicate_moments(chunks, chunk_analyses, timeline)  # ADD timeline param
        verified = verify_moments(deduplicated)
        report = build_video_report(video=video, timeline=timeline, analyses=chunk_analyses, deduplicated=verified)
        highlights = build_highlight_reel(video, verified)
        report = report.model_copy(update={"highlights": highlights})
        try:
            executive = await generate_executive_summary(client, report, resolved_config.game_genre)
            report = report.model_copy(update={"executive": executive})
        except Exception:
            logger.warning("Executive summary generation failed, continuing without it.")
        return ProcessedVideo(video=video, timeline=timeline, chunk_analyses=chunk_analyses, report=report)
```

**3.6d — In `analyze_and_store()`**, add saves for new agent types after the existing 4 agent saves:

```python
            if chunk.sentiment:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="sentiment",
                    analysis=chunk.sentiment,
                )
            if chunk.retry:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="retry",
                    analysis=chunk.retry,
                )
            if chunk.verbal:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="verbal",
                    analysis=chunk.verbal,
                )
```

### Step 3.7 — Update `src/gamesight/pipeline/__init__.py`

Add imports and `__all__` entries for `verify_moments`, `build_highlight_reel`, `generate_executive_summary`.

---

## PHASE 4: Cross-Video Study Layer

**Depends on:** Phase 3 complete (needs enriched `VideoReport` with all new fields).

### Step 4.1 — Create `src/gamesight/prompts/study.py`

```python
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
```

### Step 4.2 — Create `src/gamesight/pipeline/study.py`

```python
"""Cross-video study aggregation.

Collects completed VideoReports from multiple sessions and produces
a StudyReport with segment-level fingerprints, stop-risk cohorts,
and LLM-synthesized cross-session insights.
"""

import json
from collections import Counter, defaultdict

import google.genai as genai

from gamesight.config import normalize_segment_label
from gamesight.gemini.generate import generate_structured
from gamesight.prompts.study import STUDY_SYNTHESIS_PROMPT
from gamesight.schemas.report import VideoReport
from gamesight.schemas.study import (
    CrossVideoInsight,
    CrossVideoSynthesis,
    SegmentFingerprint,
    StopRiskCohort,
    StudyReport,
)


def _report_has_agent_coverage(report: VideoReport, agent_name: str) -> bool:
    return any(getattr(coverage, agent_name) for coverage in report.agent_coverage)


def _build_segment_fingerprints(reports: list[VideoReport]) -> list[SegmentFingerprint]:
    """Group all canonical moments by segment_label across all reports."""
    seg_data: dict[str, dict] = defaultdict(lambda: {
        "sessions": set(),
        "friction_sessions": set(),
        "delight_sessions": set(),
        "friction_severities": [],
        "friction_sources": [],
        "delight_drivers": [],
        "sentiment_scores": [],
        "retry_attempts": [],
        "quit_signals": 0,
        "first_attempt_failures": 0,
        "retry_sessions": 0,
        "quotes": [],
    })

    for report in reports:
        session_id = report.video_id
        has_sentiment = _report_has_agent_coverage(report, "sentiment")
        has_retry = _report_has_agent_coverage(report, "retry")
        has_verbal = _report_has_agent_coverage(report, "verbal")
        for m in report.friction_moments:
            label = normalize_segment_label(m.segment_label)
            if label:
                d = seg_data[label]
                d["sessions"].add(session_id)
                d["friction_sessions"].add(session_id)
                d["friction_severities"].append(m.severity_numeric)
                d["friction_sources"].append(m.source_label)
        for m in report.delight_moments:
            label = normalize_segment_label(m.segment_label)
            if label:
                d = seg_data[label]
                d["sessions"].add(session_id)
                d["delight_sessions"].add(session_id)
                d["delight_drivers"].append(m.source_label)
        if has_sentiment:
            for m in report.sentiment_moments:
                label = normalize_segment_label(m.segment_label)
                if label is None or m.sentiment_raw_score is None:
                    continue
                d = seg_data[label]
                d["sessions"].add(session_id)
                d["sentiment_scores"].append(m.sentiment_raw_score)
        if has_retry:
            for m in report.retry_moments:
                label = normalize_segment_label(m.segment_label or m.source_label)
                if label:
                    d = seg_data[label]
                    d["sessions"].add(session_id)
                    d["retry_sessions"] += 1
                    if m.retry_total_attempts is not None:
                        d["retry_attempts"].append(m.retry_total_attempts)
                        if m.retry_total_attempts > 1:
                            d["first_attempt_failures"] += 1
                    if m.retry_quit_signal:
                        d["quit_signals"] += 1
        if has_verbal:
            for m in report.verbal_moments:
                label = normalize_segment_label(m.segment_label)
                if label and m.verbal_quote:
                    seg_data[label]["sessions"].add(session_id)
                    seg_data[label]["quotes"].append(m.verbal_quote)

    fingerprints: list[SegmentFingerprint] = []
    for label, d in seg_data.items():
        sessions_enc = len(d["sessions"])
        if sessions_enc < 1:
            continue
        friction_count = len(d["friction_sessions"])
        delight_count = len(d["delight_sessions"])
        friction_sources = Counter(d["friction_sources"])
        delight_drivers = Counter(d["delight_drivers"])
        sentiments = d["sentiment_scores"]
        retries = d["retry_attempts"]
        retry_sess = d["retry_sessions"]

        fingerprints.append(SegmentFingerprint(
            segment_label=label,
            sessions_encountered=sessions_enc,
            sessions_with_friction=friction_count,
            friction_rate=round(friction_count / sessions_enc, 3) if sessions_enc else 0.0,
            avg_friction_severity=round(sum(d["friction_severities"]) / len(d["friction_severities"]), 2) if d["friction_severities"] else 0.0,
            sessions_with_delight=delight_count,
            delight_rate=round(delight_count / sessions_enc, 3) if sessions_enc else 0.0,
            dominant_friction_source=friction_sources.most_common(1)[0][0] if friction_sources else None,
            dominant_delight_driver=delight_drivers.most_common(1)[0][0] if delight_drivers else None,
            avg_sentiment=round(sum(sentiments) / len(sentiments), 2) if sentiments else None,
            positive_sentiment_rate=round(sum(1 for s in sentiments if s > 0) / len(sentiments), 3) if sentiments else None,
            first_attempt_failure_rate=round(d["first_attempt_failures"] / retry_sess, 3) if retry_sess else None,
            avg_retry_attempts=round(sum(retries) / len(retries), 2) if retries else None,
            quit_signal_rate=round(d["quit_signals"] / retry_sess, 3) if retry_sess else None,
            representative_quotes=d["quotes"][:5],
        ))

    fingerprints.sort(key=lambda f: f.sessions_encountered, reverse=True)
    return fingerprints


def _build_stop_risk_cohorts(reports: list[VideoReport], fingerprints: list[SegmentFingerprint]) -> list[StopRiskCohort]:
    """Identify segments with high stop-risk patterns."""
    total = len(reports)
    cohorts: list[StopRiskCohort] = []
    for fp in fingerprints:
        if fp.friction_rate >= 0.3 and fp.sessions_encountered >= 2:
            cohorts.append(StopRiskCohort(
                trigger_segment=fp.segment_label,
                sessions_affected=fp.sessions_with_friction,
                total_sessions=total,
                percentage=round(fp.sessions_with_friction / total * 100, 1) if total else 0.0,
                common_pattern=f"Friction rate {fp.friction_rate:.0%}, avg severity {fp.avg_friction_severity:.1f}/10"
                    + (f", {fp.quit_signal_rate:.0%} quit signal rate" if fp.quit_signal_rate else ""),
                representative_quotes=fp.representative_quotes,
            ))
    cohorts.sort(key=lambda c: c.percentage, reverse=True)
    return cohorts[:5]


async def build_study_report(
    client: genai.Client,
    reports: list[VideoReport],
    game_key: str,
) -> StudyReport:
    """Aggregate multiple VideoReports into a cross-session StudyReport."""
    game_title = reports[0].game_title if reports else game_key
    fingerprints = _build_segment_fingerprints(reports)
    cohorts = _build_stop_risk_cohorts(reports, fingerprints)
    total_duration = sum(r.duration_seconds for r in reports) / 60.0

    # Prepare full stats for LLM synthesis. Do not trim inputs.
    stats_payload = {
        "game_key": game_key,
        "game_title": game_title,
        "total_sessions": len(reports),
        "total_duration_minutes": round(total_duration, 1),
        "segment_fingerprints": [fp.model_dump(mode="json") for fp in fingerprints],
        "stop_risk_cohorts": [c.model_dump() for c in cohorts],
        "full_session_reports": [report.model_dump(mode="json") for report in reports],
    }

    prompt = STUDY_SYNTHESIS_PROMPT.format(
        session_count=len(reports),
        game_title=game_title,
        study_json=json.dumps(stats_payload, indent=2),
    )
    synthesis = await generate_structured(
        client,
        contents=prompt,
        response_schema=CrossVideoSynthesis,
        thinking_level="medium",
    )

    return StudyReport(
        game_key=game_key,
        game_title=game_title,
        total_sessions=len(reports),
        total_duration_minutes=round(total_duration, 1),
        segment_fingerprints=fingerprints,
        stop_risk_cohorts=cohorts,
        insights=synthesis.insights,
        top_priorities=synthesis.top_priorities,
        executive_summary=synthesis.executive_summary,
    )


__all__ = ["build_study_report"]
```

### Step 4.3 — Modify `src/gamesight/db/database.py`

Add to `SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS study_reports (
    game_key TEXT PRIMARY KEY,
    game_title TEXT NOT NULL,
    report_json TEXT NOT NULL,
    session_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Step 4.4 — Modify `src/gamesight/db/repository.py`

Add imports:

```python
from gamesight.schemas.study import StudyReport
```

Add methods to `Repository`:

```python
    async def get_all_reports(self, game_key: str | None = None) -> list[VideoReport]:
        async with await get_connection(self.database_path) as db:
            if game_key:
                rows = await db.execute_fetchall(
                    "SELECT report_json FROM video_reports WHERE json_extract(report_json, '$.game_key') = ?",
                    (game_key,),
                )
            else:
                rows = await db.execute_fetchall("SELECT report_json FROM video_reports")
        return [VideoReport.model_validate_json(row["report_json"]) for row in rows]

    async def save_study_report(self, game_key: str, study: StudyReport) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """INSERT INTO study_reports (game_key, game_title, report_json, session_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(game_key) DO UPDATE SET
                       game_title = excluded.game_title,
                       report_json = excluded.report_json,
                       session_count = excluded.session_count""",
                (game_key, study.game_title, study.model_dump_json(), study.total_sessions),
            )
            await db.commit()

    async def get_study_report(self, game_key: str) -> StudyReport | None:
        row = await self._fetch_one(
            "SELECT report_json FROM study_reports WHERE game_key = ?", (game_key,)
        )
        if row is None:
            return None
        return StudyReport.model_validate_json(row["report_json"])
```

### Step 4.5 — Modify `src/gamesight/pipeline/orchestrator.py`

Add import:

```python
from gamesight.pipeline.study import build_study_report
```

Add new function:

```python
async def process_study(
    client: genai.Client,
    repository: Repository,
    game_key: str,
) -> "StudyReport":
    from gamesight.schemas.study import StudyReport
    reports = await repository.get_all_reports(game_key)
    if not reports:
        raise ValueError(f"No completed reports found for game_key: {game_key}")
    study = await build_study_report(client, reports, game_key)
    await repository.save_study_report(game_key, study)
    return study
```

Update `__all__` to include `"process_study"`.

### Step 4.6 — Modify `src/gamesight/api/routes.py`

Add imports:

```python
from gamesight.pipeline import process_study
from gamesight.schemas.executive import ExecutiveSummary
from gamesight.schemas.highlights import HighlightReel
from gamesight.schemas.study import StudyReport
```

Add routes:

```python
@router.get("/videos/{video_id}/sentiment")
async def get_sentiment(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.sentiment_moments]


@router.get("/videos/{video_id}/retry")
async def get_retry(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.retry_moments]


@router.get("/videos/{video_id}/verbal")
async def get_verbal(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.verbal_moments]


@router.get("/videos/{video_id}/highlights", response_model=HighlightReel)
async def get_highlights(video_id: str, request: Request) -> HighlightReel:
    report = await get_report(video_id, request)
    if report.highlights is None:
        raise HTTPException(status_code=404, detail="Highlights not found.")
    return report.highlights


@router.get("/videos/{video_id}/executive", response_model=ExecutiveSummary)
async def get_executive(video_id: str, request: Request) -> ExecutiveSummary:
    report = await get_report(video_id, request)
    if report.executive is None:
        raise HTTPException(status_code=404, detail="Executive summary not found.")
    return report.executive


@router.post("/studies/{game_key}/analyze", response_model=StudyReport)
async def analyze_study(game_key: str, request: Request) -> StudyReport:
    repository = _repository_from_request(request)
    client = _client_from_request(request)
    if client is None:
        raise HTTPException(status_code=503, detail="Gemini client is not configured.")
    return await process_study(client, repository, game_key)


@router.get("/studies/{game_key}", response_model=StudyReport)
async def get_study(game_key: str, request: Request) -> StudyReport:
    repository = _repository_from_request(request)
    study = await repository.get_study_report(game_key)
    if study is None:
        raise HTTPException(status_code=404, detail="Study report not found.")
    return study
```

---

## Dependency Graph

```
Phase 1 (Foundation)
  ├── 1.1  enums.py
  ├── 1.1a config.py
  ├── 1.2  timeline.py schema (depends on 1.1)
  ├── 1.3  timeline.py prompt
  ├── 1.5  schemas/sentiment.py (depends on 1.1)
  ├── 1.6  schemas/retry.py (depends on 1.1)
  ├── 1.7  schemas/verbal.py (depends on 1.1)
  ├── 1.8  schemas/executive.py
  ├── 1.9  schemas/highlights.py
  ├── 1.10 schemas/study.py (depends on 1.1)
  ├── 1.4  schemas/video.py (depends on 1.2, 1.5, 1.6, 1.7)
  ├── 1.11 schemas/report.py (depends on 1.8, 1.9)
  ├── 1.12 schemas/__init__.py (depends on all above)
  ├── 1.13 timeline_pass.py (depends on 1.2, 1.4, 1.1a)
  └── 1.14 gemini/debug.py
         │
Phase 2 (Agents) ← depends on Phase 1
  ├── 2.1  prompts/sentiment.py
  ├── 2.2  prompts/retry.py
  ├── 2.3  prompts/verbal.py
  ├── 2.4  prompts/__init__.py (depends on 2.1-2.3)
  ├── 2.5  chunk_pass.py (depends on 2.4, 1.1a, 1.4, 1.5, 1.6, 1.7)
  └── 2.6  dedup.py (depends on 1.1a, 1.4, 1.11)
         │
Phase 3 (Post-Processing) ← depends on Phase 2
  ├── 3.1  pipeline/verification.py (depends on 1.11)
  ├── 3.2  pipeline/highlights.py (depends on 1.9, 1.11)
  ├── 3.3  prompts/executive.py (depends on 1.8)
  ├── 3.4  pipeline/executive_pass.py (depends on 1.1a, 3.3)
  ├── 3.5  pipeline/aggregation.py (depends on 1.11)
  ├── 3.6  pipeline/orchestrator.py (depends on 1.1a, 3.1-3.5)
  └── 3.7  pipeline/__init__.py
         │
Phase 4 (Cross-Video) ← depends on Phase 3
  ├── 4.1  prompts/study.py
  ├── 4.2  pipeline/study.py (depends on 1.1a, 1.10, 4.1)
  ├── 4.3  db/database.py
  ├── 4.4  db/repository.py (depends on 4.3)
  ├── 4.5  pipeline/orchestrator.py (depends on 4.2, 4.4)
  └── 4.6  api/routes.py (depends on 4.5)
```

## File Summary

| Action | Count | Files |
|--------|:-----:|-------|
| **Create** | 15 | `schemas/sentiment.py`, `schemas/retry.py`, `schemas/verbal.py`, `schemas/executive.py`, `schemas/highlights.py`, `schemas/study.py`, `prompts/sentiment.py`, `prompts/retry.py`, `prompts/verbal.py`, `prompts/executive.py`, `prompts/study.py`, `pipeline/verification.py`, `pipeline/highlights.py`, `pipeline/executive_pass.py`, `pipeline/study.py` |
| **Modify** | 18 | `config.py`, `schemas/enums.py`, `schemas/timeline.py`, `schemas/video.py`, `schemas/report.py`, `schemas/__init__.py`, `prompts/timeline.py`, `prompts/__init__.py`, `pipeline/timeline_pass.py`, `pipeline/chunk_pass.py`, `pipeline/dedup.py`, `pipeline/aggregation.py`, `pipeline/orchestrator.py`, `pipeline/__init__.py`, `gemini/debug.py`, `api/routes.py`, `db/database.py`, `db/repository.py` |
