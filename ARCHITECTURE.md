# GameSight AI — Architecture

---

## System Overview

GameSight AI is a three-service architecture: a **React frontend**, a **Streams Finder** backend for video discovery, and the **GameSight Analysis** backend that runs 8 specialized AI agents against gameplay video using Gemini 3 Flash's native multimodal capabilities.

```
                          ┌──────────────────────────────────────────┐
                          │         Frontend (React + Vite)          │
                          │              Port 5555                   │
                          │                                          │
                          │  Game Discovery ──► Batch Analysis       │
                          │  Period Filters     Streaming Progress   │
                          │  Video Cards        Timeline + Insights  │
                          │  Study View         Executive Summary    │
                          │                                          │
                          │  Cache: IndexedDB (discover-cache.ts)    │
                          └──────────┬─────────────────┬─────────────┘
                                     │                 │
                          Vite proxy  │                 │  Vite proxy
                       /api/research/*│                 │  /api/videos/*
                                     │                 │  /api/studies/*
                                     ▼                 ▼
                 ┌────────────────────────┐  ┌───────────────────────────────┐
                 │    Streams Finder      │  │    GameSight Analysis         │
                 │    FastAPI :8000       │  │    FastAPI :8001              │
                 │                        │  │                               │
                 │  POST /research/       │  │  POST /videos/analyze         │
                 │       discover         │  │  GET  /videos                 │
                 │  POST /research/       │  │  GET  /videos/{id}/report     │
                 │       discover/stream  │  │  GET  /videos/{id}/timeline   │
                 │  GET  /health          │  │  GET  /videos/{id}/friction   │
                 │                        │  │  GET  /videos/{id}/clarity    │
                 │  Components:           │  │  GET  /videos/{id}/delight    │
                 │  ├─ QueryGenerator     │  │  GET  /videos/{id}/quality    │
                 │  ├─ YouTubeProvider    │  │  GET  /videos/{id}/sentiment  │
                 │  ├─ TwitchProvider     │  │  GET  /videos/{id}/retry      │
                 │  ├─ VideoVerifier      │  │  GET  /videos/{id}/verbal     │
                 │  └─ ResearchDiscoverer │  │  GET  /videos/{id}/highlights │
                 │                        │  │  GET  /videos/{id}/executive  │
                 │  Cache: in-memory dict │  │  POST /studies/{key}/analyze  │
                 │                        │  │  GET  /studies/{key}          │
                 └──────────┬─────────────┘  │  GET  /health                │
                            │                └──────────┬────────────────────┘
                            │                           │
                            ▼                           ▼
                 ┌────────────────────┐      ┌──────────────────────────┐
                 │  External APIs     │      │   Gemini 3 Flash API     │
                 │                    │      │   (google-genai 1.68.0)  │
                 │  YouTube (yt-dlp)  │      │                          │
                 │  Twitch API        │      │  Native multimodal:      │
                 │  Gemini (queries + │      │  video + audio + facecam │
                 │   verification)    │      │  1M token context        │
                 └────────────────────┘      │  Structured JSON output  │
                                             │  Prefix caching          │
                                             │  Thinking levels         │
                                             └──────────┬───────────────┘
                                                        │
                                             ┌──────────▼───────────────┐
                                             │   SQLite + aiosqlite     │
                                             │   (gamesight.db, WAL)    │
                                             │                          │
                                             │  videos                  │
                                             │  chunk_analyses          │
                                             │  video_timelines         │
                                             │  video_reports           │
                                             │  study_reports           │
                                             └──────────────────────────┘
```

---

## Video Analysis Pipeline

Each video goes through 9 sequential stages:

