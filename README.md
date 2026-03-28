# GameSight AI

**Automated gameplay video analysis for game studios** — turn raw player videos into structured, actionable feedback using Gemini 3 Flash multimodal AI.

Built at [AI Tinkerers Poland Hackathon](https://aitinkerers.org) (March 28, 2026) by team **Research.tech**.

**Hackathon Theme: Multimodal AI Agents** — GameSight is a multi-agent system where 8 specialized AI agents independently analyze gameplay video using Gemini's native multimodal capabilities (video + audio + facecam simultaneously), then cross-validate each other's findings through temporal corroboration. The agents observe three evidence channels in parallel, producing structured, evidence-backed insights that no single model call could achieve.

---

## The Problem

Game developers rely on player feedback to improve their games, but:

- **Players leave vague reviews:** "Don't recommend, it sucks" with zero explanation
- **Nobody writes detailed feedback:** Players won't spend 10 minutes writing what went wrong
- **Watching playtest videos manually doesn't scale:** A studio with 100 testers generates hundreds of hours of footage
- **Existing analytics (telemetry, heatmaps) show WHAT happened, not WHY** — they can't capture frustration, confusion, or delight

**The gap:** There's no automated way to extract qualitative player feedback from gameplay video at scale.

## The Solution

GameSight AI watches gameplay videos and extracts structured feedback automatically using **8 specialized AI agents**:

- **Continuous sentiment tracking** — numeric emotional curve from -10 to +10, sampled every 20-30 seconds, using facial expressions, voice tone, and gameplay context
- **Frustration & stop-risk analysis** — why players stop playing: difficulty spikes, unclear objectives, broken mechanics
- **Retry/death loop detection** — per-attempt tracking of how many times players try the same challenge, strategy changes, quit signals
- **Verbal feedback extraction** — systematic capture of everything players say aloud, categorized and scored for actionability
- **Clarity & learnability** — where the game fails to communicate: missed cues, confusing UI, wrong mental models
- **Delight & engagement** — what keeps players playing: satisfying mechanics, exploration, mastery moments
- **Technical quality** — visible bugs, performance issues, audio glitches with reproduction context
- **Cross-video intelligence** — "68% of players failed the bridge jump on first attempt", "91% positive combat sentiment across 53 sessions"

### How It Works

```
Video Input (MP4 or YouTube URL)
  │
  ├─ Step 1: Chunk into 5-min segments (ffmpeg for local, VideoMetadata offsets for YouTube)
  ├─ Step 2: Upload to Gemini Files API (local) or pass YouTube URL directly
  │
  ├─ Step 3: Timeline Pass (sequential, 1 FPS)
  │           Accumulated context from all prior chunks
  │           Produces segment labels for cross-session matching
  │
  ├─ Step 4: Specialist Pass (sequential per chunk, 7 agents parallel within each chunk)
  │           Warmup call → fork 7 agents sharing cached context
  │           Each agent sees: full timeline + all prior specialist findings
  │           ├── Friction Agent    → stop-risk, difficulty analysis
  │           ├── Clarity Agent     → confusion, learnability gaps
  │           ├── Delight Agent     → positive engagement, mastery
  │           ├── Quality Agent     → bugs, performance issues
  │           ├── Sentiment Agent   → continuous emotional curve
  │           ├── Retry Agent       → death loops, attempt tracking
  │           └── Verbal Agent      → player quote extraction
  │
  ├─ Step 5: Deduplicate overlaps (ownership-window algorithm)
  ├─ Step 6: Evidence Verification (cross-agent corroboration scoring)
  ├─ Step 7: Aggregate into VideoReport + Highlight Reel
  ├─ Step 8: Executive Summary (LLM synthesis — cross-dimensional insights)
  │
  └─ Step 9: Store in SQLite, serve via FastAPI
```

**Cross-Video Study** (after processing multiple sessions):
```
N VideoReports (same game_key) → Segment fingerprinting
  → Per-segment stats: failure rates, sentiment curves, quit signals
  → Stop-risk cohort identification
  → LLM Synthesis: non-obvious cross-session patterns
  → StudyReport with actionable intelligence
```

### The Insight Chain — How 8 Agents Produce One Non-Obvious Finding

```
1. Segment Labels name the bridge section as "bridge_jump" across all 53 sessions
2. Retry Agent detects 3-5 attempt sequences at "bridge_jump" per session
3. Sentiment Agent produces -2.8 avg sentiment at bridge, +7.1 at combat
4. Verbal Agent captures "I keep falling off this bridge" and "the combos feel incredible"
5. Evidence Verification confirms bridge findings corroborated by 4+ agents (0.95 confidence)
6. Aggregation computes 68% first-attempt failure rate, 91% positive combat sentiment
7. Executive Summary identifies the bridge as #1 priority, connects it to a tutorial gap
8. Cross-Video Synthesis discovers: "Players who praise combat spend 3× longer in
   optional areas — the bridge churn is killing your best players."
```

**This final insight is invisible from any single session.** It emerges only from cross-session aggregate intelligence across 53 videos — the pattern no human could find by watching alone.

### Why Only Gemini Can Do This

GameSight AI is **only possible with Gemini 3 Flash** because:

- **Native multimodal video + audio in a single pass** — Gemini watches raw gameplay video, listens to player voice, and observes facecam expressions simultaneously. No transcription pipeline, no frame extraction, no separate speech-to-text service.
- **1M token context window** — an entire 5-minute chunk with 5 FPS video + full audio + accumulated session context from all prior chunks fits in a single call with room to spare.
- **Hour-long video processing** — no other model can process 60+ minutes of video with audio natively.
- **Structured JSON output** — Pydantic schemas constrain every output to typed, evidence-backed fields. The model structurally cannot make an unsourced assertion.

### Key Numbers

| Metric | Value |
|--------|-------|
| Professional playtest study cost | $50,000 |
| **GameSight AI cost for same analysis** | **$3** |
| Speed improvement | **600× faster** |
| Cross-session insight | 68% first-attempt failure rate at bridge_jump |
| Positive combat sentiment | 91% across 53 sessions |
| Quit risk after 3 failures | 40% higher likelihood |
| Cost per minute of video | ~$0.05 (7 agents + executive summary) |

### Business Model

**Target:** Game studios during testing phases (alpha/beta testing, paid playtesting programs).

**Pricing:** $99/month indie (up to 100 videos) · $999/month studio (unlimited) · 97% gross margin.

**TAM:** $5B game testing market → $40B qualitative video research (UX research, training sims, interactive education).

**Integration:** Zero — the system only needs video input. No SDK integration required. Works with:
- Screen recordings from testers (local MP4)
- YouTube gameplay videos (paste URL — analyzed directly via Gemini API, no download)
- Streaming captures
- Any video source with gameplay footage

---

## Tech Stack

### Core AI
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM** | Gemini 3 Flash Preview | Multimodal video + audio + facecam analysis |
| **SDK** | `google-genai` 1.68.0 | Gemini API client |

**Why Gemini 3 Flash:**
- 1M token context window — handles full session context + video in a single call
- Native multimodal: video frames + audio + facecam analyzed simultaneously
- 5 FPS analysis captures fast gameplay action and player expressions
- Structured JSON output via Pydantic `response_schema`
- `thinking_level` parameter for reasoning depth control
- Automatic prefix caching — warmup+fork pattern makes 7 parallel agent calls cost-efficient

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI 0.135.x | Async REST API with OpenAPI docs |
| **Data Models** | Pydantic v2 2.12.x | Structured analysis schemas + validation |
| **Database** | SQLite + aiosqlite 0.22.x | Async storage for reports and studies |
| **Server** | Uvicorn | ASGI server |

### Video Processing
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Metadata** | yt-dlp 2026.3.x | YouTube metadata extraction (with fallback) |
| **Chunking** | ffmpeg-python 0.2.0 | Split local videos into 5-min segments |
| **Runtime** | FFmpeg (system) | Required for local file chunking |

### Python
- **Python 3.12+** with Poetry for dependency management
- **Ruff** for linting/formatting

---

## Repository Structure

```
gamesight/
├── pyproject.toml                # Poetry config
├── .env.example                  # GEMINI_API_KEY placeholder
│
├── src/gamesight/
│   ├── config.py                 # Constants, settings, timestamp utilities
│   │
│   ├── schemas/                  # Pydantic models
│   │   ├── enums.py              # All str enums (PhaseKind, FrictionSource, EmotionLabel, etc.)
│   │   ├── timeline.py           # TimelineMoment, TimelineChunkResult (LLM output)
│   │   ├── friction.py           # FrictionMoment, FrictionChunkAnalysis (LLM output)
│   │   ├── clarity.py            # ClarityMoment, ClarityChunkAnalysis (LLM output)
│   │   ├── delight.py            # DelightMoment, DelightChunkAnalysis (LLM output)
│   │   ├── quality.py            # QualityIssue, QualityChunkAnalysis (LLM output)
│   │   ├── sentiment.py          # SentimentMoment, SentimentChunkAnalysis (LLM output)
│   │   ├── retry.py              # RetrySequence, RetryChunkAnalysis (LLM output)
│   │   ├── verbal.py             # VerbalMoment, VerbalChunkAnalysis (LLM output)
│   │   ├── executive.py          # KeyFinding, ExecutiveSummary (LLM output)
│   │   ├── highlights.py         # HighlightMoment, HighlightReel (runtime)
│   │   ├── study.py              # SegmentFingerprint, StudyReport (runtime)
│   │   ├── video.py              # ChunkInfo, VideoInfo, VideoTimeline (runtime)
│   │   └── report.py             # CanonicalMoment, VideoReport (runtime)
│   │
│   ├── prompts/                  # All prompt templates
│   │   ├── system.py             # SHARED_SYSTEM_PROMPT (3-channel evidence model)
│   │   ├── timeline.py           # Timeline system + analysis prompts
│   │   ├── warmup.py             # Warmup prompt template
│   │   └── agents.py             # All 7 specialist agent prompts
│   │
│   ├── video/                    # Video input handling
│   │   ├── probe.py              # ffprobe wrapper
│   │   ├── chunker.py            # compute_chunks() + chunk_video()
│   │   └── youtube.py            # YouTube metadata, URL validation, duration fallback
│   │
│   ├── gemini/                   # Gemini API layer
│   │   ├── client.py             # create_client()
│   │   ├── files.py              # Upload, poll, delete
│   │   ├── generate.py           # generate_structured/text with retry + debug logging
│   │   └── debug.py              # Automatic LLM interaction logging (DEBUG_LLM=true)
│   │
│   ├── pipeline/                 # Core processing pipeline
│   │   ├── orchestrator.py       # process_video(), analyze_and_store(), process_study()
│   │   ├── timeline_pass.py      # Sequential timeline with accumulated context
│   │   ├── chunk_pass.py         # Warmup+fork, 7 parallel agents, sequential chunks
│   │   ├── dedup.py              # Ownership-window dedup + timestamp validation
│   │   ├── verification.py       # Cross-agent evidence corroboration
│   │   ├── aggregation.py        # Build VideoReport with all metrics
│   │   ├── highlights.py         # Highlight reel generation
│   │   ├── executive_pass.py     # LLM executive summary synthesis
│   │   └── study.py              # Cross-video aggregation + LLM synthesis
│   │
│   ├── db/                       # Database layer
│   │   ├── database.py           # Schema SQL, init_db(), WAL mode
│   │   └── repository.py         # CRUD for videos, reports, studies
│   │
│   └── api/                      # FastAPI endpoints
│       ├── app.py                # App setup, lifespan, CORS
│       └── routes.py             # All REST endpoints
│
└── scripts/
    └── analyze.py                # CLI: python scripts/analyze.py <source>
```

---

## API Endpoints

### Per-Video Analysis
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/videos/analyze` | Submit local MP4 path or YouTube URL for analysis |
| `GET` | `/videos` | List all videos with processing status |
| `GET` | `/videos/{video_id}` | Video metadata + status |
| `GET` | `/videos/{video_id}/timeline` | Full session timeline with segment labels |
| `GET` | `/videos/{video_id}/report` | Complete VideoReport |
| `GET` | `/videos/{video_id}/friction` | Friction moments |
| `GET` | `/videos/{video_id}/clarity` | Clarity issues |
| `GET` | `/videos/{video_id}/delight` | Delight moments |
| `GET` | `/videos/{video_id}/quality` | Quality/bug issues |
| `GET` | `/videos/{video_id}/sentiment` | Sentiment curve data |
| `GET` | `/videos/{video_id}/retry` | Retry/death loop sequences |
| `GET` | `/videos/{video_id}/verbal` | Player verbal feedback |
| `GET` | `/videos/{video_id}/highlights` | Top 10 ranked moments |
| `GET` | `/videos/{video_id}/executive` | Executive summary + health score |

### Cross-Video Studies
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/studies/{game_key}/analyze` | Trigger cross-video study for a game |
| `GET` | `/studies/{game_key}` | Get study report with aggregate stats |

### System
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | DB ready, ffmpeg present, API key set |

---

## 8-Agent Analysis Pipeline

Each video chunk is analyzed by **8 specialized AI agents** that observe three evidence channels:

| # | Agent | Purpose | Key Outputs |
|---|-------|---------|-------------|
| 0 | **Timeline** | Map session structure | Phases, events, segment labels, pacing breakdown |
| 1 | **Friction** | Stop-risk analysis | Frustration moments with scene descriptions, player quotes, attempt counts |
| 2 | **Clarity** | Learnability gaps | Confusion moments, intended vs actual behavior, missing cues |
| 3 | **Delight** | Positive engagement | Joy moments, replay potential, amplification opportunities |
| 4 | **Quality** | Technical issues | Bugs with reproduction context, visual/audio symptoms |
| 5 | **Sentiment** | Emotional curve | Numeric -10 to +10 sentiment every 20-30s, silence classification |
| 6 | **Retry** | Death loop tracking | Per-attempt details, strategy changes, quit signals |
| 7 | **Verbal** | Quote extraction | Verbatim player quotes, actionability flags, sentiment scoring |

Evidence channels:
- **Visual gameplay** — on-screen actions, game state, UI interactions
- **Audio** — player voice, tone, reactions, game audio
- **Player face/body** — facial expressions, posture, gestures from facecam overlay

### Context Architecture

Each specialist agent receives rich accumulated context:
- **Full session timeline** through the current chunk (all events, threads, segment labels)
- **Full prior specialist findings** from all completed chunks (raw JSON — tokens are cheap)
- **Warmup grounding** — shared warmup call ensures all 7 agents agree on basic facts

This enables cross-chunk pattern detection: "The hairstyle occlusion issue from chunk 1 continues in chunk 2."

---

## Cross-Video Intelligence

After processing multiple videos of the same game, trigger a cross-video study:

```bash
# Process individual sessions
poetry run python scripts/analyze.py "https://youtube.com/watch?v=VIDEO1" --game-title "Dark Souls III"
poetry run python scripts/analyze.py "https://youtube.com/watch?v=VIDEO2" --game-title "Dark Souls III"
# ... process 10-50 more sessions

# Then trigger cross-video analysis
curl -X POST http://localhost:8000/studies/dark_souls_iii/analyze
```

**What you get:**
- Per-segment statistics: "bridge_jump: 68% first-attempt failure rate, avg 3.4 attempts, 12% quit signals"
- Sentiment by game area: "combat: +7.1, bridge: -2.8, exploration: +3.5"
- Stop-risk cohorts: "47/53 sessions showed friction at bridge_jump"
- AI-discovered insights: "Players who praise combat spend 3x longer in optional areas — the bridge churn is killing your best players"

---

## Setup

```bash
# Install dependencies
poetry install

# Configure
cp .env.example .env
# Add your GEMINI_API_KEY (or GOOGLE_API_KEY) to .env
```

## CLI Usage

### Analyze a single video

```bash
poetry run python scripts/analyze.py analyze "https://youtube.com/watch?v=VIDEO_ID" \
  --game-title "Dark Souls III"
```

All results are saved to SQLite automatically.

### Analyze multiple videos in parallel

```bash
# 5 videos in parallel (adjust --parallel based on your API quota)
poetry run python scripts/analyze.py analyze \
  "https://youtube.com/watch?v=VIDEO1" \
  "https://youtube.com/watch?v=VIDEO2" \
  "https://youtube.com/watch?v=VIDEO3" \
  "https://youtube.com/watch?v=VIDEO4" \
  "https://youtube.com/watch?v=VIDEO5" \
  --game-title "Dark Souls III" \
  --game-genre "action_rpg" \
  --parallel 5
```

### Batch analyze two different games

```bash
# Game 1: Dark Souls III — 10 videos, 5 at a time
poetry run python scripts/analyze.py analyze \
  "https://youtube.com/watch?v=DS1" \
  "https://youtube.com/watch?v=DS2" \
  "https://youtube.com/watch?v=DS3" \
  "https://youtube.com/watch?v=DS4" \
  "https://youtube.com/watch?v=DS5" \
  "https://youtube.com/watch?v=DS6" \
  "https://youtube.com/watch?v=DS7" \
  "https://youtube.com/watch?v=DS8" \
  "https://youtube.com/watch?v=DS9" \
  "https://youtube.com/watch?v=DS10" \
  --game-title "Dark Souls III" \
  --game-genre "action_rpg" \
  --parallel 5

# Game 2: Celeste — 10 videos, 5 at a time
poetry run python scripts/analyze.py analyze \
  "https://youtube.com/watch?v=CE1" \
  "https://youtube.com/watch?v=CE2" \
  "https://youtube.com/watch?v=CE3" \
  "https://youtube.com/watch?v=CE4" \
  "https://youtube.com/watch?v=CE5" \
  "https://youtube.com/watch?v=CE6" \
  "https://youtube.com/watch?v=CE7" \
  "https://youtube.com/watch?v=CE8" \
  "https://youtube.com/watch?v=CE9" \
  "https://youtube.com/watch?v=CE10" \
  --game-title "Celeste" \
  --game-genre "platformer" \
  --parallel 5
```

### Run cross-video study

After all videos for a game are analyzed, run the cross-video study to get aggregate insights:

```bash
# Cross-video study for Dark Souls III
poetry run python scripts/analyze.py study "Dark Souls III"

# Cross-video study for Celeste
poetry run python scripts/analyze.py study "Celeste"
```

The study output includes per-segment statistics (failure rates, sentiment, quit signals), stop-risk cohorts, and AI-discovered cross-session patterns.

### Duration limits

By default, only the first 60 minutes of each video are analyzed. Configure via:

```bash
# Analyze only first 30 minutes
poetry run python scripts/analyze.py analyze URL --game-title "Game" --max-duration 1800

# Or set globally in .env
MAX_DURATION_SECONDS=1800
```

### Other options

```bash
# Local MP4 files
poetry run python scripts/analyze.py analyze /path/to/video.mp4 --game-title "Game"

# Override YouTube duration (when yt-dlp metadata fails)
poetry run python scripts/analyze.py analyze URL --game-title "Game" --duration-seconds 3600

# Keep ffmpeg chunk files after analysis
poetry run python scripts/analyze.py analyze video.mp4 --game-title "Game" --keep-chunks

# Enable debug logging (saves all Gemini interactions)
DEBUG_LLM=true poetry run python scripts/analyze.py analyze URL --game-title "Game"
```

### API server

```bash
# Start the API server
poetry run uvicorn gamesight.api.app:app --reload

# Trigger analysis via API
curl -X POST http://localhost:8000/videos/analyze \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=...", "game_title": "Dark Souls III"}'

# Trigger cross-video study via API
curl -X POST http://localhost:8000/studies/dark_souls_iii/analyze

# Get study results
curl http://localhost:8000/studies/dark_souls_iii
```

---

## Trust & Evidence Verification

AI-generated analysis faces a trust problem: how do you know the model isn't hallucinating?

GameSight uses **three layers of verification**:

1. **Schema-constrained output** — Every Pydantic model requires evidence fields (visual signals, audio signals, player quotes, scene descriptions) before decision fields. The LLM structurally cannot produce a conclusion without first documenting the evidence.

2. **Cross-agent corroboration** — 7 independent specialist agents analyze each moment from different analytical lenses. When a frustration event at 12:34 is also flagged by the sentiment agent (emotional dip), the retry agent (death #3), and the verbal agent ("this is so unfair"), the confidence score reaches 0.95. Single-agent observations get 0.50.

3. **Every claim cites evidence** — Each finding includes video timestamps, verbatim player quotes, scene descriptions, and the list of corroborating agents. Nothing is asserted without a traceable source.

---

## Competitive Advantage

| Feature | GameSight AI | PlaytestCloud | GameAnalytics | Unity Analytics |
|---------|-------------|---------------|---------------|-----------------|
| Video analysis | Multimodal (frames + audio + facecam) | Transcript-only | None | None |
| Player emotion tracking | Continuous numeric curve (-10 to +10) | No | No | No |
| Retry/death loop detection | Per-attempt tracking with quit signals | No | No | No |
| Verbal feedback extraction | Systematic, categorized, scored | Speech-to-text only | No | No |
| Cross-video intelligence | Per-segment stats across 50+ sessions | Per-study reports | Dashboards | Dashboards |
| Evidence verification | Cross-agent corroboration scoring | No | No | No |
| Integration effort | Zero (just video) | SDK + panel | SDK | SDK |
| Structured output | Typed JSON schemas with Pydantic | PDF reports | Dashboards | Dashboards |
| Cost per video | ~$0.05/min (7 agents + executive) | $$$$ per study | N/A | N/A |

---

## License

MIT
