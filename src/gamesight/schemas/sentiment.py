from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import EmotionLabel, SilenceType


class SentimentMoment(BaseModel):
    model_config = ConfigDict()

    relative_timestamp: str = Field(description="MM:SS from chunk start")
    trigger: str = Field(description="What caused this emotional state or shift")
    visual_basis: str = Field(
        description="Gameplay state informing this rating: success, failure, exploration, stalling"
    )
    audio_basis: str = Field(description="Player voice tone, words, volume, breathing. 'Silent' if no player audio")
    facecam_basis: str | None = Field(description="Facial expression and posture. None if no facecam visible")
    silence_type: SilenceType | None = Field(
        description="If player is silent, classify the silence type. None if player is speaking"
    )
    confidence: str = Field(description="high, medium, or low based on evidence clarity")
    dominant_emotion: EmotionLabel
    sentiment_score: int = Field(description="Player sentiment from -10 (rage-quit) to +10 (peak delight)")


class SentimentChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What gameplay section this covers")
    moments: list[SentimentMoment] = Field(
        description="5-15 sentiment samples, roughly every 20-30 seconds through the chunk"
    )
    sentiment_curve: str = Field(description="Narrative: how player emotion evolves across this segment")
    lowest_point: str = Field(description="Timestamp and cause of the emotional low point")
    highest_point: str = Field(description="Timestamp and cause of the emotional high point")
    recovery_after_setback: str = Field(
        description="How quickly and fully the player recovers emotionally after negative events. 'No setbacks observed' if none"
    )
    dominant_emotion: EmotionLabel
    average_sentiment: float = Field(description="Mean sentiment score for this chunk")


__all__ = ["SentimentChunkAnalysis", "SentimentMoment"]
