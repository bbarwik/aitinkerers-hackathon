from gamesight.pipeline.dedup import deduplicate_moments
from gamesight.schemas.clarity import ClarityChunkAnalysis, ClarityMoment
from gamesight.schemas.delight import DelightChunkAnalysis, DelightMoment
from gamesight.schemas.enums import (
    BugSeverity,
    ClarityIssueType,
    ClaritySeverity,
    DelightDriver,
    DelightStrength,
    FrictionSeverity,
    FrictionSource,
    PhaseKind,
    StopRisk,
)
from gamesight.schemas.friction import FrictionChunkAnalysis, FrictionMoment
from gamesight.schemas.quality import QualityChunkAnalysis
from gamesight.schemas.video import ChunkAnalysisBundle, ChunkInfo, TimelineEvent, VideoTimeline


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
    timeline = VideoTimeline(
        video_id="video-1",
        game_title="Demo Game",
        session_arc="Boss retry loop",
        chunk_summaries=[],
        objectives=[],
        active_threads=[],
        events=[
            TimelineEvent(
                source_chunk_index=1,
                absolute_seconds=285.0,
                absolute_timestamp="4:45",
                relative_timestamp="0:45",
                visual_observation="Bridge boss checkpoint",
                audio_observation="Sigh",
                player_expression=None,
                event_description="Player retries the bridge boss",
                phase_kind=PhaseKind.BOSS,
                significance="pivotal",
                segment_label="bridge_boss",
            ),
            TimelineEvent(
                source_chunk_index=1,
                absolute_seconds=300.0,
                absolute_timestamp="5:00",
                relative_timestamp="1:00",
                visual_observation="Player looks for a grapple point",
                audio_observation="Where do I go?",
                player_expression=None,
                event_description="Navigation confusion in the boss arena",
                phase_kind=PhaseKind.BOSS,
                significance="notable",
                segment_label="bridge_boss",
            ),
            TimelineEvent(
                source_chunk_index=1,
                absolute_seconds=360.0,
                absolute_timestamp="6:00",
                relative_timestamp="2:00",
                visual_observation="Successful parry chain",
                audio_observation="Nice",
                player_expression=None,
                event_description="Combat clicks for the player",
                phase_kind=PhaseKind.COMBAT,
                significance="notable",
                segment_label="bridge_boss",
            ),
        ],
        thread_records=[],
        chunks=[],
    )
    analyses = [
        ChunkAnalysisBundle(
            chunk_index=0,
            friction=FrictionChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[
                    FrictionMoment(
                        relative_timestamp="4:45",
                        scene_description="Bridge boss checkpoint",
                        visual_signals=["Repeated deaths"],
                        audio_signals=["Sigh"],
                        verbal_feedback=[],
                        player_expression=None,
                        game_context="Bridge boss",
                        root_cause="Repeated punishment without learning",
                        progress_impact="The player stalled",
                        attempts_observed=3,
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
                overall_quality=BugSeverity.COSMETIC,
            ),
        ),
        ChunkAnalysisBundle(
            chunk_index=1,
            friction=FrictionChunkAnalysis(
                chunk_activity="Boss retry loop",
                moments=[
                    FrictionMoment(
                        relative_timestamp="0:45",
                        scene_description="Bridge boss checkpoint",
                        visual_signals=["Repeated deaths"],
                        audio_signals=["Sigh"],
                        verbal_feedback=[],
                        player_expression=None,
                        game_context="Bridge boss",
                        root_cause="Repeated punishment without learning",
                        progress_impact="The player stalled",
                        attempts_observed=3,
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
                        scene_description="Boss arena grapple route",
                        visual_signals=["Map reopened"],
                        audio_signals=["Where do I go?"],
                        verbal_feedback=["Where do I go?"],
                        player_expression=None,
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
                        scene_description="Bridge boss arena",
                        visual_signals=["Fast inputs"],
                        audio_signals=["Nice"],
                        verbal_feedback=["Nice"],
                        player_expression=None,
                        game_context="Successful parry chain",
                        why_it_works="The timing feedback feels crisp",
                        amplification_opportunity="Add more enemy patterns using this system",
                        replay_potential="High because the player immediately re-engaged",
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
                overall_quality=BugSeverity.COSMETIC,
            ),
        ),
    ]

    deduplicated = deduplicate_moments(chunks, analyses, timeline)

    assert len(deduplicated.friction_moments) == 1
    assert deduplicated.friction_moments[0].absolute_timestamp == "4:45"
    assert deduplicated.friction_moments[0].segment_label == "bridge_boss"
    assert len(deduplicated.clarity_moments) == 1
    assert len(deduplicated.delight_moments) == 1
