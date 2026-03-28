from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import AgentKind
from gamesight.schemas.executive import ExecutiveSummary
from gamesight.schemas.highlights import HighlightReel
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
    segment_label: str | None = None
    confidence_score: float = 0.5
    corroborating_agents: list[str] = Field(default_factory=list)
    sentiment_raw_score: int | None = None
    retry_total_attempts: int | None = None
    retry_quit_signal: bool | None = None
    retry_final_outcome: str | None = None
    verbal_is_actionable: bool | None = None
    verbal_quote: str | None = None


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


class DeduplicatedAnalyses(BaseModel):
    model_config = ConfigDict(extra="forbid")

    friction_moments: list[CanonicalMoment]
    clarity_moments: list[CanonicalMoment]
    delight_moments: list[CanonicalMoment]
    quality_issues: list[CanonicalMoment]
    sentiment_moments: list[CanonicalMoment] = Field(default_factory=list)
    retry_moments: list[CanonicalMoment] = Field(default_factory=list)
    verbal_moments: list[CanonicalMoment] = Field(default_factory=list)


class VideoReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    filename: str
    duration_seconds: float
    chunk_count: int
    game_title: str
    game_key: str
    session_arc: str
    friction_moments: list[CanonicalMoment]
    clarity_moments: list[CanonicalMoment]
    delight_moments: list[CanonicalMoment]
    quality_issues: list[CanonicalMoment]
    sentiment_moments: list[CanonicalMoment] = Field(default_factory=list)
    retry_moments: list[CanonicalMoment] = Field(default_factory=list)
    verbal_moments: list[CanonicalMoment] = Field(default_factory=list)
    top_stop_risk_drivers: list[str]
    top_praised_features: list[str]
    top_clarity_fixes: list[str]
    bug_count: int
    overall_friction: str
    overall_engagement: str
    overall_stop_risk: str
    recommendations: list[str]
    avg_sentiment: float | None = None
    sentiment_by_segment: dict[str, float] = Field(default_factory=dict)
    total_retry_sequences: int = 0
    first_attempt_failure_count: int = 0
    notable_quotes: list[str] = Field(default_factory=list)
    segments_encountered: list[str] = Field(default_factory=list)
    highlights: HighlightReel | None = None
    executive: ExecutiveSummary | None = None
    agent_coverage: list[ChunkAgentCoverage] = Field(default_factory=list)


class ProcessedVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video: VideoInfo
    timeline: VideoTimeline
    chunk_analyses: list[ChunkAnalysisBundle]
    report: VideoReport


__all__ = [
    "CanonicalMoment",
    "ChunkAgentCoverage",
    "DeduplicatedAnalyses",
    "ExecutiveSummary",
    "HighlightReel",
    "ProcessedVideo",
    "VideoReport",
]
