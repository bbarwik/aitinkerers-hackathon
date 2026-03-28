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