```
Video Input (MP4 or YouTube URL)
  │
  ├─[1] RESOLVE & CHUNK
  │     Local: ffprobe duration → ffmpeg split into 5-min segments (copy codec)
  │     YouTube: yt-dlp metadata → VideoMetadata offsets (no download)
  │     Overlap: 60s between chunks, ownership-window dedup
  │
  ├─[2] UPLOAD (local files only)
  │     Gemini Files API with concurrency semaphore (3 parallel)
  │     Poll until ACTIVE state
  │
  ├─[3] TIMELINE PASS (sequential, 1 FPS)
  │     For each chunk:
  │       System prompt includes accumulated context from all prior chunks
  │       Gemini → TimelineChunkResult (3-8 events, phases, segment_labels)
  │       Normalize segment_labels to snake_case
  │       Filter events by ownership window
  │     Output: VideoTimeline with session_arc, events, threads
  │
  ├─[4] SPECIALIST PASS (sequential per chunk, 7 agents parallel within chunk)
  │     For each chunk:
  │     ┌─────────────────────────────────────────────────────────────┐
  │     │  Warmup Call (grounding)                                   │
  │     │  Context: full timeline + all prior specialist findings    │
  │     │  Creates Gemini cache (prefix caching for cost efficiency) │
  │     └─────────────────────┬───────────────────────────────────────┘
  │                           │
  │     ┌─────────────────────┼───────────────────────────┐
  │     │  asyncio.gather (4 required agents)             │
  │     │  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────┐│
  │     │  │ Friction  │ │ Clarity  │ │ Delight │ │Qualit││
  │     │  │ stop-risk │ │ confusio │ │ engagem │ │ bugs ││
  │     │  │ severity  │ │ missing  │ │ mastery │ │ perf ││
  │     │  │ attempts  │ │ cues     │ │ replay  │ │      ││
  │     │  └──────────┘ └──────────┘ └─────────┘ └──────┘│
  │     └─────────────────────────────────────────────────┘
  │     ┌─────────────────────────────────────────────────┐
  │     │  asyncio.gather (3 optional agents, fail-safe)  │
  │     │  ┌───────────┐ ┌──────────┐ ┌────────┐         │
  │     │  │ Sentiment  │ │  Retry   │ │ Verbal │         │
  │     │  │ -10 to +10 │ │ deaths   │ │ quotes │         │
  │     │  │ every 20s  │ │ attempts │ │ tone   │         │
  │     │  │ emotion    │ │ quit sig │ │ action │         │
  │     │  └───────────┘ └──────────┘ └────────┘         │
  │     └─────────────────────────────────────────────────┘
  │     Post: clamp numeric values, normalize timestamps
  │     Output: list[ChunkAnalysisBundle]
  │
  ├─[5] DEDUPLICATION (ownership-window algorithm)
  │     Each chunk "owns" the non-overlapping portion:
  │       chunk 0: [0, chunk_end - overlap/2)
  │       chunk N: [chunk_start + overlap/2, chunk_end - overlap/2)
  │       last:    [chunk_start + overlap/2, video_end)
  │     Convert agent-specific moments → CanonicalMoment (unified schema)
  │     Assign segment_label from nearest timeline event (30s window)
  │     Map severity via named constants (FRICTION_SEVERITY_MAP, etc.)
  │     Output: DeduplicatedAnalyses (7 sorted moment lists)
  │
  ├─[6] EVIDENCE VERIFICATION (cross-agent corroboration)
  │     For each moment, find OTHER agent types within 15s window + same segment
  │     confidence = 0.50 + 0.15 × corroborating_agents + 0.10 if has_quote
  │     Capped at 1.0
  │     Example: friction at 12:34 + sentiment dip + retry death + verbal quote
  │              → confidence = 0.50 + 0.45 + 0.10 = 0.95
  │     Output: DeduplicatedAnalyses with confidence_score + corroborating_agents
  │
  ├─[7] AGGREGATION
  │     Build VideoReport from all analyses:
  │     - Highest stop_risk, friction severity, engagement across chunks
  │     - Top stop-risk drivers, praised features, clarity fixes (Counter)
  │     - Sentiment averages (global + per-segment)
  │     - Retry statistics (total sequences, first-attempt failures)
  │     - Notable quotes (actionable first, then by severity)
  │     - Agent coverage per chunk (which optional agents succeeded)
  │     - Auto-generated recommendations
  │
  ├─[8] HIGHLIGHTS (pure code, no LLM)
  │     Score = severity × agent_weight × (1 + 0.3 × corroborating_agents)
  │     Weights: retry 1.3, friction 1.2, quality 1.1, clarity 1.0, verbal 0.9,
  │              delight 0.8, sentiment 0.7
  │     Cluster within 30s windows → top 10 moments
  │     Each with clip boundaries (±10s)
  │
  └─[9] EXECUTIVE SUMMARY (single LLM call, text-only)
        Full VideoReport JSON → Gemini → ExecutiveSummary:
        - session_health_score (0-100, clamped)
        - 3-paragraph summary (overview, critical issues, strengths)
        - 3-5 key findings with timestamps and evidence
        - Priority actions (concrete: "add checkpoint before bridge")
        - Cross-dimensional insight (non-obvious pattern)
```

