from pydantic import BaseModel, ConfigDict, Field


class KeyFinding(BaseModel):
    model_config = ConfigDict()

    evidence_summary: str = Field(
        description="Specific timestamps, player quotes, and statistics that support this finding"
    )
    affected_timestamps: list[str] = Field(description="Absolute timestamps (MM:SS) where this finding manifests")
    finding: str = Field(description="The insight in one sentence")
    recommended_action: str = Field(description="What the development team should do about this")
    severity: str = Field(description="critical, important, or notable")


class ExecutiveSummary(BaseModel):
    model_config = ConfigDict()

    executive_summary: str = Field(
        description="Three short paragraphs: session overview, critical issues, strengths to protect"
    )
    key_findings: list[KeyFinding] = Field(description="3-5 prioritized findings, most impactful first")
    priority_actions: list[str] = Field(description="Ranked list of development actions, most urgent first")
    cross_dimensional_insight: str = Field(
        description="One non-obvious pattern that connects findings across multiple analysis dimensions"
    )
    session_health_score: int = Field(description="Overall session health from 0 (unplayable) to 100 (flawless)")


__all__ = ["ExecutiveSummary", "KeyFinding"]
