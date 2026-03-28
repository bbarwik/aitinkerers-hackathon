from pydantic import BaseModel, ConfigDict

from gamesight.schemas.enums import AgentKind
from gamesight.schemas.video import ChunkAnalysisBundle, VideoInfo, VideoTimeline


class CanonicalMoment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_kind: AgentKind
    source_label: str
    absolute_seconds: float
    absolute_timestamp: str
    summary: str
    game_context: str
    evidence: list[str]
    severity_numeric: int
    source_chunk_index: int


class DeduplicatedAnalyses(BaseModel):
    model_config = ConfigDict(extra="forbid")

    friction_moments: list[CanonicalMoment]
    clarity_moments: list[CanonicalMoment]
    delight_moments: list[CanonicalMoment]
    quality_issues: list[CanonicalMoment]


class VideoReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    filename: str
    duration_seconds: float
    chunk_count: int
    game_title: str
    session_arc: str
    friction_moments: list[CanonicalMoment]
    clarity_moments: list[CanonicalMoment]
    delight_moments: list[CanonicalMoment]
    quality_issues: list[CanonicalMoment]
    top_stop_risk_drivers: list[str]
    top_praised_features: list[str]
    top_clarity_fixes: list[str]
    bug_count: int
    overall_friction: str
    overall_engagement: str
    overall_stop_risk: str
    recommendations: list[str]


class ProcessedVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video: VideoInfo
    timeline: VideoTimeline
    chunk_analyses: list[ChunkAnalysisBundle]
    report: VideoReport


__all__ = ["CanonicalMoment", "DeduplicatedAnalyses", "ProcessedVideo", "VideoReport"]
