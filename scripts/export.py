"""Export all analysis data from the database as JSON files."""

import argparse
import asyncio
import json
from pathlib import Path

from gamesight.config import get_settings
from gamesight.db import Repository, init_db


async def _export_video(repository: Repository, video_id: str, output_dir: Path) -> None:
    video = await repository.get_video(video_id)
    if video is None:
        print(f"  Video {video_id} not found in DB")
        return

    video_dir = output_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    # Video metadata
    (video_dir / "video.json").write_text(json.dumps(video.model_dump(), indent=2))
    print(f"  Saved video.json")

    # Timeline
    timeline = await repository.get_timeline(video_id)
    if timeline:
        (video_dir / "timeline.json").write_text(json.dumps(timeline.model_dump(mode="json"), indent=2))
        print(f"  Saved timeline.json ({len(timeline.events)} events)")

    # Full report
    report = await repository.get_report(video_id)
    if report:
        report_data = report.model_dump(mode="json")
        (video_dir / "report.json").write_text(json.dumps(report_data, indent=2))
        print(f"  Saved report.json")

        # Individual sections for easy reading
        sections = {
            "friction": report_data.get("friction_moments", []),
            "clarity": report_data.get("clarity_moments", []),
            "delight": report_data.get("delight_moments", []),
            "quality": report_data.get("quality_issues", []),
            "sentiment": report_data.get("sentiment_moments", []),
            "retry": report_data.get("retry_moments", []),
            "verbal": report_data.get("verbal_moments", []),
        }
        for name, moments in sections.items():
            (video_dir / f"{name}.json").write_text(json.dumps(moments, indent=2))
            print(f"  Saved {name}.json ({len(moments)} moments)")

        # Highlights
        if report_data.get("highlights"):
            (video_dir / "highlights.json").write_text(json.dumps(report_data["highlights"], indent=2))
            print(f"  Saved highlights.json")

        # Executive summary
        if report_data.get("executive"):
            (video_dir / "executive.json").write_text(json.dumps(report_data["executive"], indent=2))
            print(f"  Saved executive.json")

        # Summary stats
        summary = {
            "video_id": report_data.get("video_id"),
            "game_title": report_data.get("game_title"),
            "game_key": report_data.get("game_key"),
            "duration_seconds": report_data.get("duration_seconds"),
            "chunk_count": report_data.get("chunk_count"),
            "overall_friction": report_data.get("overall_friction"),
            "overall_engagement": report_data.get("overall_engagement"),
            "overall_stop_risk": report_data.get("overall_stop_risk"),
            "bug_count": report_data.get("bug_count"),
            "avg_sentiment": report_data.get("avg_sentiment"),
            "sentiment_by_segment": report_data.get("sentiment_by_segment"),
            "total_retry_sequences": report_data.get("total_retry_sequences"),
            "first_attempt_failure_count": report_data.get("first_attempt_failure_count"),
            "notable_quotes": report_data.get("notable_quotes"),
        }
        if report_data.get("executive"):
            summary["session_health_score"] = report_data["executive"].get("session_health_score")
            summary["priority_actions"] = report_data["executive"].get("priority_actions")
        if report_data.get("highlights"):
            summary["top_highlight"] = report_data["highlights"].get("one_line_verdict")
        (video_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        print(f"  Saved summary.json")


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Export analysis data from DB as JSON files.")
    parser.add_argument("--video-id", dest="video_id", default=None, help="Export specific video by ID")
    parser.add_argument("--output", dest="output", default="data/exports", help="Output directory (default: data/exports)")
    args = parser.parse_args()

    settings = get_settings()
    await init_db(settings.database_path)
    repository = Repository(settings.database_path)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.video_id:
        print(f"Exporting video {args.video_id}...")
        await _export_video(repository, args.video_id, output_dir)
    else:
        videos = await repository.list_videos()
        if not videos:
            print("No videos found in DB.")
            return 0
        print(f"Found {len(videos)} videos\n")
        for video in videos:
            print(f"[{video.status}] {video.id} — {video.source}")
            if video.status == "complete":
                await _export_video(repository, video.id, output_dir)
            print()

    print(f"\nExported to {output_dir.resolve()}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
