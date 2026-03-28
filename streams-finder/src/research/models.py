from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Platform(StrEnum):
    YOUTUBE = "youtube"
    TWITCH = "twitch"


class DiscoveredVideo(BaseModel):
    platform: Platform
    video_id: str = Field(description="Platform-native video ID")
    url: str = Field(description="Canonical watch URL")
    title: str
    channel_name: str | None = None
    description: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    published_at: datetime | None = None  # Always UTC-aware
    thumbnail_url: str | None = None
    source_query: str | None = None


class DiscoveryResult(BaseModel):
    game_name: str
    game_context: str = Field(default="", description="Rich game description from Gemini grounding")
    queries: list[str] = Field(default_factory=list, description="Gemini-generated search queries")
    total_found: int = 0
    popular: list[DiscoveredVideo] = Field(default_factory=list, description="Top 10 by views")
    recent: list[DiscoveredVideo] = Field(default_factory=list, description="Top 10 by date")
    source_breakdown: dict[str, int] = Field(default_factory=dict)
    partial: bool = False
    warnings: list[str] = Field(default_factory=list)
    cached: bool = False
    generated_at: datetime = Field(default_factory=datetime.now)


class ResearchDiscoverRequest(BaseModel):
    game_name: str = Field(min_length=1, max_length=100)
    refresh: bool = False
