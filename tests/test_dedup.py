from gamesight.pipeline.dedup import deduplicate_moments
from gamesight.schemas.clarity import ClarityChunkAnalysis, ClarityMoment
from gamesight.schemas.delight import DelightChunkAnalysis, DelightMoment
from gamesight.schemas.enums import (
    ClarityIssueType,
    ClaritySeverity,
    DelightDriver,
    DelightStrength,
    FrictionSeverity,
    FrictionSource,
    StopRisk,
)
from gamesight.schemas.friction import FrictionChunkAnalysis, FrictionMoment
from gamesight.schemas.quality import QualityChunkAnalysis
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo


def test_deduplicate_moments_respects_ownership() -> None:
    chunks = [
        ChunkInfo(
            index=0,
            start_seconds=0.0,
            end_seconds=300.0,
            youtube_url="https://www.youtube.com/watch?v=demo",
            owns_from=0.0,
            owns_until=270.0,
        ),
        ChunkInfo(
            index=1,
            start_seconds=240.0,
            end_seconds=540.0,
            youtube_url="https://www.youtube.com/watch?v=demo",
            owns_from=270.0,
            owns_until=540.0,
        ),
    ]
    analyses = [
        ChunkAnalysisBundle(
            chunk_index=0,
            friction=FrictionChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[
                    FrictionMoment(
                        relative_timestamp="4:45",
                        visual_signals=["Repeated deaths"],
                        audio_signals=["Sigh"],
                        player_expression=None,
                        player_quote=None,
                        game_context="Bridge boss",
                        root_cause="Repeated punishment without learning",
                        progress_impact="The player stalled",
                        source=FrictionSource.DIFFICULTY_SPIKE,
                        severity=FrictionSeverity.MAJOR,
                        stop_risk=StopRisk.HIGH,
                    )
                ],
                recurring_pattern="None detected",
                dominant_blocker="Bridge boss",
                overall_severity=FrictionSeverity.MAJOR,
                overall_stop_risk=StopRisk.HIGH,
            ),
            clarity=ClarityChunkAnalysis(
                chunk_learning_context="Boss tutorialization",
                moments=[],
                understood_elements=["Combat basics"],
                recurring_confusion="None detected",
                highest_priority_fix=None,
                overall_clarity=ClaritySeverity.MINOR,
            ),
            delight=DelightChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[],
                praised_features=[],
                standout_element=None,
                overall_engagement=DelightStrength.LIGHT,
            ),
            quality=QualityChunkAnalysis(
                chunk_activity="Boss retry loop",
                issues=[],
                performance_note="Stable",
                worst_issue=None,
                overall_quality="cosmetic",
            ),
        ),
        ChunkAnalysisBundle(
            chunk_index=1,
            friction=FrictionChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[
                    FrictionMoment(
                        relative_timestamp="0:45",
                        visual_signals=["Repeated deaths"],
                        audio_signals=["Sigh"],
                        player_expression=None,
                        player_quote=None,
                        game_context="Bridge boss",
                        root_cause="Repeated punishment without learning",
                        progress_impact="The player stalled",
                        source=FrictionSource.DIFFICULTY_SPIKE,
                        severity=FrictionSeverity.MAJOR,
                        stop_risk=StopRisk.HIGH,
                    )
                ],
                recurring_pattern="None detected",
                dominant_blocker="Bridge boss",
                overall_severity=FrictionSeverity.MAJOR,
                overall_stop_risk=StopRisk.HIGH,
            ),
            clarity=ClarityChunkAnalysis(
                chunk_learning_context="Boss tutorialization",
                moments=[
                    ClarityMoment(
                        relative_timestamp="1:00",
                        visual_signals=["Map reopened"],
                        audio_signals=["Where do I go?"],
                        player_expression=None,
                        player_quote="Where do I go?",
                        intended_behavior="Use the grapple point",
                        actual_behavior="Backtracked",
                        missing_cue="The grapple affordance is too weak",
                        issue_type=ClarityIssueType.MISSING_SIGNPOST,
                        severity=ClaritySeverity.MAJOR,
                        resolved="unresolved",
                    )
                ],
                understood_elements=["Combat basics"],
                recurring_confusion="Navigation confusion",
                highest_priority_fix="Make the grapple point read clearly.",
                overall_clarity=ClaritySeverity.MAJOR,
            ),
            delight=DelightChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[
                    DelightMoment(
                        relative_timestamp="2:00",
                        visual_signals=["Fast inputs"],
                        audio_signals=["Nice"],
                        player_expression=None,
                        player_quote="Nice",
                        game_context="Successful parry chain",
                        why_it_works="The timing feedback feels crisp",
                        amplification_opportunity="Add more enemy patterns using this system",
                        driver=DelightDriver.COMBAT,
                        strength=DelightStrength.STRONG,
                    )
                ],
                praised_features=["Parry combat"],
                standout_element="Parry combat",
                overall_engagement=DelightStrength.STRONG,
            ),
            quality=QualityChunkAnalysis(
                chunk_activity="Boss retry loop",
                issues=[],
                performance_note="Stable",
                worst_issue=None,
                overall_quality="cosmetic",
            ),
        ),
    ]

    deduplicated = deduplicate_moments(chunks, analyses)

    assert len(deduplicated.friction_moments) == 1
    assert deduplicated.friction_moments[0].absolute_timestamp == "4:45"
    assert len(deduplicated.clarity_moments) == 1
    assert len(deduplicated.delight_moments) == 1
