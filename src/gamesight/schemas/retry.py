from pydantic import BaseModel, ConfigDict, Field

from gamesight.schemas.enums import RetryOutcome


class ChallengeAttempt(BaseModel):
    model_config = ConfigDict()

    attempt_number: int = Field(description="Sequential attempt number starting from 1")
    relative_timestamp: str = Field(description="MM:SS from chunk start when this attempt begins")
    duration_seconds: int = Field(description="Approximate seconds spent on this attempt")
    outcome: str = Field(description="'died', 'failed', 'succeeded', or 'abandoned'")
    player_reaction: str = Field(description="Observable player reaction after this attempt")
    strategy_change: str = Field(
        description="How the player changed approach from previous attempt, or 'same_strategy'"
    )


class RetrySequence(BaseModel):
    model_config = ConfigDict()

    challenge_name: str = Field(
        description="Short snake_case name matching segment_label from timeline, e.g. 'bridge_jump', 'boss_phase_2'"
    )
    challenge_location: str = Field(description="Where in the game this challenge occurs")
    first_attempt_timestamp: str = Field(description="MM:SS of the first attempt in this chunk")
    total_attempts: int = Field(description="Total number of attempts observed in this chunk")
    attempts: list[ChallengeAttempt] = Field(description="Each individual attempt, chronological")
    final_outcome: RetryOutcome
    total_time_seconds: int = Field(description="Total seconds spent across all attempts")
    frustration_escalation: str = Field(
        description="How frustration changed: escalating, stable, de-escalating, or mixed"
    )
    quit_signal: bool = Field(description="True if the player showed signs of wanting to stop playing entirely")


class RetryChunkAnalysis(BaseModel):
    model_config = ConfigDict()

    chunk_activity: str = Field(description="What gameplay section this covers")
    retry_sequences: list[RetrySequence] = Field(description="0-3 retry sequences detected in this chunk")
    total_deaths_or_failures: int = Field(description="Total death/failure count including non-retry single failures")
    first_attempt_successes: int = Field(description="Number of challenges cleared on the first try")
    progression_rate: str = Field(
        description="How efficiently the player progresses: smooth, moderate_friction, or heavily_blocked"
    )


__all__ = ["ChallengeAttempt", "RetryChunkAnalysis", "RetrySequence"]
