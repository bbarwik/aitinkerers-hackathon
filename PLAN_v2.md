# GameSight AI — Business Logic & Feature Specification

*Reference document for all pipeline features in the implementation plan. Describes WHAT the system does and WHY, at the business and product level.*

Implementation guardrails for all Gemini-facing schemas:
- Use `ConfigDict()` rather than `ConfigDict(extra="forbid")`
- Put observation / evidence fields before decision fields
- Do not use `ge` / `le` constraints on LLM-facing numeric fields
- Clamp numeric outputs post-call with named constants
- Runtime-only schemas may still use `extra="forbid"`

---

## Table of Contents

1. [Segment Labels (Timeline Enrichment)](#1-segment-labels-timeline-enrichment)
2. [Sentiment/Affect Agent](#2-sentimentaffect-agent)
3. [Retry/Death Loop Agent](#3-retrydeath-loop-agent)
4. [Verbal Feedback Agent](#4-verbal-feedback-agent)
5. [Evidence Verification Pass](#5-evidence-verification-pass)
6. [Enhanced Aggregation](#6-enhanced-aggregation)
7. [Highlight Reel Generator](#7-highlight-reel-generator)
8. [Executive Summary Pass](#8-executive-summary-pass)
9. [Cross-Video Study Aggregation](#9-cross-video-study-aggregation)
10. [Cross-Video Insight Synthesis](#10-cross-video-insight-synthesis)

---

## 1. Segment Labels (Timeline Enrichment)

### Feature Name and Purpose

**Segment Labels** add a short, reusable identifier to every significant moment in the gameplay timeline — names like `bridge_jump`, `boss_dragon_phase1`, or `tutorial_movement`. These labels create a shared vocabulary for talking about specific parts of a game across multiple play sessions.

**Question it answers for a game developer:** "Which specific part of my game is causing this problem, and does the same part cause problems for other players too?"

### Business Justification

Without segment labels, the system produces timestamped findings like "frustration at 12:34" — useful for one video, meaningless across fifty. A game developer thinks in terms of game areas and challenges ("the bridge section," "the dragon boss"), not raw timestamps. Segment labels bridge the gap between timestamp-centric analysis and developer-centric thinking.

More critically, segment labels are the **grouping key** for cross-video aggregation. Without them, there is no way to compute "68% of players failed the bridge jump on their first attempt" — because there's no way to know that the event at 12:34 in session A and the event at 8:17 in session B are about the same game element.

The current system has no equivalent. Timeline events have `event_description` (free text) and `phase_kind` (coarse category like "combat" or "puzzle"), but nothing that identifies a specific, named game area that can be matched across sessions.

### Detailed Behavior Specification

**When the timeline pass processes each chunk of video**, the AI model identifies significant moments (deaths, achievements, transitions, reactions). For each moment, in addition to existing fields, the model now assigns a `segment_label`.

**Label format requirements:**
- Short, snake_case identifiers (e.g., `bridge_jump`, not `The Tricky Bridge Jump At The End Of Level 3`)
- Reusable within a session — if the player returns to the same area, the same label is reused
- Consistent across sessions — the model should recognize that different players encountering the same game area should get the same label
- Specific enough to distinguish distinct challenges — `tutorial_room` and `tutorial_combat` are different labels, not both `tutorial`
- General enough to be matchable — minor spelling variations across sessions should be minimal

**The model has strong context for producing consistent labels** because it receives the full accumulated context from all previous chunks, including all previously used labels. For the first session of a game, labels are established organically. For subsequent sessions (processed independently), the model will tend to produce similar labels because it's observing the same game areas.

**Normalization rule:** Every emitted label is passed through `normalize_segment_label()` in the timeline pass, again in dedup, and again in study aggregation. This collapses casing and punctuation variants like `Bridge Jump`, `bridge-jump`, and `BRIDGE_JUMP` into the same canonical key `bridge_jump` without trying to do fuzzy semantic matching.

**Edge cases:**
- If the player is in a loading screen, menu, or non-gameplay state, the segment_label should reflect that (e.g., `main_menu`, `loading`, `inventory_management`)
- If the player is in a unique, one-time area that doesn't clearly map to a named challenge, use a descriptive label like `forest_clearing_01`
- Cutscenes get labeled by their narrative content: `intro_cutscene`, `boss_defeat_cutscene`

### Data Flow

```
Video chunk → Gemini (timeline pass) → TimelineMoment with segment_label
    → TimelineEvent (absolute timestamp + normalized segment_label)
    → Used by dedup to assign normalized segment_label to all CanonicalMoments
    → Used by cross-video aggregation to group findings by game area
```

### Quality Criteria

**Good output:** The bridge section of a platformer consistently gets labeled `bridge_jump` or `bridge_section` across different play sessions. A developer can filter all findings by this label and see every player's experience with that specific section.

**Bad output:** Labels like `gameplay_section_3`, `challenge`, or `part_where_player_dies` — these are too vague to be meaningful or matchable across sessions. Similarly bad: wildly different labels for the same area across sessions (`bridge_jump` in one, `canyon_crossing` in another, `level_3_gap` in a third).

**Failure mode:** Label inconsistency across sessions. Mitigated by the prompt's explicit instruction to use short, stable, reusable labels, and by the model's tendency to use obvious names for visually distinctive game areas.

### Relationships

- **Depends on:** Nothing new — extends the existing timeline pass
- **Depended on by:** Evidence Verification (for segment matching), Enhanced Aggregation (for per-segment stats), Highlight Reel (for categorization), Cross-Video Study Aggregation (critical — this is the grouping key), all new specialist agents (they inherit labels via timeline context)

### Hackathon Scoring Impact

- **Running Code (+0.1):** Small incremental improvement, but enables everything else
- **Innovation (+0.3):** Semantic video segmentation without any game SDK integration is novel
- **Impact (+0.5):** Directly enables the "68% failure rate on the bridge jump" demo stat — without labels, cross-video stats are impossible
- **Target judges:** Heitzeberg (makes the aggregate insight possible), Grabowski (structured, typed output), Vadi (Gemini understanding game structure from raw video)

---

## 2. Sentiment/Affect Agent

### Feature Name and Purpose

The **Sentiment Agent** is a new specialist that watches each video chunk and produces a **numeric emotional sentiment curve** — scoring the player's emotional state at regular intervals on a scale from -10 (rage/despair) to +10 (triumph/delight).

**Question it answers:** "How does the player *feel* at each moment, and how does that feeling change over time? Where are the emotional highs and lows?"

### Business Justification

The current system captures emotional signals indirectly — the Friction agent detects frustration, the Delight agent detects joy — but neither produces a continuous, quantified emotional timeline. A game developer asking "what's the overall player sentiment during combat?" cannot get a number from the current system. They get qualitative labels like "moderate frustration" or "strong engagement," which are useful but not aggregatable.

The Sentiment Agent fills three critical gaps:

1. **Quantified metrics for the demo.** The advisory documents specify that the demo must show "91% positive combat sentiment." This requires a numeric sentiment value per moment that can be filtered by game area and computed as a percentage. No existing agent produces this.

2. **Continuous coverage.** Existing agents only fire when something notable happens (a frustration moment, a delight moment). The sentiment agent samples at regular intervals (every 20-30 seconds), providing coverage of the "boring middle" — periods where nothing dramatic happens but the player's emotional baseline reveals important information about pacing and engagement.

3. **Emotional context for other findings.** When the Friction agent reports a frustration moment at 12:34, the sentiment curve provides context: was the player already in a negative state (suggesting accumulated frustration), or did this hit suddenly from a positive baseline (suggesting a sharp design problem)?

### Detailed Behavior Specification

**Sampling approach:** The agent samples sentiment at roughly 20-30 second intervals throughout each 5-minute chunk. For a full chunk, this produces 10-15 data points. This is denser than other agents (which produce 0-5 moments) because sentiment is a continuous signal, not a discrete event.

**Three-channel evidence model:** For each sample, the agent must observe and cite evidence from all available channels:
- **Visual gameplay:** What's happening on screen — success, failure, progress, stalling, exploration, combat
- **Audio:** Player voice tone, volume, word choice, breathing patterns, laughter, sighs, silence
- **Facecam (if visible):** Facial expression, posture shifts, gestures, eye movement

**Scoring scale:**

| Range | Label | Example Behaviors |
|---|---|---|
| -10 to -7 | Active frustration | Cursing, head in hands, threatening to quit, rage |
| -6 to -4 | Negative | Struggling, losing patience, annoyed confusion |
| -3 to -1 | Mildly negative | Minor setbacks, slight annoyance, mild impatience |
| 0 | Neutral | Focused, engaged, neither positive nor negative |
| +1 to +3 | Mildly positive | Steady progress, mild satisfaction, exploratory curiosity |
| +4 to +6 | Positive | Enjoying the experience, voluntary exploration, smiling |
| +7 to +10 | Peak positive | Laughing, celebrating, exclaiming, fist pump, triumph |

**Critical calibration rules** (these prevent the most common sentiment analysis errors):
- A player who dies but laughs and immediately retries is **positive** (+2 to +4), not negative. Death ≠ frustration.
- Focused silence during intense gameplay is **neutral to slightly positive** (0 to +2), not negative. Silence ≠ boredom.
- Resigned silence after repeated failure, with slumped posture or sighing, is **negative** (-3 to -6). Context distinguishes silence types.
- Idle menu browsing with no engagement signals is **neutral to slightly negative** (-1 to -2).

**Silence classification:** When the player is silent, the agent classifies the silence type (focused, resigned, confused, tense, idle) to justify the sentiment score. This is important because many gameplay sessions have long silent periods, and the type of silence carries very different emotional information.

**Per-chunk outputs:**
- List of 5-15 sentiment samples with timestamps, scores, emotions, and evidence
- Narrative sentiment curve description ("Player started neutral, rose to +6 during combat, crashed to -4 after the third bridge failure")
- Average sentiment for the chunk (single number, -10 to +10)
- Lowest and highest points with timestamps and causes
- Dominant emotion label for the chunk
- Recovery assessment: how quickly and fully the player bounces back from negative events

**Post-parse handling:** The sentiment schema keeps evidence fields before decision fields and does not use numeric `ge` / `le` constraints. After the Gemini call returns, scores are clamped in code. When a sentiment sample becomes a canonical moment, the system stores both `severity_numeric=abs(raw_score)` for ranking and `sentiment_raw_score=raw_score` for actual math.

### Data Flow

```
Video chunk + session context → Gemini (sentiment agent, parallel with other specialists)
    → SentimentChunkAnalysis (per-chunk)
    → CanonicalMoments (via dedup, with absolute timestamps + segment labels,
      plus typed `sentiment_raw_score`)
    → Aggregation: avg_sentiment per session, sentiment_by_segment map,
      both computed from typed signed scores
    → Cross-video: per-segment sentiment distributions across sessions
```

### Quality Criteria

**Good output:** A 5-minute chunk produces 12 sentiment samples, each with a score that matches the observable evidence. The curve shows a clear narrative — "neutral during exploration (0 to +2), spike to +7 during a satisfying combat sequence, drop to -3 during a confusing puzzle." The average sentiment for a mostly-positive chunk is +3 to +5.

**Bad output:** All samples at 0 ("neutral") with no variation — the agent is failing to observe emotional signals. Or: every death is scored -8 regardless of player reaction — the agent is using game events as a proxy for emotion instead of observing the player. Or: sentiment scores that contradict observable evidence (player is laughing and scored -5).

**Failure modes:**
- **No facecam visible:** Agent relies on audio and gameplay outcomes only. This is still useful but less precise. The `confidence` field should be "medium" or "low."
- **No player audio:** Agent relies on gameplay and facecam only. Silence classification becomes the primary tool.
- **Recording is gameplay-only (no facecam, no audio):** Agent can only infer sentiment from gameplay patterns (death frequency, pause frequency, exploration patterns). Scores should cluster near 0 with low confidence.
- **Recoverable agent failure:** Optional-agent wrappers only downgrade on recoverable failures (`GeminiSafetyError`, schema validation errors, or bad values). Broader infrastructure bugs still fail loudly rather than being silently hidden.

### Relationships

- **Depends on:** Segment Labels (for sentiment_by_segment computation), existing warmup/cache infrastructure
- **Depended on by:** Enhanced Aggregation (avg_sentiment, sentiment_by_segment), Highlight Reel (sentiment swings as highlight candidates), Executive Summary (sentiment trends as key findings), Cross-Video Study (per-segment sentiment distributions)

### Hackathon Scoring Impact

- **Innovation (+0.5):** Numeric sentiment scoring from raw gameplay video is novel — no existing game analytics tool does this
- **Theme (+0.6):** This is the **deepest use of Gemini's multimodal capabilities** — simultaneously processing video frames, audio tone, and facecam expressions to produce a single numeric score. This is the feature that most clearly answers Amit Vadi's test: "Is this only possible with Gemini?"
- **Impact (+0.3):** Enables the "91% positive combat sentiment" demo stat; enables sentiment-based filtering and comparison
- **Target judges:** Vadi (Gemini multimodal indispensability), Warda (autonomous insight generation), Grabowski (measurable, typed output)

---

## 3. Retry/Death Loop Agent

### Feature Name and Purpose

The **Retry Agent** watches each video chunk and identifies **retry patterns** — moments where the player attempts the same challenge multiple times. It tracks each individual attempt, whether the player changes strategy, how frustration evolves across attempts, and whether the player ultimately succeeds or gives up.

**Question it answers:** "Where do players get stuck? How many times do they try before succeeding or quitting? Is the difficulty well-tuned?"

### Business Justification

Difficulty tuning is the #1 actionable feedback loop in game development. Every game designer needs to know: "Is this section too hard? How hard?" The current system detects frustration moments but cannot distinguish between a single annoying death and a 15-attempt grind on the same obstacle.

The Retry Agent fills the most critical gap for the demo narrative. The FINAL_REPORT specifies three key statistics:
- **"68% first-attempt failure rate"** — requires counting how many players fail a specific challenge on their first try
- **"40% more likely to quit after 3 failures"** — requires counting retries per player per challenge
- **"bridge jump"** as the demo focal point — requires identifying specific challenges by name

None of these can be produced without a dedicated agent that watches the video for retry patterns. The Friction agent only reports "this moment was frustrating" — it doesn't count attempts, track success/failure sequences, or identify the same challenge being retried.

**Why this must be a video-watching agent (not a post-processing step):** Retry detection requires seeing visual evidence that the player returned to the same location — respawning at a checkpoint, falling off the same platform, facing the same enemy. A text-based post-processing step working from timeline events can sometimes infer retries (multiple deaths in the same phase), but it misses the nuance: it can't count precise attempt numbers, observe strategy changes between attempts, or detect quit signals that happen during (not after) a retry sequence.

### Detailed Behavior Specification

**What constitutes a retry sequence:**
- The player dies and respawns at the same area (most common)
- The player fails a jump, puzzle, or combat encounter and physically returns to try again
- The player's character is reset to a previous position after failure
- The player manually reloads a save or checkpoint

**What does NOT constitute a retry sequence:**
- Dying once and immediately succeeding on the second try (this is noted as a single retry, not a concerning pattern)
- Exploring the same area multiple times voluntarily (exploration ≠ retry)
- Returning to a hub area between different objectives

**For each retry sequence, the agent tracks:**

| Field | Purpose |
|---|---|
| `challenge_name` | Snake_case label matching segment_labels from the timeline (e.g., `bridge_jump`) — this is the cross-video grouping key |
| `challenge_location` | Where in the game this occurs (descriptive, for human readability) |
| `total_attempts` | How many times the player tried |
| Per-attempt: `outcome` | died, failed, succeeded, or abandoned |
| Per-attempt: `duration_seconds` | How long each attempt lasted |
| Per-attempt: `strategy_change` | Whether the player tried a different approach |
| Per-attempt: `player_reaction` | Observable reaction (frustration, determination, humor) |
| `final_outcome` | succeeded, abandoned, or still_trying (at chunk end) |
| `frustration_escalation` | How frustration changed: escalating, stable, de-escalating, mixed |
| `quit_signal` | True if the player showed signs of wanting to stop playing entirely |

**Quit signal detection criteria:**
- Player says something like "I'm done," "this is impossible," or "I give up"
- Extended pause (>15 seconds) with no input after a failure
- Player opens the main menu or settings after a failure (potential rage-quit precursor)
- Visible body language: head in hands, leaning back, looking away from screen, checking phone
- Player begins playing noticeably less carefully (rushing into deaths, not trying)

`quit_signal` should only be `true` when evidence clearly suggests the player is considering stopping **the entire game**, not just taking a brief break or reconsidering strategy.

**Additional per-chunk metrics:**
- `total_deaths_or_failures`: Count of all deaths/failures, even those that don't form retry sequences
- `first_attempt_successes`: Count of challenges cleared on the first try — this is valuable data about well-tuned difficulty
- `progression_rate`: How efficiently the player progresses (smooth / moderate_friction / heavily_blocked)

**Canonical retry typing:** When a retry sequence is converted into a canonical moment, the system preserves typed fields `retry_total_attempts`, `retry_quit_signal`, and `retry_final_outcome`. Severity for ranking is computed in code with named constants: `RETRY_ATTEMPT_SEVERITY_WEIGHT=2`, `RETRY_QUIT_SIGNAL_SEVERITY_BONUS=3`, capped by `MAX_SEVERITY_NUMERIC=10`.

**Edge cases:**
- A retry sequence that spans a chunk boundary (player starts retrying at 4:30 and continues into the next chunk): each chunk reports its portion independently. The same `challenge_name` appears in both chunks' analyses. The dedup and aggregation layers merge them.
- A very long retry sequence (10+ attempts): report all attempts up to a reasonable limit. The `total_attempts` count is the key metric; individual attempt details beyond ~8 are less useful.
- Player succeeds after one retry: this is a minor retry sequence (total_attempts=2). Still reported, but with low severity. Single retries are normal and expected.

### Data Flow

```
Video chunk + session context → Gemini (retry agent, parallel with other specialists)
    → RetryChunkAnalysis (per-chunk)
    → CanonicalMoments (one per RetrySequence, with normalized challenge_name as segment_label
      and typed retry fields preserved)
    → Aggregation: total_retry_sequences, first_attempt_failure_count
    → Cross-video: per-challenge failure rates, quit-after-N-failures statistics
```

### Quality Criteria

**Good output:** In a video where the player dies 5 times on a bridge jump, the retry agent reports a single RetrySequence with `challenge_name="bridge_jump"`, `total_attempts=5`, detailed per-attempt tracking showing strategy changes ("jumped from the left," "tried running start"), `frustration_escalation="escalating"`, and `final_outcome="succeeded"` when the player finally clears it.

**Bad output:** Each individual death reported as a separate retry sequence instead of one coherent sequence. Or: the agent reports a retry sequence for a combat encounter where the player intentionally re-engages different enemy groups (exploration, not retry). Or: `total_attempts=1` — a single attempt is not a retry sequence.

**Failure modes:**
- **Game has invisible checkpoints:** The agent may not realize the player respawned at the same location. Mitigated by observing the visual environment returning to a previously-seen state.
- **Safety filter blocks violent content:** Some intense death sequences may trigger Gemini's safety filter. The agent is wrapped in a safe handler that returns None on failure — the chunk's retry data is simply missing, not the entire analysis.
- **Coverage gap:** If the retry agent is skipped for a chunk or session, the study layer records that gap explicitly instead of treating the missing data as zero retries.

### Relationships

- **Depends on:** Segment Labels (for consistent challenge_name across sessions), existing warmup/cache infrastructure
- **Depended on by:** Enhanced Aggregation (retry statistics), Highlight Reel (retry loops as high-importance moments), Executive Summary (retry findings as key findings), Cross-Video Study (per-challenge failure rates — THE key demo statistic)

### Hackathon Scoring Impact

- **Innovation (+0.7):** Retry detection from video without any game telemetry is genuinely novel. No existing tool does this.
- **Impact (+0.8):** Directly produces the demo's centerpiece statistics. Without this agent, the "68% failure rate" and "40% quit after 3 failures" claims cannot be backed by data.
- **Theme (+0.3):** Requires visual understanding of game state (respawn detection, checkpoint recognition)
- **Target judges:** ALL judges — the bridge jump scenario is the narrative spine of the entire demo. Heitzeberg (the "aha" moment), Skowronski (quantified business value), Reddy (operational workflow insight), Warda (proactive intelligence)

---

## 4. Verbal Feedback Agent

### Feature Name and Purpose

The **Verbal Feedback Agent** systematically extracts and classifies **everything the player says aloud** during gameplay. It transcribes quotes, categorizes them by type (complaint, praise, question, suggestion, strategy narration, emotional reaction), rates their sentiment, and flags quotes that are directly actionable for game designers.

**Question it answers:** "What did players actually say about this game? What did they ask, complain about, praise, and suggest?"

### Business Justification

Player quotes are the most emotionally compelling evidence in a playtest report. "68% failure rate" is a number. *"I keep falling off this bridge — this is so unfair"* is a human voice. Judges, stakeholders, and game directors respond to quotes more viscerally than statistics.

The current system captures player quotes incidentally — the `verbal_feedback` field on existing moment schemas records quotes when they coincide with a friction, clarity, delight, or quality event. But this misses:

1. **Quotes that don't coincide with classified events.** A player saying "They should add a checkpoint here" while calmly walking (no frustration event detected) is a design suggestion that the current system would miss entirely.
2. **Systematic coverage.** The current system captures 0-5 quotes per chunk as part of other analyses. A talkative player might say 30 notable things in 5 minutes — feedback about mechanics, narration of strategy, reactions to surprises, suggestions for improvement.
3. **Classification and sentiment.** Current quotes are raw strings with no metadata. The Verbal Agent adds sentiment scoring, category classification, voice tone, and actionability flags.

**Why this showcases Gemini's multimodal strength:** The Verbal Agent relies on Gemini's native audio understanding — it listens to the player's voice directly from the gameplay video, without a separate transcription pipeline (no Whisper, no speech-to-text API). This is the feature that most directly demonstrates "only possible with Gemini" because no other multimodal model processes hour-long video with audio natively.

### Detailed Behavior Specification

**What to capture:**

| Category | Description | Example |
|---|---|---|
| COMPLAINT | Negative feedback about mechanics, difficulty, design | "This is so unfair," "Why won't it let me jump?" |
| PRAISE | Positive feedback about features, visuals, moments | "That's so cool," "I love the art style" |
| QUESTION | Utterances revealing confusion or uncertainty | "Where do I go?", "What does this button do?" |
| NARRATION | Player describing what they're doing or planning | "Let me try going left this time" |
| STRATEGY | Explicit strategy formulation | "Maybe if I use the shield first..." |
| SUGGESTION | Direct improvement recommendations | "They should add a checkpoint here" |
| REACTION | Emotional exclamations without specific content | "Oh!", "No no no!", "YES!", laughter, sighs |

**For each verbal moment:**
- `quote`: The exact words, as close to verbatim as possible
- `category`: One of the categories above
- `sentiment_score`: -5 (very negative) to +5 (very positive)
- `voice_tone`: angry, frustrated, confused, neutral, amused, excited, sarcastic, resigned
- `game_context`: What was happening on screen at the time
- `is_actionable`: True if this quote implies a specific design change
- `actionable_insight`: If actionable, the design implication in one sentence (e.g., "Add a checkpoint before the bridge section")

**Per-chunk metadata:**
- `has_player_audio`: Whether any player speech was detected at all
- `total_speech_segments`: Approximate count of distinct speech segments
- `talk_ratio`: silent, occasional, frequent, constant
- `dominant_tone`: Overall tone of feedback in this chunk
- `most_actionable_quote`: The single most design-relevant thing said

**Canonical verbal typing:** When verbal moments are deduplicated, the system stores `verbal_is_actionable` and `verbal_quote` as typed fields on the canonical record. Quote ranking uses those fields directly rather than brittle string matching. Verbal intensity for highlight ranking is derived with `VERBAL_SEVERITY_WEIGHT=2`, capped by `MAX_SEVERITY_NUMERIC=10`.

**What to ignore:**
- Background game music and sound effects
- NPC dialogue (unless the player directly responds to or comments on it)
- Non-player voices (friends in the room, stream chat read-aloud) — unless they're commenting on the game

**Edge case — no speech:** Many gameplay recordings have no player audio. The agent should recognize this quickly, set `has_player_audio=false`, return an empty moments list, and note `talk_ratio="silent"`. This is valid data, not a failure.

### Data Flow

```
Video chunk + session context → Gemini (verbal agent, parallel with other specialists)
    → VerbalChunkAnalysis (per-chunk)
    → CanonicalMoments (one per quote, with category as source_label
      and typed quote/actionability fields preserved)
    → Aggregation: top 5 notable quotes, actionable quote list
    → Cross-video: recurring quotes/themes across sessions, quote-backed statistics
```

### Quality Criteria

**Good output:** A chatty player's 5-minute chunk produces 8-12 verbal moments spanning multiple categories. Actionable quotes are correctly flagged — "they should add a checkpoint" is actionable, "oh no I died" is not. Sentiment scores match voice tone — a sarcastic "great, another death" is scored negative (-2 to -3), not positive.

**Bad output:** Transcription of NPC dialogue or game sound effects rather than player speech. Or: every utterance classified as "reaction" with no sentiment differentiation. Or: quotes that don't match what the player actually said (hallucinated quotes).

**Failure mode:** Player speaks a language the model struggles with. Gemini supports many languages but accuracy varies. The agent should note low confidence when transcription is uncertain.

### Relationships

- **Depends on:** Existing warmup/cache infrastructure, session context for game awareness
- **Depended on by:** Enhanced Aggregation (notable_quotes list), Highlight Reel (verbal moments as candidates), Executive Summary (quotes as evidence in findings), Cross-Video Study (representative_quotes per segment, quote-backed statistics)

### Hackathon Scoring Impact

- **Theme (+0.6):** **The strongest Gemini multimodal showcase.** Audio understanding directly from video — no transcription pipeline, no external STT service. This is the feature to point to when Vadi asks "Why Gemini?"
- **Innovation (+0.3):** Systematic verbal feedback extraction from gameplay video is novel
- **Impact (+0.3):** Player quotes are the most emotionally resonant evidence in the demo. "I keep falling off this bridge" at 0:20-0:35 in the demo script comes from this agent.
- **Target judges:** Vadi (Gemini audio indispensability), Chrobok (evidence quality — direct quotes are the strongest evidence), Heitzeberg (human voice makes the product feel real)

---

## 5. Evidence Verification Pass

### Feature Name and Purpose

The **Evidence Verification Pass** is a post-processing step that scores the **confidence** of every finding by checking whether multiple independent agents flagged the same moment in time. A frustration event at 12:34 that's also flagged by the sentiment agent (emotional dip), the retry agent (death #3), and the verbal agent ("this is so unfair") gets a much higher confidence score than a lone observation.

**Question it answers:** "How confident should we be in each finding? Which findings are backed by the most evidence?"

### Business Justification

AI-generated analysis faces a fundamental trust problem: how do you know the model isn't hallucinating? The advisory documents emphasize this repeatedly — Chrobok's #1 concern is "where's the evidence?", and the scripted answer is "every claim is constrained by a Pydantic schema requiring evidence."

Evidence Verification goes further: it doesn't just require evidence, it **cross-validates evidence across independent agents**. Each specialist agent runs independently — the Friction agent doesn't know what the Sentiment agent found. When multiple independent observers flag the same timestamp, that's convergent evidence.

This directly addresses the "hallucination" objection: a finding corroborated by 3+ independent AI agents with different analytical lenses is far more credible than a single observation.

### Detailed Behavior Specification

**Algorithm:** For each canonical moment across all agent types:

1. Look at all other moments from **different** agent types within a ±15-second window
2. If both moments have a `segment_label`, require the labels to match before treating them as corroboration
3. Count how many distinct agent types have a finding in that window
4. Compute confidence score:
   - Base: 0.50 (single-agent observation)
   - +0.15 per corroborating agent type (e.g., if friction + sentiment + verbal all fire at the same time: 0.50 + 0.45 = 0.95)
   - +0.10 bonus if the moment carries a typed direct player quote (`verbal_quote`) because quotes are strong evidence
   - Cap at 1.00
5. Record the list of corroborating agent types

**Window size rationale:** ±15 seconds accounts for the fact that different agents may timestamp the "same" event slightly differently. A death at 12:34 might be flagged by the friction agent at 12:34, the sentiment agent at 12:25 (when frustration started building), and the verbal agent at 12:40 (when the player cursed after dying). All are about the same event, but only if they also refer to the same segment when both moments are labeled.

**Output:** Every `CanonicalMoment` in the system gets a `confidence_score` (0.0 to 1.0) and a `corroborating_agents` list. These values are used by downstream features (highlights, executive summary, cross-video) to weight findings appropriately.

**Edge cases:**
- A moment with no corroboration (confidence 0.50) is not wrong — it's just less certain. Many valid findings only show up in one agent (a cosmetic bug detected by the quality agent doesn't necessarily cause a sentiment dip).
- Dense event clusters (boss fight with death, frustration, cursing, and sentiment crash all within 15 seconds) will produce high confidence scores for all moments in the cluster. This is correct — high-activity moments typically are the most important.

### Data Flow

```
DeduplicatedAnalyses (all 7 moment lists) → Verification pass
    → New DeduplicatedAnalyses with confidence_score and corroborating_agents populated
    → Used by Highlight Reel (importance scoring), Executive Summary (evidence strength),
      Cross-Video Study (weighted aggregation)
```

### Quality Criteria

**Good output:** A major frustration moment where the player dies, curses, shows facial frustration, and has a sentiment score of -7 gets confidence 0.95 with corroborating_agents = ["sentiment", "verbal", "retry"]. A cosmetic graphical glitch the player doesn't notice gets confidence 0.50 with no corroboration.

**Bad output:** All moments at 0.50 (verification pass didn't run or window too small). Or: high confidence on a moment where the "corroboration" is actually about different events that happen to be nearby in time.

### Relationships

- **Depends on:** All 7 agent types having been processed and deduplicated
- **Depended on by:** Highlight Reel (uses confidence in importance scoring), Executive Summary (cites confidence levels), Cross-Video Study (can weight high-confidence findings more heavily)

### Hackathon Scoring Impact

- **Running Code (+0.2):** Shows engineering rigor — the system doesn't just produce findings, it validates them
- **Innovation (+0.3):** Cross-agent temporal correlation for confidence scoring is a novel approach to AI output validation
- **Target judges:** Chrobok (his #1 concern is evidence quality — "every claim requires evidence"), Grabowski (engineering maturity — typed, measurable confidence), Reddy (operational trust — "can I act on this?")

---

## 6. Enhanced Aggregation

### Feature Name and Purpose

**Enhanced Aggregation** extends the existing report-building step to incorporate data from all new agents. It computes session-level summary statistics: average sentiment, per-segment sentiment breakdowns, retry counts, first-attempt failure counts, and curated notable quotes.

**Question it answers:** "Give me the summary numbers for this entire session."

### Business Justification

Without aggregation, the new agents produce per-chunk data but no session-level view. A game developer doesn't want to browse 15 chunks of sentiment samples — they want "average sentiment: +3.2, combat sentiment: +7.1, bridge sentiment: -2.8." Aggregation transforms granular per-moment data into the actionable session-level metrics that the demo depends on.

### Detailed Behavior Specification

**New metrics computed:**

| Metric | Computation | Purpose |
|---|---|---|
| `avg_sentiment` | Mean of typed `sentiment_raw_score` across the session | Overall session emotional health |
| `sentiment_by_segment` | Group sentiment moments by segment_label, compute mean score per segment | "Combat: +7.1, Bridge: -2.8" — enables per-area comparison |
| `total_retry_sequences` | Count of all retry CanonicalMoments | "12 retry sequences across the session" |
| `first_attempt_failure_count` | Count of retry sequences where typed `retry_total_attempts > 1` | "Players failed on first attempt at 8 challenges" |
| `notable_quotes` | Top 5 verbal moments ranked by typed actionability first, then by sentiment magnitude | "The 5 most design-relevant things the player said" |
| `agent_coverage` | One `ChunkAgentCoverage` record per chunk showing which optional agents succeeded | Prevents silent agent skips from biasing study denominators |

**Sentiment sign preservation:** The `CanonicalMoment.severity_numeric` is always positive because it's `abs(raw_score)` and is used for ranking and highlighting only. The signed value is preserved separately in `sentiment_raw_score` and used directly for all averages and segment math.

**Notable quote selection:** Prioritize quotes flagged as actionable via the typed `verbal_is_actionable` field. If fewer than 5 actionable quotes exist, fill remaining slots with the highest-magnitude verbal moments. This ensures the quote list surfaces design suggestions first, emotional reactions second.

**Session identity:** Every `VideoReport` carries both a human-readable `game_title` and a normalized `game_key`. The title is for display; the key is for cross-session grouping and API lookup.

### Data Flow

```
Verified DeduplicatedAnalyses + ChunkAnalysisBundles → build_video_report()
    → VideoReport with new fields populated (avg_sentiment, sentiment_by_segment,
      total_retry_sequences, first_attempt_failure_count, notable_quotes,
      plus all new moment lists)
```

### Quality Criteria

**Good output:** A session with mostly positive gameplay and one frustrating section produces `avg_sentiment=+2.8`, `sentiment_by_segment={"combat": 7.1, "bridge_jump": -2.8, "exploration": 3.5}`, `total_retry_sequences=3`, `notable_quotes=["They should add a checkpoint here", "The combos feel incredible", ...]`.

**Bad output:** `avg_sentiment=0.0` when the session clearly had emotional highs and lows (aggregation bug — signed `sentiment_raw_score` was lost or ignored). Or: `notable_quotes` containing mundane narration instead of actionable feedback.

### Relationships

- **Depends on:** Sentiment, Retry, and Verbal agents having produced data; Evidence Verification having run
- **Depended on by:** Executive Summary (reads aggregated stats), Cross-Video Study (reads per-session reports with aggregated data)

### Hackathon Scoring Impact

- **Running Code (+0.2):** Completeness — all data is summarized, not just the original 4 agents
- **Impact (+0.3):** Produces the specific numbers the demo needs. `sentiment_by_segment` directly enables "Combat: 91% positive, Bridge: 32% positive" in the dashboard.
- **Target judges:** Grabowski (measurable metrics), Skowronski (business value is in the aggregates), Nowosielski (instant comprehension from summary numbers)

---

## 7. Highlight Reel Generator

### Feature Name and Purpose

The **Highlight Reel Generator** curates the **top 10 most significant moments** from the entire session across all analysis dimensions, ranked by importance. Each highlight includes a timestamp, clip boundaries (for "jump to this moment" functionality), a human-readable headline, and the evidence behind it.

**Question it answers:** "I have 60 minutes of gameplay footage. Which 10 moments should I actually watch?"

### Business Justification

A QA director reviewing playtest results doesn't have time to read through 50+ individual findings. They need a prioritized "watch list" — the moments that matter most, ranked by importance, with enough context to decide whether each one needs attention.

The current system produces flat lists of moments sorted chronologically. The Highlight Reel adds editorial judgment: "this is the #1 most important moment in the session, and here's why." This is the difference between a data dump and an analyst's recommendation.

From a demo perspective, the highlight reel enables the "jump to this moment" interaction — the director sees a ranked list, clicks on #1, and watches the 20-second clip around that moment. This is a natural, impressive workflow to demonstrate on stage.

### Detailed Behavior Specification

**Importance scoring formula:**

```
importance = severity_numeric × agent_weight × corroboration_bonus
```

Where:
- `severity_numeric`: 0-10 scale from each agent's analysis
- `agent_weight`: How impactful each agent type's findings typically are:
  - Retry: 1.3 (directly maps to demo's key metric)
  - Friction: 1.2 (stop-risk is critical)
  - Quality: 1.1 (bugs need fixing)
  - Clarity: 1.0 (confusion is important but less urgent)
  - Verbal: 0.9 (quotes are compelling evidence)
  - Delight: 0.8 (positive moments are lower priority for "fix" recommendations)
  - Sentiment: 0.7 (sentiment swings are context, not standalone findings)
- `corroboration_bonus`: `1.0 + 0.3 × len(corroborating_agents)` — multi-agent moments get boosted

**Clustering:** Moments within 30 seconds of each other are clustered. Only the highest-scored moment from each cluster makes the highlight reel. This prevents the top 10 from being 10 moments from the same 30-second crash.

**Clip boundaries:** Each highlight includes `clip_start_seconds` (10 seconds before the moment) and `clip_end_seconds` (10 seconds after), clamped to video boundaries. This provides enough context to understand what happened.

**Category mapping:** Each highlight is labeled by its primary category:
- friction → "critical_friction"
- clarity → "clarity_failure"
- delight → "player_delight"
- quality → "bug"
- sentiment → "sentiment_swing"
- retry → "retry_loop"
- verbal → "player_feedback"

**One-line verdict:** A single sentence summarizing the session, derived from the #1 highlight's summary. This appears as the headline in the report: "Critical difficulty spike at Level 3 bridge — 5 retry attempts with quit signal detected."

### Data Flow

```
Verified DeduplicatedAnalyses + VideoInfo → build_highlight_reel()
    → HighlightReel (top 10 ranked moments with clip boundaries)
    → Attached to VideoReport.highlights
```

### Quality Criteria

**Good output:** The top highlight is the session's most critical issue (e.g., a 5-attempt retry loop at the bridge with quit signal). The #2 and #3 highlights are other high-severity issues from different parts of the session. Later highlights include mix of friction, delight, and quality moments. No two highlights are from the same 30-second window.

**Bad output:** All 10 highlights from the same 2-minute section (clustering failed). Or: a mild cosmetic glitch ranked above a quit-signal retry loop (weights miscalibrated). Or: 0 highlights when the session clearly had significant events.

### Relationships

- **Depends on:** Evidence Verification (uses confidence_score and corroborating_agents for scoring)
- **Depended on by:** Executive Summary (may reference top highlights), Video Report (attached as field)

### Hackathon Scoring Impact

- **Running Code (+0.3):** Shows completeness and polish — the system doesn't just analyze, it curates
- **Impact (+0.3):** Enables the "jump to this moment" demo interaction. Game developers would genuinely use this daily.
- **Target judges:** Reddy (operational workflow — QA lead reviews highlights, not raw data), Nowosielski (instant comprehension), Heitzeberg (product completeness)

---

## 8. Executive Summary Pass

### Feature Name and Purpose

The **Executive Summary** is a Gemini-powered synthesis pass that reads the complete session report (all moments, statistics, timeline) and produces a **narrative assessment**: a session health score (0-100), a three-paragraph executive summary, 3-5 prioritized key findings with evidence citations, ranked action items, and one cross-dimensional insight.

**Question it answers:** "What's the bottom line? What should we do first, and why?"

### Business Justification

The current report is a structured data object — lists of moments, counters of sources, ordinal severity labels. It's machine-readable but not human-readable. A game director who opens this report wants to read three paragraphs and know what to do, not parse JSON.

More importantly, the Executive Summary is the only feature that can **discover cross-dimensional patterns** — connections between findings from different agents. For example: "The clarity failure at 04:12 (player didn't understand the grapple mechanic) directly caused the 5-attempt retry loop at 04:45 (player couldn't use grapple to cross the bridge), which triggered the quit signal at 05:10. Fixing the tutorial gap would eliminate both the retry loop and the stop-risk." No individual agent can see this chain — the Clarity agent sees confusion, the Retry agent sees attempts, the Friction agent sees quit risk. Only a synthesis pass that reads all findings together can connect the dots.

### Detailed Behavior Specification

**Input:** The complete `VideoReport` serialized as JSON (all moments, statistics, timeline, highlights). This is a text-only input — no video processing, making this call very cheap (~$0.01).

**Outputs:**

| Field | Description |
|---|---|
| `executive_summary` | Three short paragraphs: (1) factual session overview, (2) critical issues requiring attention, (3) strengths to protect and expand |
| `key_findings` | 3-5 findings, each with: the insight, evidence summary with timestamps, affected timestamps list, severity (critical/important/notable), and recommended action |
| `priority_actions` | Ranked list of concrete development actions, most urgent first. Must be specific: "Add checkpoint before bridge_jump" not "Improve difficulty curve" |
| `cross_dimensional_insight` | One non-obvious pattern connecting multiple analysis dimensions — the "aha" moment |
| `session_health_score` | Integer 0-100. 100 = flawless player experience. 50 = significant issues but playable. 0 = unplayable. This is clamped after the LLM call rather than schema-constrained. |

**Quality requirements for the LLM output:**
- Every claim must cite specific timestamps from the report data
- Findings must be prioritized by player impact, not frequency
- Key findings should preferentially surface patterns that cross multiple agent dimensions
- Priority actions must be concrete and actionable ("add X," "fix Y," "remove Z")
- The cross_dimensional_insight must connect at least two different agent types' findings

**Health score calibration:**
- 90-100: Smooth session, no friction above minor, strong engagement throughout
- 70-89: Some friction points but player persisted and had positive moments
- 50-69: Significant issues — retry loops with quit signals, extended confusion, major friction
- 30-49: Severe issues — multiple quit signals, very low sentiment, progression blockers
- 0-29: Session was unplayable — bugs blocking progress, player gave up

### Data Flow

```
VideoReport (complete, with all aggregated stats) → Gemini (text-only, structured output)
    → ExecutiveSummary
    → Attached to VideoReport.executive
```

### Quality Criteria

**Good output:** Health score accurately reflects the session (a session with a severe bridge problem and great combat gets ~55, not 90 or 20). Key findings correctly identify the most impactful issues. The cross_dimensional_insight connects findings in a non-obvious way that a human reading the raw data might miss.

**Bad output:** Generic findings like "The session had some frustration moments" without specific timestamps or evidence. Or: health score doesn't match the severity of issues found (90 for a session with 5 quit signals). Or: cross_dimensional_insight is actually obvious ("The player was frustrated at the bridge" — that's not cross-dimensional).

**Failure mode:** The LLM synthesis call fails (API error, safety filter, timeout). This is wrapped in a try/except — the report is still complete without the executive summary. The executive field will be None.

### Relationships

- **Depends on:** Enhanced Aggregation (needs the full report with all stats), Highlight Reel (may reference top highlights)
- **Depended on by:** Nothing directly — this is a terminal output. But the session_health_score is used by the Cross-Video Study to compare session health across the study.

### Hackathon Scoring Impact

- **Innovation (+0.4):** Two-stage LLM reasoning (analyze video → synthesize findings) is architecturally sophisticated. Shows the pipeline does more than just throw video at a model.
- **Impact (+0.5):** Narrative summaries are what product teams actually read. A 3-paragraph summary with "fix the bridge, protect the combat, watch the tutorial" is directly actionable.
- **Running Code (+0.2):** Polish and completeness
- **Target judges:** Heitzeberg (the "aha" cross-dimensional insight), Warda (proactive intelligence — system discovers non-obvious patterns), Reddy (actionable, operationalizable output), Chrobok (evidence-backed narrative)

---

## 9. Cross-Video Study Aggregation

### Feature Name and Purpose

**Cross-Video Study Aggregation** collects completed video reports from multiple sessions of the same game and computes **per-segment statistics across all sessions**. It produces segment fingerprints (how each game area performs across all players), stop-risk cohorts (groups of sessions sharing dangerous friction patterns), and the raw statistical foundation for cross-video insight synthesis.

**Question it answers:** "Across all 53 playtest sessions, which parts of the game work and which don't? What are the failure rates? What do players consistently love or hate?"

### Business Justification

This is the **single most important differentiator** in the entire project. The FINAL_REPORT calls it "the insight no other hackathon project can show" and "the aha no other team can replicate."

Every other hackathon project shows one interaction — one video analyzed, one conversation with a chatbot, one document processed. GameSight shows **patterns that emerge from scale**. "The bridge jump has a 68% first-attempt failure rate across 53 sessions" is fundamentally different from "this player struggled with the bridge." The first is a product insight that changes design decisions. The second is an anecdote.

Without cross-video aggregation, GameSight is a nice video analysis tool. With it, GameSight is a playtest analytics platform.

### Detailed Behavior Specification

**Study identity and grouping:** Cross-video studies are grouped by normalized `game_key`, not by raw `game_title`. `VideoInfo`, `VideoReport`, and `StudyReport` all carry `game_key` for stable grouping plus `game_title` for display.

**Segment Fingerprints** — For each unique `segment_label` found across all sessions:

| Statistic | Computation | Example |
|---|---|---|
| `sessions_encountered` | Count of sessions where this segment appears in any moment | 47 out of 53 |
| `friction_rate` | sessions_with_friction / sessions_encountered | 0.68 (68% of players who reached the bridge had friction) |
| `avg_friction_severity` | Mean severity_numeric across all friction moments for this segment | 7.2 / 10 |
| `delight_rate` | sessions_with_delight / sessions_encountered | 0.91 (91% of players enjoyed combat) |
| `avg_sentiment` | Mean sentiment score for this segment across all sessions | +7.1 for combat, -2.8 for bridge |
| `positive_sentiment_rate` | Fraction of sentiment samples > 0 | 0.91 (91% positive — THIS is the "91% positive combat sentiment" stat) |
| `first_attempt_failure_rate` | Retry sequences with attempts > 1 / total retry encounters | 0.68 (68% — THIS is the "68% first-attempt failure rate" stat) |
| `avg_retry_attempts` | Mean attempt count across all retry sequences for this segment | 3.4 attempts average |
| `quit_signal_rate` | Retry sequences with quit_signal / total retry encounters | 0.12 (12% of players showed quit signals) |
| `representative_quotes` | Top 5 verbal moments from this segment across all sessions | ["I keep falling off this bridge", "This jump is impossible", ...] |

**Stop-Risk Cohorts** — Groups of sessions sharing a dangerous friction pattern:

For each segment with `friction_rate >= 30%` and appearing in 2+ sessions:
- How many sessions were affected
- What percentage of total sessions
- Common pattern description (friction rate + severity + quit signal rate)
- Representative player quotes

Cohorts are ranked by percentage of total sessions affected, top 5 reported.

**Coverage-aware denominators:** Optional agents can fail or be skipped on some chunks. Each `VideoReport` therefore carries per-chunk `ChunkAgentCoverage`, and study metrics only treat a session as part of a retry / sentiment / verbal denominator if that agent actually ran. Missing optional-agent output is never interpreted as a zero.

**Edge cases:**
- Segment label normalization: Different sessions may emit minor casing or punctuation variants (`Bridge Jump`, `bridge-jump`, `bridge_jump`). `normalize_segment_label()` collapses those into one grouping key. Truly different labels such as `bridge_jump` vs `bridge_crossing` remain distinct unless prompts or manual cleanup align them.
- Sessions of different lengths: Some sessions may not reach later game areas. The `sessions_encountered` count handles this — statistics are computed only across sessions that actually encountered each segment.
- Game areas that only appear in one session: These produce valid but low-confidence fingerprints. They're included but ranked low.

### Data Flow

```
All VideoReports from database (filtered by game_key)
    → Segment fingerprint computation (pure code, normalized labels, typed fields,
      coverage-aware denominators)
    → Stop-risk cohort identification (pure code)
    → StudyReport with raw statistics (ready for LLM synthesis)
```

### Quality Criteria

**Good output:** The bridge_jump segment has `sessions_encountered=47`, `friction_rate=0.68`, `first_attempt_failure_rate=0.68`, `avg_retry_attempts=3.4`, `quit_signal_rate=0.12`, `avg_sentiment=-2.8`, and representative quotes from multiple different players all describing the same frustration.

**Bad output:** Fragmented segments — the same game area appears as 5 different labels across sessions, each with only 2-3 sessions, instead of one consolidated label with 47 sessions. This reduces statistical power and makes findings less compelling.

### Relationships

- **Depends on:** All individual video analyses complete (Phase 1-3), segment labels in timeline, retry/sentiment/verbal data in reports
- **Depended on by:** Cross-Video Insight Synthesis (reads the aggregated statistics)

### Hackathon Scoring Impact

- **Innovation (+0.8):** "Patterns across 53 sessions" — this is the differentiator. No other hackathon project shows aggregate intelligence from scale.
- **Impact (+0.8):** Produces the exact statistics the demo needs: "68% failure rate," "91% positive sentiment," "47/53 sessions affected"
- **Theme (+0.3):** Demonstrates Gemini processing at scale (53 videos × multimodal analysis)
- **Target judges:** Heitzeberg (the "aha" — "make this a startup"), Skowronski (volume = leverage, business case), Vadi (Gemini platform engagement at scale), ALL judges (this IS the demo)

---

## 10. Cross-Video Insight Synthesis

### Feature Name and Purpose

**Cross-Video Insight Synthesis** takes the aggregated statistics from the Study Aggregation step and feeds them to Gemini as a text-only synthesis call, asking the model to discover **non-obvious patterns** — correlations, tradeoffs, and tipping points that would be invisible from watching any single session.

**Question it answers:** "What surprising patterns emerge when we look across all sessions? What would no one see by watching videos one at a time?"

### Business Justification

The Study Aggregation produces numbers. This step produces *intelligence*. The numbers say "68% bridge failure rate" and "91% combat sentiment." The insight synthesis says: "Players who praise the combat system spend 3× longer in optional exploration areas. Your combat is so good it's driving exploration — if you put a shortcut past the bridge that unlocks after 3 failures, you keep those players in the game instead of losing them."

This is the "proactive intelligence" beat in the demo script (0:55-1:02). The agent volunteers an unsolicited finding that crosses two data dimensions — something no one asked about, connecting information that no individual session reveals. This is the moment that makes judges say "that's not just a tool, that's an analyst."

### Detailed Behavior Specification

**Input:** The complete study statistics serialized as JSON: all segment fingerprints, all stop-risk cohorts, and the full session reports. This input is intentionally not trimmed or sliced before synthesis; tokens are cheap, and the synthesis pass should see the whole study. This is a text-only Gemini call — no video, very cheap (~$0.02).

**Instructions to the model:**
1. Find 3-5 non-obvious patterns from the aggregated data
2. Every insight must cite specific statistics (percentages, session counts, averages)
3. Reject weak patterns — only include patterns supported by 3+ sessions
4. Focus on patterns invisible from any single session
5. Turn insights into concrete recommended actions

**Types of insights the model should look for:**
- **Correlations:** "Players who [positive signal in area X] show [different behavior in area Y]"
- **Tipping points:** "After N failures, quit probability jumps from X% to Y%"
- **Compensating strengths:** "Despite high friction at [area], players persist because [feature] has [positive metric]"
- **Surprising disconnects:** "Players report [emotion] verbally but their behavior shows [opposite]"
- **Segment comparisons:** "Combat has 91% positive sentiment vs bridge at 32% — the gap is driven by [specific factors]"

**Output schema:**
- 3-5 `CrossVideoInsight` objects, each with:
  - `title`: Short headline
  - `insight`: The full finding
  - `evidence_summary`: Statistics backing it up
  - `sessions_supporting`: How many sessions show this pattern
  - `confidence`: strong (5+ sessions, clear evidence), moderate (3-4 sessions), suggestive (pattern exists but evidence is thin)
  - `recommended_action`: What the studio should do about it
- `top_priorities`: Ranked action items derived from the insights
- `executive_summary`: 3-paragraph narrative of the cross-session findings

**Edge cases:**
- Too few sessions (< 5): Insights will be low-confidence. The model should acknowledge this and focus on the most robust patterns.
- Very consistent sessions (everyone loves the game): The model should say so — "no significant friction patterns detected across 53 sessions" is a valid and valuable finding.
- Contradictory data: Some players love something others hate. The model should identify this as a segmentation pattern, not average it away.

### Data Flow

```
StudyReport statistics (JSON) → Gemini (text-only, structured output)
    → CrossVideoSynthesis (insights + priorities + executive summary)
    → Merged into final StudyReport
    → Stored in database
```

### Quality Criteria

**Good output:** "Players who fail the bridge_jump 3 or more times (N=31) are 40% more likely to show quit signals than those who fail 1-2 times (N=16). However, 87% of players who eventually succeed report the bridge as a 'memorable challenge' in their verbal feedback. Recommendation: add an optional hint system after 3 failures rather than removing the challenge entirely — preserve the sense of achievement while reducing churn."

This is good because: it cites specific numbers (31, 16, 40%, 87%), it reveals a non-obvious tradeoff (bridge is frustrating but memorable), and the recommendation balances churn reduction with game design principles.

**Bad output:** "Many players struggled with the bridge. We recommend making it easier." This is bad because: no specific numbers, obvious observation (not non-obvious), and generic recommendation.

### Relationships

- **Depends on:** Cross-Video Study Aggregation (needs the computed statistics)
- **Depended on by:** Nothing — this is the terminal output of the entire system

### Hackathon Scoring Impact

- **Innovation (+0.8):** AI discovering non-obvious correlations across 53 sessions is genuinely novel. This is the feature no other hackathon project has.
- **Impact (+0.5):** The insights are directly actionable and demonstrate business value. "Put a shortcut past the bridge that unlocks after 3 failures" is a specific design recommendation backed by quantified evidence.
- **Theme (+0.2):** Gemini synthesizing derived metrics (not just raw model output) shows the pipeline uses Gemini for reasoning, not just perception
- **Target judges:** Heitzeberg (the "aha" — "100 playtesters, 100 hours of video, one AI that finds what they all have in common"), Warda (proactive intelligence, agent discovers things unprompted), Chrobok (evidence-backed, cross-validated claims), Skowronski ("no human could find this by watching alone" = business moat)

---

## Summary: How All Features Work Together

```
                          ┌─────────────────────┐
                          │   Video Input (MP4   │
                          │   or YouTube URL)    │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Timeline Pass       │
                          │  (+ segment_labels)  │ ◄── Feature 1
                          └──────────┬──────────┘
                                     │
                  ┌──────────────────┼──────────────────┐
                  │                  │                   │
         ┌────────▼────────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
         │  Original 4     │ │ Sentiment   │ │ Retry + Verbal    │
         │  Specialists    │ │ Agent       │ │ Agents            │
         │  (unchanged)    │ │ Feature 2   │ │ Features 3 & 4    │
         └────────┬────────┘ └──────┬──────┘ └─────────┬─────────┘
                  │                  │                   │
                  └──────────────────┼───────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Dedup + Segment     │
                          │  Label Assignment    │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Evidence            │
                          │  Verification        │ ◄── Feature 5
                          └──────────┬──────────┘
                                     │
                  ┌──────────────────┼──────────────────┐
                  │                  │                   │
         ┌────────▼────────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
         │  Enhanced       │ │ Highlight   │ │ Executive         │
         │  Aggregation    │ │ Reel        │ │ Summary (LLM)     │
         │  Feature 6      │ │ Feature 7   │ │ Feature 8         │
         └────────┬────────┘ └──────┬──────┘ └─────────┬─────────┘
                  │                  │                   │
                  └──────────────────┼───────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  VideoReport         │
                          │  (complete, stored)  │
                          └──────────┬──────────┘
                                     │
                          × N sessions (e.g., 53)
                                     │
                          ┌──────────▼──────────┐
                          │  Cross-Video Study   │
                          │  Aggregation         │ ◄── Feature 9
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Cross-Video Insight │
                          │  Synthesis (LLM)     │ ◄── Feature 10
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  StudyReport         │
                          │  (the demo output)   │
                          └─────────────────────┘
```

**Operational exposure:**
- Per-video routes expose the new outputs directly: `/videos/{video_id}/sentiment`, `/videos/{video_id}/retry`, `/videos/{video_id}/verbal`, `/videos/{video_id}/highlights`, and `/videos/{video_id}/executive`
- Study routes expose cross-video analysis by normalized key: `POST /studies/{game_key}/analyze` and `GET /studies/{game_key}`
- Debug traces label the new structured calls as `sentiment`, `retry`, `verbal`, `executive`, and `study_synthesis`

**The key insight chain that produces the demo's centerpiece moment:**

1. **Segment Labels** name the bridge section as `bridge_jump` across all sessions
2. **Retry Agent** detects 3-5 attempt sequences at `bridge_jump` per session
3. **Sentiment Agent** produces -2.8 average sentiment at `bridge_jump` and +7.1 at `combat`
4. **Verbal Agent** captures "I keep falling off this bridge" and "the combos feel incredible"
5. **Evidence Verification** confirms bridge findings are corroborated by 4+ agents (0.95 confidence)
6. **Enhanced Aggregation** computes `sentiment_by_segment` and `first_attempt_failure_count`
7. **Executive Summary** identifies the bridge as the #1 priority and connects it to the tutorial gap
8. **Cross-Video Study** computes 68% first-attempt failure rate across 53 sessions
9. **Cross-Video Synthesis** discovers: "Players who praise combat spend 3× longer in optional areas. The bridge churn is killing your best players."

**Without any single feature in this chain, the demo's most impressive moment doesn't work.**
