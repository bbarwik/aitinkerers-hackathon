from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import VerbalCategory


class VerbalMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    quote: str = Field(description="Exact words spoken by the player, as close to verbatim as possible")
    voice_tone: str = Field(description="angry, frustrated, confused, neutral, amused, excited, sarcastic, or resigned")
    game_context: str = Field(description="What was happening on screen when this was said")
    actionable_insight: str | None = Field(description="The design implication if actionable, else None")
    category: VerbalCategory
    sentiment_score: int = Field(description="-5 (very negative) to +5 (very positive)")
    is_actionable: bool = Field(description="True if this quote implies a specific design change the studio could make")


class VerbalChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    has_player_audio: bool = Field(description="Whether player speech was detected in this chunk")
    moments: list[VerbalMoment] = Field(
        description="All notable verbal feedback, chronological. Empty if no speech detected."
    )
    total_speech_segments: int = Field(description="Approximate count of distinct speech segments")
    talk_ratio: str = Field(
        description="What portion of the chunk has player speech: silent, occasional, frequent, or constant"
    )
    dominant_tone: str = Field(description="Overall tone of verbal feedback in this chunk")
    most_actionable_quote: str | None = Field(
        description="The single most design-relevant thing the player said, or None"
    )


__all__ = ["VerbalChunkAnalysis", "VerbalMoment"]
