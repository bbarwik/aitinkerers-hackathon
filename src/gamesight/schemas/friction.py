from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import FrictionSeverity, FrictionSource, StopRisk


class FrictionMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    visual_signals: list[str] = Field(description="Observable behavior: deaths, pausing, menu spam")
    audio_signals: list[str] = Field(description="Sighs, cursing, raised voice, defeated silence")
    player_expression: str | None = Field(
        description="Facecam: facial expression, posture, gestures. None if no facecam visible"
    )
    player_quote: str | None = Field(description="Direct quote if audible, else None")
    game_context: str = Field(description="What in-game element caused this")
    root_cause: str = Field(description="Why the player is frustrated")
    progress_impact: str = Field(description="How this affected momentum")
    source: FrictionSource = Field(description="The main source of frustration")
    severity: FrictionSeverity = Field(description="How severe this friction moment is")
    stop_risk: StopRisk = Field(description="Likelihood this moment makes the player stop")


class FrictionChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What the player was doing")
    moments: list[FrictionMoment] = Field(description="0-5 frustration incidents")
    recurring_pattern: str = Field(description="Repeated pattern, or 'None detected'")
    dominant_blocker: str | None = Field(description="Main frustration source, or None")
    overall_severity: FrictionSeverity = Field(description="Overall friction severity in the chunk")
    overall_stop_risk: StopRisk = Field(description="Overall stop-playing risk for the chunk")


__all__ = ["FrictionChunkAnalysis", "FrictionMoment"]
