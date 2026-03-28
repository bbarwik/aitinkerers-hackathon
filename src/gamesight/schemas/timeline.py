from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import PhaseKind


class TimelineMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    visual_observation: str = Field(description="What is visible on screen")
    audio_observation: str = Field(description="What is heard. 'No player audio' if silent")
    player_expression: str | None = Field(description="Facecam: facial expression, posture. None if no facecam")
    event_description: str = Field(description="What happened in one sentence")
    phase_kind: PhaseKind = Field(description="The gameplay phase for this moment")
    significance: str = Field(description="routine, notable, or pivotal")
    segment_label: str = Field(
        description="Short reusable snake_case label for the game area or challenge, e.g. 'bridge_jump', 'boss_dragon', 'tutorial_movement'. Reuse the same label if the player returns to the same area."
    )


class CarryoverThread(BaseModel):
    model_config = ConfigDict()

    thread_name: str = Field(description="Short label for the ongoing issue")
    evidence: str = Field(description="What suggests this continues")
    current_status: str = Field(description="active, stalled, or resolved")


class TimelineChunkResult(BaseModel):
    model_config = ConfigDict()

    chunk_summary: str = Field(description="2-3 sentence factual summary")
    player_objective: str = Field(description="What the player is trying to accomplish")
    events: list[TimelineMoment] = Field(description="3-8 significant moments, chronological")
    emotional_trajectory: str = Field(description="How player emotion evolves in this segment")
    pacing_breakdown: str = Field(
        description="How the chunk's time is distributed across gameplay phases such as menus, exploration, combat, cutscenes, or loading"
    )
    carryover_threads: list[CarryoverThread] = Field(description="Unresolved threads for next segment")
    has_high_interest_moments: bool = Field(description="True if segment warrants detailed analysis")


__all__ = ["CarryoverThread", "TimelineChunkResult", "TimelineMoment"]