---

## Cross-Video Study Pipeline

After processing N videos of the same game:

```
N VideoReports (same game_key)
  │
  ├─[1] SEGMENT FINGERPRINTING
  │     Group all CanonicalMoments by normalized segment_label across sessions
  │     Per segment: friction_rate, avg_severity, delight_rate, avg_sentiment,
  │     positive_sentiment_rate, first_attempt_failure_rate, avg_retry_attempts,
  │     quit_signal_rate, representative_quotes
  │
  ├─[2] STOP-RISK COHORTS
  │     Segments with friction_rate >= 30% and >= 2 sessions
  │     Sorted by affected percentage, top 5
  │
  └─[3] LLM SYNTHESIS (single Gemini call)
        Full stats + all session reports → CrossVideoSynthesis:
        - 3-5 non-obvious cross-session patterns
        - Top priorities (ranked actions)
        - Executive summary (3 paragraphs)
```

---

## Streams Finder Pipeline

```
Game Name (user input)
  │
  ├─[1] QUERY GENERATION (Gemini)
  │     Game name → 5-10 diverse search queries
  │     Targets: gameplay, walkthrough, let's play, review
  │
  ├─[2] VIDEO DISCOVERY (parallel)
  │     YouTube: yt-dlp search with period/date filters
  │     Twitch: API search (if credentials configured)
  │     Deduplication by video ID
  │
  ├─[3] CONTENT VERIFICATION (Gemini)
  │     Classify each video: gameplay, review, trailer, commentary
  │     Filter to relevant content types
  │
  └─[4] RESULT
        DiscoveryResult with verified videos, metadata, thumbnails
        Cached in-memory (backend) + IndexedDB (frontend)
```

---

## Data Flow

```
User searches "Dark Souls III"
  │
  └─► Frontend POST /api/research/discover/stream
        └─► Streams Finder discovers 20 YouTube videos (SSE progress)
              └─► Frontend displays video cards with thumbnails

User selects 10 videos → "Analyze Batch"
  │
  └─► Frontend POST /api/videos/analyze/batch/stream
        └─► GameSight processes each video through 9-stage pipeline
              └─► SSE: timeline_chunk, insight, video_report events
                    └─► Frontend renders real-time progress per video

User clicks "Run Study"
  │
  └─► Frontend POST /api/studies/dark_souls_iii/analyze
        └─► GameSight aggregates all reports → LLM synthesis
              └─► StudyReport with cross-session patterns
```

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | React | 19.2 | UI framework |
| | TypeScript | 5.9 | Type safety |
| | Vite | 7.3 | Build + dev server + proxy |
| | Tailwind CSS | 4.2 | Styling |
| | shadcn/ui (Radix) | latest | Component library |
| | react-player | 3.4 | Video playback |
| | IndexedDB | native | Frontend caching |
| **Analysis Backend** | FastAPI | 0.135 | Async REST API |
| | Pydantic v2 | 2.12 | Schema validation + LLM output |
| | google-genai | 1.68 | Gemini API client |
| | aiosqlite | 0.22 | Async SQLite |
| | ffmpeg-python | 0.2 | Video chunking |
| | yt-dlp | 2026.3 | YouTube metadata |
| **Discovery Backend** | FastAPI | latest | Async REST API |
| | google-genai | 1.68 | Query generation + verification |
| | yt-dlp | 2026.3 | YouTube search |
| | httpx | latest | Twitch API client |
| **Database** | SQLite | system | WAL mode, 5 tables |
| **AI Model** | Gemini 3 Flash Preview | latest | 1M context, multimodal |
| **Runtime** | Python | 3.12+ | Backend |
| | Node.js | 18+ | Frontend dev |

