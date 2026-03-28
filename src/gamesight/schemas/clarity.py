from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import ClarityIssueType, ClaritySeverity


class ClarityMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    visual_signals: list[str] = Field(description="Wandering, map reopening, wrong interactions")
    audio_signals: list[str] = Field(description="Questions, uncertain tone, reading UI aloud")
    player_expression: str | None = Field(
        description="Facecam: confused look, squinting, shrugging. None if no facecam"
    )
    player_quote: str | None = Field(description="Direct quote if audible")
    intended_behavior: str = Field(description="What the game wanted the player to do")
    actual_behavior: str = Field(description="What the player did instead")
    missing_cue: str = Field(description="What communication was missing or misleading")
    issue_type: ClarityIssueType = Field(description="The kind of clarity issue observed")
    severity: ClaritySeverity = Field(description="How severe the clarity issue is")
    resolved: str = Field(description="self_resolved, game_cue_resolved, or unresolved")


class ClarityChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_learning_context: str = Field(description="What player should understand here")
    moments: list[ClarityMoment] = Field(description="0-5 confusion incidents")
    understood_elements: list[str] = Field(description="Game elements the player clearly grasped")
    recurring_confusion: str = Field(description="Repeated confusion, or 'None detected'")
    highest_priority_fix: str | None = Field(description="Most impactful clarity improvement")
    overall_clarity: ClaritySeverity = Field(description="Overall clarity assessment for the chunk")


__all__ = ["ClarityChunkAnalysis", "ClarityMoment"]
