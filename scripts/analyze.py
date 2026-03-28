import argparse
import asyncio
import json
import logging
import sys

from gamesight.config import AnalysisConfig, get_settings, normalize_game_key
from gamesight.db import init_db, Repository
from gamesight.gemini import close_client, create_client
from gamesight.pipeline import analyze_and_store, process_study

logger = logging.getLogger("gamesight")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze gameplay videos with GameSight AI.")
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # --- analyze ---
    analyze = sub.add_parser("analyze", help="Analyze one or more videos (saved to DB)")
    analyze.add_argument("sources", nargs="+", help="Local MP4 paths or YouTube URLs")
    analyze.add_argument("--game-title", dest="game_title", required=True, help="Game title (used for cross-video grouping)")
    analyze.add_argument("--game-genre", dest="game_genre", default="unknown", help="Game genre label")
    analyze.add_argument("--duration-seconds", dest="duration_seconds", type=float, default=None, help="Duration override for YouTube")
    analyze.add_argument("--max-duration", dest="max_duration_seconds", type=float, default=None, help="Max duration to analyze in seconds (default: 3600)")
    analyze.add_argument("--keep-chunks", action="store_true", help="Keep local ffmpeg chunk files after analysis")
    analyze.add_argument("--parallel", dest="parallel", type=int, default=1, help="Number of videos to process in parallel (default: 1)")

    # --- study ---
    study = sub.add_parser("study", help="Run cross-video study for a game")
    study.add_argument("game_title", help="Game title (same as used in analyze)")

    # backward compat: bare source without subcommand
    parser.add_argument("source", nargs="?", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--game-title", dest="game_title_compat", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--game-genre", dest="game_genre_compat", default="unknown", help=argparse.SUPPRESS)
    parser.add_argument("--duration-seconds", dest="duration_seconds_compat", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--max-duration", dest="max_duration_seconds_compat", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--keep-chunks", dest="keep_chunks_compat", action="store_true", help=argparse.SUPPRESS)

    return parser


async def _run_analyze(args: argparse.Namespace) -> int:
    settings = get_settings()
    await init_db(settings.database_path)
    client = create_client()
    max_dur = args.max_duration_seconds or settings.max_duration_seconds
    config = AnalysisConfig(
        game_title=args.game_title,
        game_genre=args.game_genre,
        duration_seconds=args.duration_seconds,
        keep_chunk_files=args.keep_chunks,
        upload_concurrency=settings.upload_concurrency,
        chunk_concurrency=settings.chunk_concurrency,
        max_duration_seconds=max_dur,
    )
    repository = Repository(settings.database_path)
    parallel = max(1, args.parallel)
    semaphore = asyncio.Semaphore(parallel)
    sources: list[str] = args.sources
    results: dict[str, str] = {}

    async def _process_one(source: str) -> None:
        async with semaphore:
            logger.info("Starting analysis: %s", source)
            try:
                processed = await analyze_and_store(client, repository, source, config)
                results[source] = f"OK  video_id={processed.video.video_id}"
                logger.info("Completed: %s → video_id=%s", source, processed.video.video_id)
            except Exception as exc:
                results[source] = f"FAILED: {exc}"
                logger.error("Failed: %s → %s", source, exc)

    try:
        await asyncio.gather(*(_process_one(s) for s in sources))
    finally:
        await close_client(client)

    print("\n=== Results ===")
    for source, status in results.items():
        print(f"  {source}: {status}")

    failed = sum(1 for s in results.values() if s.startswith("FAILED"))
    total = len(sources)
    print(f"\n{total - failed}/{total} succeeded")
    if failed:
        print(f"{failed}/{total} failed")

    print(f"\nTo run cross-video study:\n  poetry run python scripts/analyze.py study \"{args.game_title}\"")

    return 1 if failed == total else 0


async def _run_study(args: argparse.Namespace) -> int:
    settings = get_settings()
    await init_db(settings.database_path)
    client = create_client()
    repository = Repository(settings.database_path)
    game_key = normalize_game_key(args.game_title)
    try:
        logger.info("Running cross-video study for game_key=%s", game_key)
        study = await process_study(client, repository, game_key)
        print(json.dumps(study.model_dump(mode="json"), indent=2))
        logger.info("Study complete: %d sessions, %d insights", study.total_sessions, len(study.insights))
    finally:
        await close_client(client)
    return 0


async def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        return await _run_analyze(args)
    if args.command == "study":
        return await _run_study(args)

    # backward compat: no subcommand, bare source
    if args.source:
        # Simulate the analyze subcommand
        args.sources = [args.source]
        args.game_title = args.game_title_compat
        args.game_genre = args.game_genre_compat
        args.duration_seconds = args.duration_seconds_compat
        args.max_duration_seconds = args.max_duration_seconds_compat
        args.keep_chunks = args.keep_chunks_compat
        args.parallel = 1
        if not args.game_title:
            print("Error: --game-title is required", file=sys.stderr)
            return 1
        return await _run_analyze(args)

    parser.print_help()
    return 1


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