---

## Database Schema

```sql
videos (
    id TEXT PRIMARY KEY,           -- UUID5 from source path/URL
    source TEXT NOT NULL,          -- file path or YouTube URL
    source_type TEXT NOT NULL,     -- "local" or "youtube"
    filename TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    status TEXT DEFAULT 'pending', -- pending → analyzing → complete/failed
    error_message TEXT,
    created_at TIMESTAMP
)

chunk_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT REFERENCES videos(id),
    chunk_index INTEGER NOT NULL,
    chunk_start_seconds REAL,
    chunk_end_seconds REAL,
    agent_type TEXT NOT NULL,      -- friction/clarity/delight/quality/sentiment/retry/verbal
    analysis_json TEXT NOT NULL,   -- Full Pydantic model as JSON
    UNIQUE(video_id, chunk_index, agent_type)
)

video_timelines (
    video_id TEXT PRIMARY KEY REFERENCES videos(id),
    timeline_json TEXT NOT NULL,   -- Full VideoTimeline as JSON
    game_title TEXT
)

video_reports (
    video_id TEXT PRIMARY KEY REFERENCES videos(id),
    report_json TEXT NOT NULL,     -- Full VideoReport as JSON (includes all moments)
    overall_friction TEXT,
    overall_engagement TEXT,
    overall_stop_risk TEXT,
    bug_count INTEGER
)

study_reports (
    game_key TEXT PRIMARY KEY,     -- normalized game title
    game_title TEXT NOT NULL,
    report_json TEXT NOT NULL,     -- Full StudyReport as JSON
    session_count INTEGER NOT NULL
)
```

---

## Evidence Trust Model

Three layers prevent hallucination:

```
Layer 1: SCHEMA CONSTRAINT
  Every Pydantic model requires evidence fields BEFORE decision fields.
  The LLM structurally cannot produce a conclusion without documenting evidence.
  Example: FrictionMoment requires scene_description, visual_signals, audio_signals,
           verbal_feedback, player_expression → THEN source, severity, stop_risk.

Layer 2: CROSS-AGENT CORROBORATION
  7 independent agents analyze each moment from different lenses.
  Confidence scoring: 0.50 base + 0.15 per corroborating agent + 0.10 for verbal quote.
  A frustration event confirmed by sentiment + retry + verbal = 0.95 confidence.
  Single-agent observations = 0.50 confidence.

Layer 3: EVIDENCE CITATION
  Every CanonicalMoment includes:
  - absolute_timestamp (verifiable against video)
  - evidence[] (visual signals, audio signals, player quotes, scene descriptions)
  - corroborating_agents[] (which other agents confirmed this)
  - segment_label (game area, matchable across sessions)
```

---

## Gemini API Usage Patterns

