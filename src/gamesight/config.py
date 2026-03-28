from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
import re as _re
from shutil import which
from typing import Final

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME: Final[str] = "GameSight AI"
DEFAULT_MODEL_ID: Final[str] = "gemini-3-flash-preview"
DEFAULT_GAME_GENRE: Final[str] = "unknown"
CHUNK_DURATION_SECONDS: Final[int] = 300
CHUNK_OVERLAP_SECONDS: Final[int] = 60
CHUNK_STEP_SECONDS: Final[int] = CHUNK_DURATION_SECONDS - CHUNK_OVERLAP_SECONDS
TIMELINE_FPS: Final[int] = 1
SPECIALIST_FPS: Final[int] = 5
UPLOAD_CONCURRENCY: Final[int] = 3
CHUNK_CONCURRENCY: Final[int] = 2
MIN_CACHEABLE_CHUNK_SECONDS: Final[int] = 60
CACHE_TTL_SECONDS: Final[int] = 600
DEFAULT_MAX_DURATION_SECONDS: Final[float] = 3600.0
LLM_RETRY_DELAYS_SECONDS: Final[tuple[int, ...]] = (10, 30, 60, 90, 120)
FRICTION_SEVERITY_MAP: Final[dict[str, int]] = {"minor": 2, "moderate": 5, "major": 7, "severe": 9}
CLARITY_SEVERITY_MAP: Final[dict[str, int]] = {"minor": 3, "major": 6, "critical": 9}
BUG_SEVERITY_MAP: Final[dict[str, int]] = {"cosmetic": 2, "play_affecting": 6, "blocking": 9}
DELIGHT_STRENGTH_MAP: Final[dict[str, int]] = {"light": 3, "clear": 5, "strong": 7, "signature": 9}
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    database_path: Path = Field(default=Path("gamesight.db"), validation_alias="DATABASE_PATH")
    data_dir: Path = Field(default=Path("data"), validation_alias="DATA_DIR")
    model_id: str = DEFAULT_MODEL_ID
    upload_concurrency: int = UPLOAD_CONCURRENCY
    chunk_concurrency: int = CHUNK_CONCURRENCY
    llm_retry_delays_seconds: tuple[int, ...] = LLM_RETRY_DELAYS_SECONDS
    debug_llm: bool = Field(default=False, validation_alias="DEBUG_LLM")
    max_duration_seconds: float = Field(default=DEFAULT_MAX_DURATION_SECONDS, validation_alias="MAX_DURATION_SECONDS")
    youtube_cookies_path: str | None = Field(default=None, validation_alias="YOUTUBE_COOKIES_PATH")

    @property
    def chunks_dir(self) -> Path:
        return self.data_dir / "chunks"

    @property
    def videos_dir(self) -> Path:
        return self.data_dir / "videos"


class AnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    game_title: str | None = None
    game_genre: str = DEFAULT_GAME_GENRE
    duration_seconds: float | None = None
    upload_concurrency: int = UPLOAD_CONCURRENCY
    chunk_concurrency: int = CHUNK_CONCURRENCY
    keep_chunk_files: bool = False
    use_caching: bool = True
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS

    def resolved_game_title(self, fallback: str) -> str:
        return self.game_title.strip() if self.game_title and self.game_title.strip() else fallback


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def ensure_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.chunks_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)


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


def parse_mmss(timestamp: str) -> float:
    try:
        parts = timestamp.strip().split(":")
        if len(parts) == 3:
            hour_part, minute_part, second_part = parts
            return int(hour_part) * 3600 + int(minute_part) * 60 + float(second_part)
        if len(parts) == 2:
            minute_part, second_part = parts
            return int(minute_part) * 60 + float(second_part)
    except (AttributeError, TypeError, ValueError):
        return 0.0
    return 0.0


def to_mmss(seconds: float) -> str:
    minutes, remainder = divmod(int(max(seconds, 0)), 60)
    return f"{minutes}:{remainder:02d}"


def relative_to_absolute(relative_timestamp: str, chunk_start_seconds: float) -> tuple[float, str]:
    absolute_seconds = chunk_start_seconds + parse_mmss(relative_timestamp)
    return absolute_seconds, to_mmss(absolute_seconds)


def validate_relative_timestamp(
    relative_timestamp: str,
    chunk_start_seconds: float,
    chunk_duration_seconds: float,
) -> str:
    stripped_timestamp = relative_timestamp.strip()
    parts = stripped_timestamp.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(
            f"Invalid timestamp {relative_timestamp!r}. Expected MM:SS or HH:MM:SS relative to the current chunk."
        )
    if any(not part for part in parts):
        raise ValueError(f"Invalid timestamp {relative_timestamp!r}. Timestamp parts cannot be empty.")

    parsed_seconds = parse_mmss(stripped_timestamp)
    if parsed_seconds < 0:
        raise ValueError(f"Invalid timestamp {relative_timestamp!r}. Relative timestamps must be non-negative.")

    if parsed_seconds <= chunk_duration_seconds:
        return to_mmss(parsed_seconds)

    chunk_end_seconds = chunk_start_seconds + chunk_duration_seconds
    if chunk_start_seconds <= parsed_seconds <= chunk_end_seconds:
        return to_mmss(parsed_seconds - chunk_start_seconds)

    raise ValueError(
        f"Timestamp {relative_timestamp!r} is outside chunk bounds. "
        f"Expected a chunk-relative timestamp between 00:00 and {to_mmss(chunk_duration_seconds)}, "
        f"or an absolute timestamp between {to_mmss(chunk_start_seconds)} and {to_mmss(chunk_end_seconds)}."
    )


def format_list(items: Sequence[str]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- {item}" for item in items)


def ffmpeg_available() -> bool:
    return which("ffmpeg") is not None and which("ffprobe") is not None


__all__ = [
    "APP_NAME",
    "AnalysisConfig",
    "BUG_SEVERITY_MAP",
    "CACHE_TTL_SECONDS",
    "CHUNK_CONCURRENCY",
    "CHUNK_DURATION_SECONDS",
    "CHUNK_OVERLAP_SECONDS",
    "CHUNK_STEP_SECONDS",
    "CLARITY_SEVERITY_MAP",
    "HEALTH_SCORE_MAX",
    "HEALTH_SCORE_MIN",
    "DEFAULT_GAME_GENRE",
    "DEFAULT_MAX_DURATION_SECONDS",
    "DEFAULT_MODEL_ID",
    "DELIGHT_STRENGTH_MAP",
    "FRICTION_SEVERITY_MAP",
    "LLM_RETRY_DELAYS_SECONDS",
    "MAX_SEVERITY_NUMERIC",
    "MIN_CACHEABLE_CHUNK_SECONDS",
    "RETRY_ATTEMPT_SEVERITY_WEIGHT",
    "RETRY_QUIT_SIGNAL_SEVERITY_BONUS",
    "SENTIMENT_SCORE_MAX",
    "SENTIMENT_SCORE_MIN",
    "SPECIALIST_FPS",
    "Settings",
    "TIMELINE_FPS",
    "UPLOAD_CONCURRENCY",
    "VERBAL_SENTIMENT_MAX",
    "VERBAL_SENTIMENT_MIN",
    "VERBAL_SEVERITY_WEIGHT",
    "clamp",
    "ensure_directories",
    "ffmpeg_available",
    "format_list",
    "get_settings",
    "normalize_game_key",
    "normalize_segment_label",
    "parse_mmss",
    "relative_to_absolute",
    "to_mmss",
    "validate_relative_timestamp",
]
