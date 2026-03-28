# GameSight AI

**Automated gameplay video analysis for game studios** — turn raw player videos into structured, actionable feedback using Gemini 3 Flash multimodal AI.

Built at [AI Tinkerers Poland Hackathon](https://aitinkerers.org) (March 28, 2026) by team **Research.tech**.

---

## The Problem

Game developers rely on player feedback to improve their games, but:

- **Players leave vague reviews:** "Don't recommend, it sucks" with zero explanation
- **Nobody writes detailed feedback:** Players won't spend 10 minutes writing what went wrong
- **Watching playtest videos manually doesn't scale:** A studio with 100 testers generates hundreds of hours of footage
- **Existing analytics (telemetry, heatmaps) show WHAT happened, not WHY** — they can't capture frustration, confusion, or delight

**The gap:** There's no automated way to extract qualitative player feedback from gameplay video at scale.

## The Solution

GameSight AI watches gameplay videos and extracts structured feedback automatically:

- **Sentiment analysis** — detect frustration, excitement, boredom, confusion from both audio reactions and visual behavior
- **Key moment detection** — timestamped events where players struggle, celebrate, get stuck, or disengage
- **Mechanic engagement tracking** — what game features players interact with most, what they skip
- **UI/UX friction points** — where players hesitate, misclick, or look confused
- **Verbal feedback extraction** — what players say out loud (commentary, complaints, praise)
- **Cross-video aggregation** — "73% of players got frustrated at the bridge section", "most praised feature: combat system"

### How It Works

```
YouTube/Video URL --> Download --> Chunk (5-10 min segments) --> Gemini 3 Flash Analysis --> Structured JSON --> FastAPI serves results
```

1. **Input:** YouTube URLs, direct video uploads, or any video source
2. **Download & Chunk:** yt-dlp downloads videos, ffmpeg splits into analyzable segments
3. **AI Analysis:** Each chunk is uploaded to Gemini 3 Flash via Files API, analyzed with structured output prompts
4. **Structured Output:** Pydantic models define the exact feedback schema — Gemini returns typed JSON
5. **Aggregation:** Cross-video insights are computed from individual analyses
6. **API:** FastAPI serves results for dashboards and integrations

### Business Model

**Target:** Game studios during testing phases (alpha/beta testing, paid playtesting programs).

**Integration:** Minimal — the system only needs video input from players. No SDK integration into the game engine required. Works with:
- Screen recordings from testers
- YouTube/Twitch gameplay videos
- Streaming captures
- Any video source

---

## Tech Stack

### Core AI
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **LLM** | Gemini 3 Flash Preview | `gemini-3-flash-preview` | Multimodal video + audio analysis |
| **SDK** | Google GenAI Python SDK | `google-genai` 1.68.0 | Gemini API client |

**Why Gemini 3 Flash:**
- 1M token context window — handles up to ~1 hour of video per request
- Native multimodal: analyzes video frames (1 FPS) + audio simultaneously
- Efficient video tokenization: 70 tokens/frame (vs 258 in older models)
- Structured JSON output via Pydantic `response_schema`
- `thinking_level` parameter for controlling reasoning depth
- Cost: ~$0.003/min of video at default resolution (~$3.00 for entire 100-video demo)

### Backend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **API Framework** | FastAPI | 0.135.x | Async REST API with auto-generated OpenAPI docs |
| **Data Models** | Pydantic v2 | 2.12.x | Structured analysis schemas + validation |
| **Database** | SQLite + aiosqlite | 0.22.x | Lightweight async storage for analysis results |
| **Server** | Uvicorn | latest | ASGI server |

### Video Processing
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Downloader** | yt-dlp | 2026.3.x | YouTube video download + metadata extraction |
| **Chunking** | ffmpeg-python | 0.2.0 | Split videos into 5-10 min segments via segment muxer |
| **Runtime** | FFmpeg | system | Required by both yt-dlp and ffmpeg-python |

### Python
- **Python 3.14+**
- **Ruff** for linting/formatting
- **uv** for dependency management

---

## Repository Structure

```
gamesight/
├── README.md
├── pyproject.toml
├── .env.example                  # GEMINI_API_KEY placeholder
│
├── src/
│   ├── __init__.py
│   │
│   ├── models/                   # Pydantic schemas (shared across all modules)
│   │   ├── __init__.py
│   │   ├── analysis.py           # GameplayFeedback, KeyMoment, FrustrationPoint, etc.
│   │   ├── video.py              # VideoMetadata, VideoChunk, ProcessingStatus
│   │   └── aggregation.py        # AggregatedInsights, CrossVideoStats
│   │
│   ├── analysis/                 # Core Gemini video analysis
│   │   ├── __init__.py
│   │   ├── analyzer.py           # Upload to Gemini, analyze chunk, parse response
│   │   ├── prompts.py            # Prompt templates for gameplay analysis
│   │   └── aggregator.py         # Cross-video aggregation logic
│   │
│   ├── video/                    # Video acquisition and processing
│   │   ├── __init__.py
│   │   ├── downloader.py         # yt-dlp wrapper: download videos + extract metadata
│   │   └── chunker.py            # ffmpeg chunking: split video into segments
│   │
│   ├── api/                      # FastAPI application
│   │   ├── __init__.py
│   │   ├── app.py                # FastAPI app, CORS, lifespan
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── videos.py         # POST /videos, GET /videos
│   │   │   ├── analysis.py       # GET /analysis/{video_id}
│   │   │   └── insights.py       # GET /insights (aggregated)
│   │   └── deps.py               # Dependency injection (DB session, Gemini client)
│   │
│   └── db/                       # Database layer
│       ├── __init__.py
│       ├── database.py           # SQLite + aiosqlite setup
│       └── repository.py         # CRUD operations
│
├── scripts/                      # Standalone CLI scripts
│   ├── download_videos.py        # Bulk download from YouTube URL list
│   ├── process_videos.py         # Bulk analyze downloaded videos
│   └── seed_demo.py              # Seed database with pre-processed demo data
│
├── data/                         # Pre-processed demo data
│   ├── demo_videos.json          # 50-100 YouTube URLs for demo
│   └── demo_results/             # Pre-computed analysis results
│
└── .tmp/                         # Temporary files (gitignored)
```

---

## API Endpoints

### Videos
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/videos` | Submit a YouTube URL or video for analysis |
| `GET` | `/videos` | List all submitted videos with processing status |
| `GET` | `/videos/{video_id}` | Get video metadata and processing status |

### Analysis
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analysis/{video_id}` | Full analysis results for a video |
| `GET` | `/analysis/{video_id}/moments` | Key moments with timestamps |
| `GET` | `/analysis/{video_id}/sentiment` | Sentiment timeline for a video |

### Insights (Aggregated)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/insights` | Cross-video aggregated insights |
| `GET` | `/insights/frustration` | Top frustration points across all videos |
| `GET` | `/insights/engagement` | Engagement metrics across all videos |
| `GET` | `/insights/features` | Most discussed game features/mechanics |

---

## Analysis Schema

The core output schema for each video chunk analysis:

```python
class KeyMoment(BaseModel):
    timestamp: str          # MM:SS format
    event_type: Literal["frustration", "excitement", "confusion",
                         "boredom", "achievement", "discovery"]
    description: str        # What happened
    evidence: str           # Observable audio/visual evidence
    severity: int           # 1-10 scale

class GameplayFeedback(BaseModel):
    overall_sentiment: Literal["positive", "neutral", "negative", "mixed"]
    engagement_score: int                    # 1-10
    key_moments: list[KeyMoment]
    frustration_points: list[KeyMoment]
    praised_features: list[str]
    criticized_features: list[str]
    ui_ux_issues: list[str]
    player_commentary_summary: str
    time_spent_breakdown: dict[str, float]   # % time on: combat, exploration, menu, etc.
    recommendations: list[str]               # Actionable suggestions for devs
```

---

## Gemini 3 Flash Integration

### Model Configuration
```python
from google import genai
from google.genai import types

client = genai.Client()  # Uses GEMINI_API_KEY env var

# Upload video chunk via Files API
video = client.files.upload(file="chunk_001.mp4")

# Poll until processing complete
while video.state.name == "PROCESSING":
    video = client.files.get(name=video.name)

# Analyze with structured output
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[video, ANALYSIS_PROMPT],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GameplayFeedback,
        thinking_level="medium",
    ),
)

result: GameplayFeedback = response.parsed
```

### Video Token Economics
| Resolution | Tokens/Frame | Tokens/Min (video+audio) | Cost/Min | 1hr Cost |
|-----------|-------------|-------------------------|----------|----------|
| Default (70 tok/frame @ 1 FPS) | 70 | ~6,120 | ~$0.003 | ~$0.18 |
| High (280 tok/frame) | 280 | ~18,720 | ~$0.009 | ~$0.56 |

**Demo dataset cost:** 100 videos x 10 min avg = 1,000 min x $0.003 = **~$3.00 total input cost**

### Key Documentation
- Gemini 3 Guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Video Understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Structured Outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Files API: https://ai.google.dev/gemini-api/docs/files
- Media Resolution: https://ai.google.dev/gemini-api/docs/media-resolution
- Python SDK: https://github.com/googleapis/python-genai
- Pricing: https://ai.google.dev/gemini-api/docs/pricing

---

## Demo Plan

1. **Pre-compute:** Bulk-analyze 50-100 gameplay videos from 2-3 games
2. **Dashboard data:** Serve pre-computed results via FastAPI
3. **Live demo:** Process 1-2 new YouTube URLs live during presentation
4. **Key showcases:**
   - Per-video analysis with timestamped moments
   - Cross-video aggregation: "Here's what 80 players think about your game"
   - Cost efficiency: entire demo dataset analyzed for ~$3

---

## Competitive Advantage

| Feature | GameSight AI | PlaytestCloud | GameAnalytics | Unity Analytics |
|---------|-------------|---------------|---------------|-----------------|
| Video analysis | Multimodal (frames + audio) | Transcript-only | None | None |
| Visual cue detection | Yes | No | No | No |
| Audio sentiment | Yes (tone, emotion) | Speech-to-text only | No | No |
| Integration effort | Zero (just video) | SDK + panel | SDK | SDK |
| Structured output | Typed JSON schemas | PDF reports | Dashboards | Dashboards |
| Self-hosted | Yes | No | No | No |
| Cost per video | ~$0.003/min | $$$$ per study | N/A | N/A |

---

## Setup

```bash
# Install dependencies
uv sync

# Configure
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Run API server
uv run uvicorn src.api.app:app --reload

# Analyze a single video
uv run python scripts/process_videos.py --url "https://youtube.com/watch?v=..."

# Bulk download demo videos
uv run python scripts/download_videos.py --input data/demo_videos.json

# Bulk process
uv run python scripts/process_videos.py --input-dir data/videos/
```

---

## License

MIT