```
Pattern 1: WARMUP + FORK (cost-efficient multi-agent)
  Create Gemini cache with: system_prompt + video chunk
  Warmup call → shared grounding response
  Fork 7 parallel calls, each reusing cached prefix
  Delete cache after all agents complete
  Result: 7 agents for ~1.5x the cost of a single call

Pattern 2: STRUCTURED OUTPUT
  response_mime_type = "application/json"
  response_schema = PydanticModel
  Gemini returns typed JSON matching the schema
  Fallback: parse response.text if response.parsed is None

Pattern 3: YOUTUBE DIRECT ANALYSIS (no download)
  file_data = FileData(file_uri=youtube_url)
  video_metadata = VideoMetadata(start_offset="300s", end_offset="600s", fps=5)
  Gemini analyzes the YouTube video directly via URL

Pattern 4: THINKING LEVELS
  Timeline pass: "low" (structural mapping, less reasoning needed)
  Specialist agents: "medium" (evidence evaluation + judgment)
  Executive summary: "medium" (synthesis across dimensions)
  Study synthesis: "medium" (cross-session pattern detection)

Pattern 5: RETRY WITH BACKOFF
  ServerError or 429 → retry after 5s, 15s, 45s
  ClientError 400 (cache issue) → fallback to direct (non-cached) agent call
  Safety block → skip chunk entirely
  Optional agents (sentiment/retry/verbal) → catch errors, return None
```

---

## Next Steps: Production Architecture

This section describes the target production architecture with cloud deployment, authentication, voice interface, and enterprise-grade infrastructure.

### Production Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUD RUN (europe-central2)                     │
│                         Fully managed, auto-scaling, HTTPS              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Frontend (Static + CDN)                                        │   │
│  │  React 19 + Vite + Tailwind + shadcn/ui                         │   │
│  │                                                                   │   │
│  │  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐  │   │
│  │  │ Game Search  │  │ Aggregate View   │  │ Voice Agent Widget │  │   │
│  │  │ + Discovery  │  │ N Sessions       │  │ (Vapi embedded)    │  │   │
│  │  └─────────────┘  └──────────────────┘  └────────────────────┘  │   │
│  │                                                                   │   │
│  │  ┌──────────────────────────┐  ┌──────────────────────────────┐  │   │
│  │  │ Tool-Trace Sidebar       │  │ Auth0 Login Gate             │  │   │
│  │  │ Live latency + tool logs │  │ Role badge + approval flow   │  │   │
│  │  └──────────────────────────┘  └──────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│              │                          │                    │           │
│              ▼                          ▼                    ▼           │
│  ┌───────────────────┐  ┌──────────────────────────┐  ┌─────────────┐  │
│  │  Streams Finder   │  │  GameSight Analysis      │  │ Voice Tools │  │
│  │  :8000            │  │  :8001                   │  │ (Webhooks)  │  │
│  │                   │  │                          │  │             │  │
│  │  Gemini queries   │  │  8-Agent Pipeline        │  │ query_frust │  │
│  │  YouTube search   │  │  Cross-Video Studies     │  │ get_stats   │  │
│  │  Twitch search    │  │  Executive Summaries     │  │ compare_seg │  │
│  │  Video verify     │  │  Highlight Reels         │  │ gen_bug_rpt │  │
│  └───────────────────┘  └──────────────────────────┘  └─────────────┘  │
│                                    │                         │          │
├────────────────────────────────────┼─────────────────────────┼──────────┤
│                                    ▼                         ▼          │
│         ┌──────────────────────────────────────────────┐               │
│         │  Google Cloud Platform                       │               │
│         │                                              │               │
│         │  Gemini 3 Flash (Vertex AI)                  │               │
│         │    Video + Audio + Facecam — one native pass  │               │
│         │    1M token context, prefix caching           │               │
│         │    Structured JSON via Pydantic schemas       │               │
│         │                                              │               │
│         │  Secret Manager                              │               │
│         │    GEMINI_API_KEY, VAPI_API_KEY               │               │
│         │    AUTH0_CLIENT_SECRET, TWITCH_CLIENT_SECRET  │               │
│         │                                              │               │
│         │  Cloud SQL (PostgreSQL) or Firestore          │               │
│         │    Production database replacing SQLite       │               │
│         └──────────────────────────────────────────────┘               │
│                                                                         │
│         ┌────────────────────────┐  ┌──────────────────────────┐       │
│         │  Auth0                 │  │  Vapi                    │       │
│         │                        │  │                          │       │
│         │  Universal Login       │  │  Gemini-backed voice     │       │
│         │  Role-based access     │  │  Multi-tool calling      │       │
│         │  CIBA async approval   │  │  Barge-in support        │       │
│         │  Token Vault           │  │  Webhook → /tools/*      │       │
│         └────────────────────────┘  └──────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Voice Agent — Tool Definitions

```
Tool 1: query_frustration_points
  Input:  { level?: string, severity_min?: int, segment_label?: string }
  Action: Query video_reports for friction moments matching criteria
  Output: { count: int, moments: [{ timestamp, quote, severity, session_id }] }
  Example: "What should I fix first?" → queries sev≥7 → "The bridge jump in Level 3"

Tool 2: get_cross_video_stats
  Input:  { segment_label?: string, metric?: string }
  Action: Query study_reports, aggregate by segment
  Output: { segment, failure_rate, avg_sentiment, quit_signal_rate, sessions }
  Example: "How does combat compare to the bridge?" → segment comparison

Tool 3: generate_bug_report
  Input:  { segment_label: string, title: string }
  Action: Aggregate evidence → structured bug report → Auth0 approval
  Output: { report_id, title, severity, sessions_affected, status: "pending_approval" }
  Example: "File a bug report for the bridge" → P1 report → approve via Auth0

Tool 4: compare_segments
  Input:  { segments: [string, string] }
  Action: Side-by-side segment fingerprint comparison
  Output: { comparisons: [{ metric, segment_a_value, segment_b_value }] }
```

---

### Auth0 Integration

```
1. LOGIN GATE
   User visits dashboard → Auth0 Universal Login
   Returns JWT with role claim: "qa_director" or "viewer"
   Frontend shows role badge: "QA Director: Sarah Chen"

2. API AUTHORIZATION
   All /tools/* and /studies/*/analyze endpoints require Bearer token
   Auth0 middleware validates JWT + checks role permissions
   Viewers: read-only access to reports
   QA Directors: can trigger analysis, approve bug reports

