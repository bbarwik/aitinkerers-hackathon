from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import DelightDriver, DelightStrength


class DelightMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    visual_signals: list[str] = Field(description="Rapid inputs, voluntary exploration, replaying")
    audio_signals: list[str] = Field(description="Laughter, exclamations, praise, focused silence")
    player_expression: str | None = Field(
        description="Facecam: smiling, leaning forward, fist pump, wide eyes. None if no facecam"
    )
    player_quote: str | None = Field(description="Direct positive quote if audible")
    game_context: str = Field(description="What triggered the positive response")
    why_it_works: str = Field(description="Why this moment landed for the player")
    amplification_opportunity: str = Field(description="How the studio could expand this")
    driver: DelightDriver = Field(description="The main driver behind the positive response")
    strength: DelightStrength = Field(description="How strong the delight signal is")


class DelightChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What the player was doing")
    moments: list[DelightMoment] = Field(description="0-5 positive engagement moments")
    praised_features: list[str] = Field(description="Features the player enjoyed")
    standout_element: str | None = Field(description="Most engaging element, or None")
    overall_engagement: DelightStrength = Field(description="Overall engagement strength for the chunk")


__all__ = ["DelightChunkAnalysis", "DelightMoment"]
