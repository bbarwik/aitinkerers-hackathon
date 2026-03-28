from gamesight.schemas.enums import FrictionSeverity, FrictionSource, StopRisk, VideoSourceType
from gamesight.schemas.friction import FrictionChunkAnalysis, FrictionMoment
from gamesight.schemas.report import VideoReport
from gamesight.schemas.video import ChunkInfo, VideoInfo


def test_schema_instantiation() -> None:
    chunk = ChunkInfo(
        index=0,
        start_seconds=0.0,
        end_seconds=300.0,
        file_path="/tmp/chunk_000.mp4",
        owns_from=0.0,
        owns_until=270.0,
    )
    video = VideoInfo(
        video_id="video-1",
        source_type=VideoSourceType.LOCAL,
        source="/tmp/video.mp4",
        filename="video.mp4",
        title="video",
        duration_seconds=600.0,
    )
    analysis = FrictionChunkAnalysis(
        chunk_activity="Combat loop",
        moments=[
            FrictionMoment(
                relative_timestamp="0:10",
                visual_signals=["Missed jump"],
                audio_signals=["Sigh"],
                player_expression=None,
                player_quote=None,
                game_context="Tutorial gap",
                root_cause="The jump timing is unclear",
                progress_impact="The player paused",
                source=FrictionSource.UNCLEAR_OBJECTIVE,
                severity=FrictionSeverity.MODERATE,
                stop_risk=StopRisk.LOW,
            )
        ],
        recurring_pattern="None detected",
        dominant_blocker="Tutorial gap",
        overall_severity=FrictionSeverity.MODERATE,
        overall_stop_risk=StopRisk.LOW,
    )
    report = VideoReport(
        video_id=video.video_id,
        filename=video.filename,
        duration_seconds=video.duration_seconds,
        chunk_count=1,
        game_title="Demo Game",
        session_arc="Curious then mildly frustrated",
        friction_moments=[],
        clarity_moments=[],
        delight_moments=[],
        quality_issues=[],
        top_stop_risk_drivers=[],
        top_praised_features=[],
        top_clarity_fixes=[],
        bug_count=0,
        overall_friction="moderate",
        overall_engagement="light",
        overall_stop_risk="low",
        recommendations=[],
    )

    assert chunk.duration_seconds == 300.0
    assert analysis.moments[0].severity is FrictionSeverity.MODERATE
    assert report.video_id == "video-1"