3. BUG REPORT APPROVAL (CIBA)
   Voice agent says "Drafting bug report. Sending for approval."
   Backend initiates Auth0 CIBA flow → push notification to QA lead
   QA lead approves/denies on phone
   Agent responds: "Approved and filed." or "Denied by QA lead."
```

---

### Cloud Run Deployment

```bash
# Deploy GameSight Analysis
gcloud run deploy gamesight-analysis \
  --source ./src/gamesight \
  --region europe-central2 \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --memory 2Gi \
  --timeout 600

# Deploy Streams Finder
gcloud run deploy streams-finder \
  --source ./streams-finder \
  --region europe-central2 \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"

# Deploy Frontend (static build)
gcloud run deploy gamesight-frontend \
  --source ./inshights-frontend \
  --region europe-central2

# Store secrets
gcloud secrets create gemini-api-key --data-file=- <<< "$GEMINI_API_KEY"
gcloud secrets create auth0-secret --data-file=- <<< "$AUTH0_CLIENT_SECRET"
gcloud secrets create vapi-key --data-file=- <<< "$VAPI_API_KEY"
```

---

### Key Metrics

| Metric | Value |
|--------|-------|
| Cost per study (vs $50,000 traditional) | ~$3 |
| Speed improvement | 600x |
| Cost per minute of video | ~$0.05 |
| Agents per video chunk | 8 (parallel) |
| Context window | 1M tokens |
| Pricing (indie) | $99/month (up to 100 videos) |
| Pricing (studio) | $999/month (unlimited) |
| Gross margin | 97% |
