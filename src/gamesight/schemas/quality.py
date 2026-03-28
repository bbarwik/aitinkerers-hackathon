from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import BugCategory, BugSeverity


class QualityIssue(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    visual_symptoms: list[str] = Field(description="Clipping, T-pose, pop-in, frame drop")
    audio_symptoms: list[str] = Field(description="Missing SFX, desync. 'None' if fine")
    player_reaction: str = Field(description="Noticed and commented, ignored, or not noticed")
    reproduction_context: str = Field(description="What was happening: area, action, game state")
    gameplay_impact: str = Field(description="cosmetic_only, disrupted_flow, or blocked_progress")
    category: BugCategory = Field(description="The technical quality category")
    severity: BugSeverity = Field(description="How severe the issue is")
    evidence_certainty: str = Field(description="clear, likely, or ambiguous")


class QualityChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What gameplay section this covers")
    issues: list[QualityIssue] = Field(description="0-5 technical issues. Empty list if clean.")
    performance_note: str = Field(description="Frame rate stability. 'Stable' if no concerns")
    worst_issue: str | None = Field(description="Most severe issue, or None")
    overall_quality: BugSeverity = Field(description="Overall technical quality severity for the chunk")


__all__ = ["QualityChunkAnalysis", "QualityIssue"]
