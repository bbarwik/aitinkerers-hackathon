from pydantic import BaseModel, ConfigDict


class HighlightMoment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int
    absolute_timestamp: str
    absolute_seconds: float
    clip_start_seconds: float
    clip_end_seconds: float
    category: str
    headline: str
    why_important: str
    evidence: list[str]
    importance_score: float
    corroborating_agents: list[str]


class HighlightReel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    total_moments_analyzed: int
    highlights: list[HighlightMoment]
    one_line_verdict: str


__all__ = ["HighlightMoment", "HighlightReel"]
