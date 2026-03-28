# GameSight AI — Development Guide

Complete technical reference for building the GameSight AI gameplay video analysis pipeline. All patterns are cross-verified from SDK source code, official documentation, and multiple AI research agents.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Google GenAI SDK Reference](#2-google-genai-sdk-reference)
3. [Gemini 3 Flash Configuration](#3-gemini-3-flash-configuration)
4. [Video Analysis Pipeline](#4-video-analysis-pipeline)
5. [Pydantic Schemas](#5-pydantic-schemas)
6. [Prompt Engineering](#6-prompt-engineering)
7. [yt-dlp Video Downloader](#7-yt-dlp-video-downloader)
8. [ffmpeg Video Chunking](#8-ffmpeg-video-chunking)
9. [Database Layer (aiosqlite)](#9-database-layer-aiosqlite)
10. [FastAPI Endpoints](#10-fastapi-endpoints)
11. [Error Handling & Retries](#11-error-handling--retries)
12. [Cost Optimization](#12-cost-optimization)
13. [Gotchas Checklist](#13-gotchas-checklist)
14. [Risks & Mitigations](#14-risks--mitigations)
15. [Key Documentation Links](#15-key-documentation-links)

---

## 1. Environment Setup

### Dependencies

```toml
# pyproject.toml
[project]
name = "gamesight"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "google-genai>=1.68.0",
    "yt-dlp>=2026.3.0",
    "ffmpeg-python>=0.2.0",
    "fastapi>=0.135.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.12.0",
    "aiosqlite>=0.22.0",
    "python-multipart>=0.0.20",
]

[tool.ruff]
line-length = 160
target-version = "py314"
```

### Environment Variables

```bash
# .env
GEMINI_API_KEY=your_api_key_here    # or GOOGLE_API_KEY (takes priority if both set)
DATABASE_PATH=gamesight.db
DATA_DIR=data
```

### System Requirements

- Python 3.14+
- ffmpeg + ffprobe on PATH (required by both yt-dlp and ffmpeg-python)
- Internet access for Gemini API and YouTube downloads

---

## 2. Google GenAI SDK Reference

**Package:** `google-genai` v1.68.0
**GitHub:** https://github.com/googleapis/python-genai
**Docs:** https://googleapis.github.io/python-genai/

### Client Initialization

```python
from google import genai

# Option A: Explicit API key (keyword-only)
client = genai.Client(api_key="YOUR_API_KEY")

# Option B: From environment variable (auto-detected)
# Priority: GOOGLE_API_KEY > GEMINI_API_KEY
# If both set, logs warning, uses GOOGLE_API_KEY
client = genai.Client()

# Option C: Context manager (auto-closes httpx connections)
with genai.Client(api_key="YOUR_API_KEY") as client:
    ...
```

**Source:** `client.py:376-386` — all params are keyword-only. `_api_client.py:108-115` — env var priority.

### File Upload + Poll Until Active

```python
import time
from google import genai
from google.genai import types

client = genai.Client()

# Upload — returns types.File
# mime_type is auto-detected from extension if not provided
video_file = client.files.upload(file="path/to/video.mp4")

# Poll — state does NOT update in-place; must re-fetch
while True:
    if video_file.state and video_file.state.name == "ACTIVE":
        break
    if video_file.state and video_file.state.name == "FAILED":
        raise RuntimeError(f"Video processing failed: {video_file.error}")
    time.sleep(5)
    video_file = client.files.get(name=video_file.name)
```

**Key types from source:**
- `FileState` enum (`types.py:1018`): `STATE_UNSPECIFIED`, `PROCESSING`, `ACTIVE`, `FAILED`
- `File.state` can be `None` initially — always guard with `if video_file.state and ...`
- `File.error` is `Optional[FileStatus]` with `message`, `code`, `details`
- Files API is **Gemini Developer API only** — raises `ValueError` on Vertex AI
- `upload()` accepts: `file: str | os.PathLike | io.IOBase`
- Files retained for 48 hours, up to 2GB per file, 20GB per project

### generate_content with Structured Output

```python
from pydantic import BaseModel, Field
from google.genai import types

class VideoAnalysis(BaseModel):
    summary: str = Field(description="Brief summary")
    key_topics: list[str] = Field(description="Main topics")

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[video_file, "Analyze this video."],  # video FIRST, prompt SECOND
    config=types.GenerateContentConfig(
        response_mime_type="application/json",   # REQUIRED with response_schema
        response_schema=VideoAnalysis,           # Pydantic CLASS, NOT instance
    ),
)
```

**Critical rules:**
- `response_mime_type="application/json"` is **mandatory** with `response_schema`
- Pass the **class itself** (`VideoAnalysis`), not an instance or `.model_json_schema()`
- `contents` accepts: `str`, `File`, `Part`, `Content`, or `list` of these
- Video should come **before** text prompt in the list
- Do NOT send both `response_schema` and `response_json_schema`

### response_schema Type Behavior

| Input Type | `response.parsed` Result |
|---|---|
| `pydantic.BaseModel` subclass | Typed Pydantic instance |
| `list[str]`, `int`, etc. | Native Python type |
| `Enum` or `Literal["a","b"]` | Enum value or string |
| `dict` or `types.Schema` | Plain `dict` |
| Via `response_json_schema=Model.model_json_schema()` | Plain `dict` (not typed) |

### Accessing response.parsed

```python
# Type: Optional[Union[pydantic.BaseModel, dict, Enum]]
analysis: VideoAnalysis = response.parsed

# ALWAYS check for None — parse failures are SILENT (no exception)
if response.parsed is None:
    # Fallback: manual parse for better error messages
    try:
        analysis = VideoAnalysis.model_validate_json(response.text)
    except Exception as e:
        print(f"Parse failed: {e}")
        print(f"Raw response: {response.text}")
        raise
else:
    analysis = response.parsed
```

**How `parsed` works** (verified at `types.py:8027-8138`):
1. SDK extracts `response_schema` from the original request kwargs
2. For Pydantic BaseModel: calls `response_schema.model_validate_json(result_text)`
3. On `ValidationError` or `JSONDecodeError`: **silently sets `parsed = None`**

### Async Version

```python
import asyncio
from google import genai
from google.genai import types

async def analyze_video(path: str) -> VideoAnalysis:
    client = genai.Client()

    try:
        # All async methods live under client.aio.*
        video_file = await client.aio.files.upload(file=path)

        while True:
            if video_file.state and video_file.state.name == "ACTIVE":
                break
            if video_file.state and video_file.state.name == "FAILED":
                raise RuntimeError("Video processing failed")
            await asyncio.sleep(5)
            video_file = await client.aio.files.get(name=video_file.name)

        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[video_file, "Analyze this video."],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VideoAnalysis,
            ),
        )

        if response.parsed is None:
            raise ValueError(f"Parse failed: {response.text}")
        return response.parsed

    finally:
        await client.aio.aclose()
        client.close()
```

### Token Counting

```python
# Before generation — estimate cost
token_info = client.models.count_tokens(
    model="gemini-3-flash-preview",
    contents=[video_file, "Analyze this video."],
)
print(f"Total tokens: {token_info.total_tokens}")

# After generation — actual usage
response = client.models.generate_content(...)
meta = response.usage_metadata
print(f"Prompt: {meta.prompt_token_count}")
print(f"Output: {meta.candidates_token_count}")
print(f"Total:  {meta.total_token_count}")
```

### YouTube Direct Analysis (No Download)

```python
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=types.Content(parts=[
        types.Part(file_data=types.FileData(
            file_uri="https://www.youtube.com/watch?v=VIDEO_ID"
        )),
        types.Part(text="Analyze this video."),
    ]),
)
```

**Limitations:** Public videos only, 8hr/day free tier, no explicit caching, preview feature.

### YouTube URL with Clipping + Custom FPS

```python
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=types.Content(parts=[
        types.Part(
            file_data=types.FileData(
                file_uri="https://www.youtube.com/watch?v=VIDEO_ID"
            ),
            video_metadata=types.VideoMetadata(
                start_offset="120s",
                end_offset="420s",
                fps=5,
            ),
        ),
        types.Part(text="Analyze this segment."),
    ]),
)
```

### Context Caching (for Repeated Queries on Same Video)

```python
# Create cache
cache = client.caches.create(
    model="models/gemini-3-flash-preview",
    config=types.CreateCachedContentConfig(
        display_name="gamesight-video",
        system_instruction="You are an expert gameplay analyzer.",
        contents=[video_file],
        ttl="3600s",  # 1 hour
    )
)

# Query N times against the cache (10x cheaper input tokens)
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="What are the frustration points?",
    config=types.GenerateContentConfig(
        cached_content=cache.name,
        response_mime_type="application/json",
        response_schema=GameplayFeedback,
    )
)

# Cleanup
client.caches.delete(name=cache.name)
client.files.delete(name=video_file.name)
```

**Constraints:**
- Minimum 1,024 cached tokens for Flash
- Cached content acts as a prefix — cannot change system_instruction per query
- YouTube URLs cannot be explicitly cached — must upload file first
- Break-even: 2+ queries within TTL window

### Error Hierarchy

```
errors.APIError(Exception)         # .code, .status, .message, .response, .details
├── errors.ClientError(APIError)   # 4xx
└── errors.ServerError(APIError)   # 5xx
```

---

## 3. Gemini 3 Flash Configuration

**Model ID:** `gemini-3-flash-preview`
**Context:** 1,048,576 input tokens / 65,536 output tokens
**Knowledge cutoff:** January 2025
**Status:** Preview (may change, more restrictive rate limits)

### thinking_level Parameter

Controls reasoning depth before producing a response.

```python
config=types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level="medium")
)
```

| Level | Behavior | Use Case |
|---|---|---|
| `"minimal"` | Minimizes latency; may still think for complex tasks | Never for video analysis (too shallow) |
| `"low"` | Minimizes latency and cost | **Bulk pre-compute** (100 videos) |
| `"medium"` | Balanced | **Default for our project** |
| `"high"` | Maximum reasoning depth; higher latency | Live demo, deep-dive on flagged segments |

**Default when omitted is `"high"`** — explicitly set `"medium"` or `"low"` to save cost.

**Hard rule:** Never combine `thinking_level` with legacy `thinking_budget` — returns 400 error.

### media_resolution Parameter

Controls tokens per video frame. Gemini 3 uses a new variable-sequence approach.

```python
config=types.GenerateContentConfig(
    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW
)
```

| Setting | Tokens/Frame (Video) | When to Use |
|---|---|---|
| `MEDIA_RESOLUTION_LOW` | 70 | General video (same as MEDIUM) |
| `MEDIA_RESOLUTION_MEDIUM` | 70 | General video (same as LOW) |
| `MEDIA_RESOLUTION_HIGH` | 280 | Text-in-video / OCR / small details |
| Default (unset) | 70 | **Recommended — sufficient for gameplay analysis** |

**ULTRA_HIGH** exists only for per-part resolution (requires `v1alpha` API), not for global config.

**Our recommendation:** Don't set `media_resolution` at all. Default 70 tokens/frame is sufficient. Only escalate to HIGH when reading small text in video (game UI, chat messages).

### Temperature

**DO NOT SET. Leave at default 1.0.**

All sources unanimously agree: setting temperature below 1.0 on Gemini 3 causes **looping or degraded performance** on complex reasoning tasks.

### Thought Signatures

Encrypted representations of internal reasoning maintained across multi-turn API calls.
- **Function calling:** Missing signatures = 400 error
- **Chat:** Omission degrades quality
- **Official SDKs handle this automatically** — no manual management needed

### Pricing (Paid Tier)

| Resource | Standard | Batch (50% off) |
|---|---|---|
| Input (text/image/video) | $0.50 / 1M tokens | $0.25 / 1M tokens |
| Input (audio) | $1.00 / 1M tokens | $0.50 / 1M tokens |
| Output (incl. thinking) | $3.00 / 1M tokens | $1.50 / 1M tokens |
| Cached input (text/image/video) | $0.05 / 1M tokens | $0.05 / 1M tokens |
| Cache storage | $1.00 / 1M tokens / hour | $1.00 / 1M tokens / hour |

### Video Token Economics

| Resolution | Tokens/Frame | Tokens/Min (video+audio) | Cost/Min | 1hr Cost |
|---|---|---|---|---|
| Default (70 tok/frame @ 1 FPS) | 70 | ~6,120 | ~$0.003 | ~$0.18 |
| HIGH (280 tok/frame) | 280 | ~18,720 | ~$0.009 | ~$0.56 |

**Demo dataset (100 videos x 10 min avg):** ~$3–6 total input cost.

### Rate Limits

- Per-project, not per API key
- Preview models have more restrictive limits
- Tier-based: Free → Tier 1 ($250 cap) → Tier 2 ($2000 cap) → Tier 3
- Check exact limits at https://aistudio.google.com/rate-limit

---

## 4. Video Analysis Pipeline

### Architecture

```
URL ──> yt-dlp (metadata + download) ──> ffmpeg (chunk if needed)
    ──> Gemini Files API (upload + poll) ──> generate_content (structured output)
    ──> aiosqlite (persist) ──> FastAPI (serve)
```

### Strategy: Hybrid Input

| Path | When | Why |
|---|---|---|
| **YouTube URL direct** (`file_uri`) | Live demo (1-2 videos) | Zero latency, instant, impressive |
| **yt-dlp download + Files API upload** | Bulk pre-compute (50-100 videos) | Cacheable, re-analyzable, no 8hr/day limit |

### Chunking Decision Tree

```
Input video
    │
    ├─ Duration < 45 min? ──> Send whole to Gemini (no chunking)
    │                          Maybe downscale if >720p (for upload speed only)
    │
    └─ Duration >= 45 min? ──> Chunk into 30-min segments
                                15s overlap between chunks
                                Stream copy (fast) unless downscaling
```

**Why 45 min threshold:** At default resolution (70 tok/frame + 32 tok/sec audio = ~6,120 tokens/min), a 45-min video uses ~275K tokens — only 26% of the 1M context window. Plenty of room.

**Downscaling does NOT save tokens.** Gemini's token count per frame is determined by `media_resolution`, not pixel resolution. A 4K video at default res costs the same as 480p. Downscale only for upload bandwidth.

---

## 5. Pydantic Schemas

### Core Analysis Schema

```python
import enum
from pydantic import BaseModel, Field


class EventType(str, enum.Enum):
    FRUSTRATION = "frustration"
    EXCITEMENT = "excitement"
    CONFUSION = "confusion"
    BOREDOM = "boredom"
    ACHIEVEMENT = "achievement"
    DISCOVERY = "discovery"
    STRUGGLE = "struggle"


class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class EmotionLabel(str, enum.Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CONFUSED = "confused"
    BORED = "bored"


class KeyMoment(BaseModel):
    timestamp: str = Field(description="Timestamp in MM:SS format from the video")
    event_type: EventType = Field(description="Type of gameplay event detected")
    description: str = Field(description="What happened in 1-2 sentences")
    evidence: str = Field(description="Observable audio/visual evidence supporting this classification")
    player_expression: str | None = Field(description="Facecam: facial expression, posture, gestures. None if no facecam visible")
    player_emotion: EmotionLabel = Field(description="Detected player emotion at this moment")
    severity: int = Field(description="Impact severity from 1 (minor) to 10 (critical)", ge=1, le=10)


class VerbalComment(BaseModel):
    timestamp: str = Field(description="Timestamp in MM:SS format")
    quote: str = Field(description="What the player said (direct quote or close paraphrase)")
    sentiment: SentimentLabel = Field(description="Sentiment of the verbal comment")
    topic: str = Field(description="What game element the comment is about")


class UIFrictionPoint(BaseModel):
    timestamp: str = Field(description="Timestamp in MM:SS format")
    description: str = Field(description="What UI/UX issue was observed")
    evidence: str = Field(description="How you detected this: hesitation, misclick, confusion, etc.")


class GameplayFeedback(BaseModel):
    """Structured analysis of a gameplay video segment."""
    overall_sentiment: SentimentLabel = Field(
        description="Overall player sentiment across the entire segment"
    )
    engagement_score: int = Field(
        description="Overall engagement level from 1 (disengaged) to 10 (highly engaged)",
        ge=1, le=10,
    )
    segment_summary: str = Field(
        description="2-3 sentence summary of what happened in this video segment"
    )
    key_moments: list[KeyMoment] = Field(
        description="Important gameplay events with timestamps, sorted chronologically"
    )
    verbal_comments: list[VerbalComment] = Field(
        description="Notable things the player said out loud, with timestamps"
    )
    ui_friction_points: list[UIFrictionPoint] = Field(
        description="UI/UX issues observed: hesitations, misclicks, confusion"
    )
    praised_features: list[str] = Field(
        description="Game features/mechanics the player appeared to enjoy"
    )
    criticized_features: list[str] = Field(
        description="Game features/mechanics the player appeared to dislike"
    )
    game_mechanics_observed: list[str] = Field(
        description="Game mechanics/systems the player interacted with"
    )
    recommendations: list[str] = Field(
        description="Actionable suggestions for game developers based on this session"
    )
```

**Design rationale:**
- `str` enums produce human-readable JSON values (not integer ordinals)
- `Field(description=...)` on every field — the SDK sends these to Gemini and they **significantly improve structured output quality**
- Flat structure — Gemini performs better with shallow nesting
- Timestamps as `str` in `MM:SS` — matches Gemini's native timestamp format in video context
- `ge`/`le` constraints guide the model's numeric output range

### Video Metadata Schema

```python
from pydantic import BaseModel


class VideoMetadata(BaseModel):
    video_id: str
    title: str
    url: str
    duration_seconds: float | None
    uploader: str | None
    view_count: int | None
    description: str | None
    tags: list[str]
    thumbnail_url: str | None
    upload_date: str | None


class ProcessingStatus(BaseModel):
    video_id: str
    status: str  # pending | downloading | chunking | analyzing | complete | failed
    chunks_total: int
    chunks_completed: int
    error_message: str | None
```

### Aggregated Insights Schema

```python
class FeatureInsight(BaseModel):
    feature_name: str
    praise_count: int
    criticism_count: int
    net_sentiment: float  # -1.0 to +1.0


class AggregatedInsights(BaseModel):
    total_videos: int
    avg_engagement_score: float
    sentiment_distribution: dict[str, int]  # {"positive": 30, "negative": 10, ...}
    top_frustration_points: list[dict]      # sorted by frequency
    top_praised_features: list[FeatureInsight]
    top_criticized_features: list[FeatureInsight]
    common_recommendations: list[str]
```

---

## 6. Prompt Engineering

### System Prompt

```python
SYSTEM_PROMPT = """You are GameSight AI, an expert gameplay analyst for game studios.

You watch gameplay videos and extract structured feedback that helps game developers
improve their games. You analyze three evidence channels:
- Visual gameplay: on-screen actions, game state, UI interactions
- Audio: player voice, tone, reactions, game audio
- Player face/body: if a facecam or webcam overlay is visible, observe facial expressions,
  posture changes, gestures (leaning forward, head in hands, fist pump, etc.)

Your analysis principles:
- Be specific: reference exact timestamps, exact on-screen events, exact player quotes
- Distinguish between visual evidence, audio evidence, and player expression evidence
- Focus on actionable insights that game developers can act on
- Rate severity honestly: a minor camera issue is 2/10, a game-breaking bug is 9/10
- If the player says nothing, note it — silence during intense moments can indicate focus OR disengagement
- Don't invent moments that aren't there. If the segment is uneventful, say so with fewer key_moments
- If no player audio is present, analyze only visual gameplay behavior
- If no facecam is visible, skip body/face observations"""
```

### Analysis Prompt

```python
GAMEPLAY_ANALYSIS_PROMPT = """Analyze this gameplay video segment carefully.

Watch the ENTIRE segment and listen to the player's audio (voice, reactions, commentary).

For each key moment you identify:
1. Note the exact timestamp (MM:SS format)
2. Classify the event type (frustration, excitement, confusion, boredom, achievement, discovery, struggle)
3. Describe what happened on screen AND what the player said/reacted
4. Rate the severity/impact (1-10)

Pay special attention to:
- **Frustration signals:** repeated failed attempts, sighs, cursing, pausing, menu-checking, facecam: furrowed brow, head shaking, head in hands
- **Confusion signals:** aimless wandering, re-reading UI elements, hesitation, asking "what do I do?", facecam: squinting, confused expression
- **Excitement signals:** leaning forward, exclaiming, rapid actions, "oh wow", "that's cool", facecam: smiling, wide eyes, fist pump
- **Boredom signals:** long pauses, tabbing out, monotone voice, repetitive actions, facecam: looking away, slumped posture
- **UI/UX friction:** hovering over wrong buttons, misinterpreting icons, missing prompts
- **Verbal feedback:** any direct commentary about game features, difficulty, fun, or problems

For the segment summary: describe what game section this covers, what the player was trying to do, and whether they succeeded.

For recommendations: focus on what the game studio should change, fix, or keep based on this player's experience."""
```

### Complete API Call Pattern

```python
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[video_file, GAMEPLAY_ANALYSIS_PROMPT],
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=GameplayFeedback,
        thinking_config=types.ThinkingConfig(thinking_level="medium"),
        # DO NOT set temperature — default 1.0 is correct for Gemini 3
        # DO NOT set media_resolution — default 70 tok/frame is sufficient
    ),
)
```

---

## 7. yt-dlp Video Downloader

**Package:** `yt-dlp` v2026.3.x
**GitHub:** https://github.com/yt-dlp/yt-dlp

### Download at 720p MP4

```python
import yt_dlp

FORMAT_720P_MP4 = (
    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo[height<=720]+bestaudio"
    "/best[height<=720]"
    "/best"
)

ydl_opts = {
    "format": FORMAT_720P_MP4,
    "merge_output_format": "mp4",
    "paths": {"home": "./data/videos"},
    "outtmpl": {"default": "%(id)s.%(ext)s"},   # MUST contain %(id)s for batch
    "noplaylist": True,
    "restrictfilenames": True,
    "retries": 10,
    "fragment_retries": 10,
    "concurrent_fragment_downloads": 4,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://youtube.com/watch?v=...", download=True)
```

**Why 720p:** Gemini tokenizes video at 70 tokens/frame regardless of resolution. 720p saves ~60% bandwidth/storage vs 1080p with identical analysis quality.

### Extract Metadata Only (No Download)

```python
with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
    info = ydl.extract_info(url, download=False)

    # IMPORTANT: extract_info returns non-serializable objects
    # Use sanitize_info() if you need JSON-safe output
    safe_info = ydl.sanitize_info(info)

    title = info.get("title")
    duration = info.get("duration")       # seconds
    uploader = info.get("uploader")
    view_count = info.get("view_count")
    description = info.get("description")
    tags = info.get("tags") or []
```

### Batch Download with Pre-Filtering

```python
# Phase 1: Extract metadata for all URLs, filter by duration
to_download = []
for url in urls:
    with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        if info and 60 <= (info.get("duration") or 0) <= 7200:
            to_download.append(url)

# Phase 2: Batch download with error tolerance
ydl_opts = {
    "format": FORMAT_720P_MP4,
    "merge_output_format": "mp4",
    "paths": {"home": "./data/videos"},
    "outtmpl": {"default": "%(id)s.%(ext)s"},
    "noplaylist": True,
    "ignoreerrors": "only_download",         # CRITICAL: continue through failures
    "download_archive": "./data/archive.txt", # skip already-downloaded
    "sleep_interval": 3,                      # seconds between downloads
    "max_sleep_interval": 10,
    "retries": 10,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(to_download)
```

### Progress Tracking

```python
def on_progress(d: dict):
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "?%")
        speed = d.get("_speed_str", "?")
        print(f"  {pct} at {speed}")
    elif d["status"] == "finished":
        print(f"  Done: {d['filename']}")

ydl_opts["progress_hooks"] = [on_progress]
```

### yt-dlp Logger Adapter

```python
import logging

class YtDlpLogger:
    """Routes yt-dlp messages to Python logging.
    Gotcha: both debug AND info messages go to debug().
    Info messages lack the '[debug] ' prefix."""
    def debug(self, msg: str):
        if msg.startswith("[debug] "):
            logging.debug(msg)
        else:
            logging.info(msg)

    def info(self, msg: str):
        logging.info(msg)

    def warning(self, msg: str):
        logging.warning(msg)

    def error(self, msg: str):
        logging.error(msg)

ydl_opts["logger"] = YtDlpLogger()
```

### yt-dlp Gotchas

1. **`ignoreerrors` defaults to `False` for API** (different from CLI) — batch MUST set `"only_download"`
2. **`extract_info` returns non-serializable objects** — always `sanitize_info()` for JSON
3. **`format: "best"` is a trap** — gives pre-merged low quality; use `bestvideo+bestaudio`
4. **`format: "mp4"` is also a trap** — use format filters + `merge_output_format` instead
5. **ffmpeg REQUIRED** for merging separate video+audio streams
6. **`SameFileError` on batch** — `outtmpl` MUST contain `%(id)s` or similar variable
7. **Logger quirk** — info messages go to `debug()` without `[debug] ` prefix
8. **Always use context manager** — `with YoutubeDL(...) as ydl:` for proper cleanup
9. **`download()` returns int error code** — use `extract_info(url, download=True)` to get info dict

---

## 8. ffmpeg Video Chunking

**Package:** `ffmpeg-python` v0.2.0
**GitHub:** https://github.com/kkroening/ffmpeg-python

### Get Video Duration/Metadata

```python
import ffmpeg
from fractions import Fraction

def probe_video(input_path: str) -> dict:
    probe = ffmpeg.probe(input_path)
    fmt = probe["format"]
    video = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)

    fps = None
    if video and video.get("r_frame_rate"):
        try:
            fps = float(Fraction(video["r_frame_rate"]))
        except (ValueError, ZeroDivisionError):
            pass

    return {
        "duration": float(fmt["duration"]),
        "width": int(video["width"]) if video else 0,
        "height": int(video["height"]) if video else 0,
        "codec": video.get("codec_name") if video else None,
        "fps": fps,
        "audio_codec": audio.get("codec_name") if audio else None,
        "file_size": int(fmt.get("size", 0)),
    }
```

### Split Video into Chunks (Stream Copy — Fast)

```python
def chunk_video_fast(input_path: str, output_dir: str, chunk_duration: int = 1800):
    """30-min chunks using segment muxer. Stream copy = near-instant."""
    pattern = f"{output_dir}/chunk_%03d.mp4"
    (
        ffmpeg
        .input(input_path)
        .output(
            pattern,
            format="segment",
            segment_time=chunk_duration,
            vcodec="copy",
            acodec="copy",
            reset_timestamps=1,      # CRITICAL: without this, players break
            segment_format="mp4",
            map="0",                  # preserve all streams
        )
        .overwrite_output()
        .run(capture_stderr=True)
    )
```

### Chunk with Overlap (Loop-Based)

```python
def chunk_video_with_overlap(
    input_path: str,
    output_dir: str,
    chunk_duration: int = 1800,  # 30 min
    overlap: int = 15,
):
    """Chunks with 15s overlap. Stream copy, keyframe-bound (acceptable)."""
    meta = probe_video(input_path)
    duration = meta["duration"]
    step = chunk_duration - overlap
    start = 0.0
    idx = 0

    while start < duration:
        length = min(chunk_duration, duration - start)
        out_path = f"{output_dir}/chunk_{idx:03d}.mp4"

        (
            ffmpeg
            .input(input_path, ss=start, t=length)
            .output(out_path, vcodec="copy", acodec="copy")
            .overwrite_output()
            .run(capture_stderr=True)
        )

        idx += 1
        start += step
```

### Chunk with Downscale (Re-encode)

```python
def chunk_video_downscale(
    input_path: str,
    output_dir: str,
    chunk_duration: int = 1800,
    overlap: int = 15,
    max_height: int = 720,
):
    """Chunks with optional downscale. Re-encodes (slower but precise)."""
    meta = probe_video(input_path)
    duration = meta["duration"]
    step = chunk_duration - overlap
    start = 0.0
    idx = 0

    while start < duration:
        length = min(chunk_duration, duration - start)
        out_path = f"{output_dir}/chunk_{idx:03d}.mp4"

        inp = ffmpeg.input(input_path, ss=start, t=length)
        video = inp.video.filter("scale", -2, max_height)  # -2 ensures divisible by 2
        audio = inp.audio

        (
            ffmpeg
            .output(
                video, audio, out_path,
                vcodec="libx264",
                acodec="aac",
                preset="fast",
                crf=23,
                pix_fmt="yuv420p",
                movflags="faststart",
            )
            .overwrite_output()
            .run(capture_stderr=True)
        )

        idx += 1
        start += step
```

### ffmpeg Gotchas

1. **`c="copy"` cuts on keyframes only** — segments are approximate, ±2-10s. Fine for our use case.
2. **`reset_timestamps=1` is essential** — without it, each chunk retains the original time offset
3. **Video filters (scale, etc.) DROP audio** — use `.video` and `.audio` selectors separately
4. **Scale filter: use `-2` not `-1`** for auto-width — H.264 requires dimensions divisible by 2
5. **`ss` on `input()` = fast seek** (before `-i`). `ss` on `output()` = slow frame-accurate seek. Use input-level for chunking.
6. **Catch `FileNotFoundError`** for missing ffmpeg and `ffmpeg.Error` for command failures
7. **`ffmpeg.Error.stderr`** is bytes — decode with `.decode("utf-8", errors="replace")`
8. **ffmpeg-python has no async API** — it wraps subprocess. Use `run_async()` for non-blocking.

---

## 9. Database Layer (aiosqlite)

**Package:** `aiosqlite` v0.22.x
**GitHub:** https://github.com/omnilib/aiosqlite

### Schema

```sql
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    duration_seconds REAL,
    uploader TEXT,
    metadata_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);

CREATE TABLE IF NOT EXISTS chunk_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL REFERENCES videos(id),
    chunk_index INTEGER NOT NULL,
    chunk_start_seconds REAL,
    chunk_end_seconds REAL,
    analysis_json TEXT NOT NULL,
    overall_sentiment TEXT,
    engagement_score INTEGER,
    token_count INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_video ON chunk_analyses(video_id);
CREATE INDEX IF NOT EXISTS idx_chunks_sentiment ON chunk_analyses(overall_sentiment);

CREATE TABLE IF NOT EXISTS video_insights (
    video_id TEXT PRIMARY KEY REFERENCES videos(id),
    insights_json TEXT NOT NULL,
    total_key_moments INTEGER,
    avg_engagement_score REAL,
    dominant_sentiment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Usage Patterns

```python
import aiosqlite
import json

DB_PATH = "gamesight.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.execute("PRAGMA journal_mode=WAL")  # better concurrent read performance
        await db.commit()

async def insert_video(video_id: str, url: str, metadata: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO videos (id, url, title, duration_seconds, uploader, metadata_json, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (video_id, url, metadata.get("title"), metadata.get("duration"),
             metadata.get("uploader"), json.dumps(metadata, separators=(",", ":")), "pending"),
        )
        await db.commit()

async def save_chunk_analysis(video_id: str, chunk_index: int, result, token_count: int, duration_ms: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO chunk_analyses
               (video_id, chunk_index, analysis_json, overall_sentiment, engagement_score, token_count, processing_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (video_id, chunk_index, result.model_dump_json(),
             result.overall_sentiment.value, result.engagement_score, token_count, duration_ms),
        )
        await db.commit()

async def get_video_analyses(video_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chunk_analyses WHERE video_id = ? ORDER BY chunk_index", (video_id,)
        ) as cursor:
            return [dict(row) async for row in cursor]

async def get_all_videos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM videos ORDER BY created_at DESC")
        return [dict(row) for row in rows]
```

**Key patterns:**
- One connection = one shared worker thread + request queue. Thread-safe for concurrent async access.
- `async with aiosqlite.connect(...) as db:` auto-closes connection
- Store JSON as TEXT; use `json.dumps(obj, separators=(",",":"))` for compact storage
- Denormalize frequently-filtered fields (sentiment, engagement_score) as separate columns
- `WAL` journal mode for better concurrent read performance

---

## 10. FastAPI Endpoints

### App Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="GameSight AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/videos` | Submit YouTube URL for analysis |
| `GET` | `/videos` | List all videos with status |
| `GET` | `/videos/{video_id}` | Video details + processing status |
| `GET` | `/analysis/{video_id}` | Full analysis results |
| `GET` | `/analysis/{video_id}/moments` | Key moments with timestamps |
| `GET` | `/analysis/{video_id}/sentiment` | Sentiment timeline |
| `GET` | `/insights` | Cross-video aggregated insights |
| `GET` | `/insights/frustration` | Top frustration points |
| `GET` | `/insights/features` | Feature praise/criticism rankings |
| `POST` | `/analyze-live` | Analyze YouTube URL directly (live demo) |

### File Upload Endpoint

```python
from fastapi import BackgroundTasks, UploadFile

@app.post("/videos")
async def submit_video(url: str, background_tasks: BackgroundTasks):
    # Save video record
    video_id = extract_video_id(url)
    await insert_video(video_id, url, {})

    # Start processing in background
    background_tasks.add_task(process_video_pipeline, video_id, url)

    return {"video_id": video_id, "status": "queued"}
```

---

## 11. Error Handling & Retries

```python
import asyncio
from google.genai import errors
from pydantic import ValidationError

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 45]

async def analyze_with_retry(client, video_file, prompt, schema):
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[video_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    system_instruction=SYSTEM_PROMPT,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )

            if response.parsed is not None:
                return response.parsed

            if response.text:
                return schema.model_validate_json(response.text)

            raise ValueError("Empty response")

        except errors.ServerError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])

        except errors.ClientError as e:
            if e.code == 429:
                last_error = e
                await asyncio.sleep(RETRY_BACKOFF[attempt] * 2)
            elif e.code == 400:
                raise  # Bad request — don't retry
            else:
                raise

        except (ValidationError, ValueError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {last_error}")
```

### Error Layers

| Layer | Error | Strategy |
|---|---|---|
| yt-dlp | `DownloadError` | Log, mark video `failed`, skip |
| ffmpeg | `ffmpeg.Error` / `FileNotFoundError` | Log, check ffmpeg installed |
| Gemini Upload | `ClientError(413)` | File >2GB — re-chunk smaller |
| Gemini Poll | `state.name == "FAILED"` | Log, try re-upload |
| Gemini Generate | `ServerError` (5xx) | Retry 3x with exponential backoff |
| Gemini Generate | `ClientError(429)` | Rate limited — backoff x2 |
| Gemini Generate | `ClientError(400)` | Bad request — don't retry |
| Parse | `response.parsed is None` | Fallback to `model_validate_json()` |
| Parse | `ValidationError` | Retry (model may produce valid on retry) |

---

## 12. Cost Optimization

### Token Economics Summary

| Metric | Value |
|---|---|
| Video (default res): 70 tok/frame @ 1 FPS | ~4,200 tokens/min |
| Audio: 32 tok/sec | ~1,920 tokens/min |
| **Combined** | **~6,120 tokens/min** |
| Input cost (paid) | $0.50 / 1M tokens |
| Output cost (incl. thinking) | $3.00 / 1M tokens |
| **Cost per minute of video** | **~$0.006/min (input+output)** |
| **100 videos x 10 min** | **~$6 total** |

### Optimization Tactics

1. **`thinking_level="low"` for bulk** — `"high"` (default) is 2-4x more thinking tokens
2. **Skip chunking for < 45 min videos** — saves ffmpeg overhead, preserves cross-segment context
3. **Context caching** for multi-query videos — 10x cheaper on cached input ($0.05 vs $0.50)
4. **YouTube direct for live demo** — no upload cost, zero latency
5. **Batch API (50% off)** — use for bulk pre-computation at $0.25/1M input
6. **Token counting before sending** — prevent surprise costs
7. **Pre-compute + SQLite cache** — analyze all demo videos ahead, serve from DB
8. **Delete uploaded files after analysis** — save 20GB project storage quota

---

## 13. Gotchas Checklist

### GenAI SDK
1. `response.parsed` is **silently None** on parse failure — no exception raised
2. `response.parsed` is **None during streaming** — only works with non-streaming
3. `response_mime_type="application/json"` is **mandatory** with `response_schema`
4. Use `response_schema=MyModel` (class), NOT `.model_json_schema()` for typed `parsed`
5. File state doesn't auto-update — must re-fetch with `client.files.get(name=...)`
6. `state` can be `None` initially — guard with `if video_file.state and ...`
7. State comparison: use `.name == "ACTIVE"` (string), not `== "ACTIVE"` directly
8. Video before prompt in `contents` list for better results
9. All params are keyword-only — cannot pass positional
10. `GOOGLE_API_KEY` wins over `GEMINI_API_KEY` — logs warning if both set
11. Files API is Gemini Developer API only — raises `ValueError` on Vertex AI
12. `count_tokens` on Developer API rejects `system_instruction`/`tools` in config

### Gemini 3 Flash
13. **Temperature: never set below 1.0** — causes looping/degraded output
14. **Never combine `thinking_level` and `thinking_budget`** — 400 error
15. Thought signatures must be passed back in multi-turn — SDKs handle automatically
16. YouTube URL: public videos only, 8hr/day free tier, no caching
17. Caching only works with uploaded files, NOT YouTube URLs
18. Video LOW = MEDIUM = 70 tok/frame — no difference until HIGH (280)
19. Global `MediaResolution` has no `ULTRA_HIGH` — only `PartMediaResolutionLevel` does
20. Per-part `media_resolution` requires `v1alpha` API version
21. 1 FPS default — sub-second events may be missed; use `fps=5` for fast action

### yt-dlp
22. `ignoreerrors` defaults to `False` for API (different from CLI)
23. `format: "best"` gives pre-merged low quality — use `bestvideo+bestaudio`
24. `outtmpl` MUST contain `%(id)s` for batch — else `SameFileError`
25. ffmpeg REQUIRED for merging separate streams
26. Logger: info messages go to `debug()` without `[debug] ` prefix

### ffmpeg-python
27. `c="copy"` cuts on keyframes only — ±2-10s imprecision (acceptable)
28. `reset_timestamps=1` is essential for segment muxer
29. Video filters DROP audio — use `.video`/`.audio` selectors separately
30. Scale filter: use `-2` not `-1` for auto-width (H.264 needs divisible by 2)

---

## 14. Risks & Mitigations

### Critical

| Risk | Impact | Mitigation |
|---|---|---|
| Gemini 3 Flash is preview | Rate limits, API changes, instability | Fallback to `gemini-2.5-flash`. Abstract model ID to config. |
| Silent parse failures | Lost analysis results | Always check `parsed is None`, manual `model_validate_json` fallback |
| 1 FPS misses fast events | Sub-second actions invisible | Accept for v1. Re-analyze flagged segments with `fps=5` |
| Rate limiting during demo | 429 errors during presentation | Pre-compute everything. Only 1-2 live URLs. |
| Hallucinated timestamps | Events at wrong times | Require "evidence" field. Validate timestamps vs duration. |
| Audio-less videos | No verbal feedback | Prompt includes "if no audio, analyze visual only" |

### Operational

| Risk | Mitigation |
|---|---|
| Files API 48h expiry | Upload, analyze, delete within pipeline |
| 20GB storage limit | Delete files immediately after analysis |
| SQLite write contention | WAL mode + single writer thread is fine for hackathon |
| ffmpeg not installed | Check at startup with `shutil.which("ffmpeg")` |

### Hackathon-Specific

| Risk | Mitigation |
|---|---|
| Network issues at venue | Pre-download all videos. Pre-compute all analyses. Run from SQLite. |
| API quota exhausted | Monitor usage. Backup API key. Free tier for YouTube direct (8h/day). |
| Demo timing | Live analysis of 10-min video takes ~30-60s. Start early, show results when ready. |
| Content safety filters | Gemini may block violent gameplay. Test demo videos ahead. |

---

## 15. Key Documentation Links

### Gemini API
- Gemini 3 Developer Guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Video Understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Structured Outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Files API: https://ai.google.dev/gemini-api/docs/files
- Audio Understanding: https://ai.google.dev/gemini-api/docs/audio
- Media Resolution: https://ai.google.dev/gemini-api/docs/media-resolution
- Context Caching: https://ai.google.dev/gemini-api/docs/caching
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Rate Limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Token Counting: https://ai.google.dev/gemini-api/docs/tokens
- Prompting Strategies: https://ai.google.dev/gemini-api/docs/prompting-strategies
- Migration Guide: https://ai.google.dev/gemini-api/docs/migrate

### Python SDK
- PyPI: https://pypi.org/project/google-genai/
- GitHub: https://github.com/googleapis/python-genai
- SDK Docs: https://googleapis.github.io/python-genai/

### Libraries
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- ffmpeg-python: https://github.com/kkroening/ffmpeg-python
- FastAPI: https://fastapi.tiangolo.com/
- Pydantic: https://docs.pydantic.dev/
- aiosqlite: https://github.com/omnilib/aiosqlite

### Gemini Cookbook (Examples)
- GitHub: https://github.com/google-gemini/cookbook
- Video quickstart notebook
- Audio quickstart notebook
- JSON/structured output notebook

### Local References (Downloaded)
- Repos: `.tmp/dependencies/repos/` (python-genai, yt-dlp, ffmpeg-python, gemini-cookbook, aiosqlite)
- Docs: `.tmp/dependencies/docs/` (40 HTML/MD/notebook files)
- Research: `.tmp/research/` (30 agent research reports across 6 topics)
