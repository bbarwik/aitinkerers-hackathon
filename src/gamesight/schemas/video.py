from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from gamesight.schemas.clarity import ClarityChunkAnalysis
from gamesight.schemas.delight import DelightChunkAnalysis
from gamesight.schemas.enums import PhaseKind, VideoSourceType
from gamesight.schemas.friction import FrictionChunkAnalysis
from gamesight.schemas.quality import QualityChunkAnalysis
from gamesight.schemas.timeline import CarryoverThread, TimelineChunkResult


class ChunkInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    start_seconds: float
    end_seconds: float
    file_path: str | None = None
    youtube_url: str | None = None
    owns_from: float
    owns_until: float

    @model_validator(mode="after")
    def validate_source(self) -> "ChunkInfo":
        if bool(self.file_path) == bool(self.youtube_url):
            raise ValueError("ChunkInfo requires exactly one of file_path or youtube_url.")
        return self

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @property
    def is_youtube(self) -> bool:
        return self.youtube_url is not None


class VideoInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: str
    source_type: VideoSourceType
    source: str
    filename: str
    title: str
    duration_seconds: float

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_chunk_index: int
    absolute_seconds: float
    absolute_timestamp: str
    relative_timestamp: str
    visual_observation: str
    audio_observation: str
    player_expression: str | None
    event_description: str
    phase_kind: PhaseKind
    significance: str


class TimelineThreadRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_chunk_index: int
    thread_name: str
    evidence: str
    current_status: str


class TimelineChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int
    start_seconds: float
    end_seconds: float
    result: TimelineChunkResult


class VideoTimeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    game_title: str
    session_arc: str
    chunk_summaries: list[str]
    objectives: list[str]
    active_threads: list[str]
    events: list[TimelineEvent]
    thread_records: list[TimelineThreadRecord]
    chunks: list[TimelineChunkRecord]


class ChunkAnalysisBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int
    friction: FrictionChunkAnalysis
    clarity: ClarityChunkAnalysis
    delight: DelightChunkAnalysis
    quality: QualityChunkAnalysis


class ChunkAnalysisRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk: ChunkInfo
    timeline: TimelineChunkResult | None = None
    friction: FrictionChunkAnalysis | None = None
    clarity: ClarityChunkAnalysis | None = None
    delight: DelightChunkAnalysis | None = None
    quality: QualityChunkAnalysis | None = None


class CarryoverThreadRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_index: int
    thread: CarryoverThread


__all__ = [
    "CarryoverThreadRecord",
    "ChunkAnalysisBundle",
    "ChunkAnalysisRecord",
    "ChunkInfo",
    "TimelineChunkRecord",
    "TimelineEvent",
    "TimelineThreadRecord",
    "VideoInfo",
    "VideoTimeline",
]
