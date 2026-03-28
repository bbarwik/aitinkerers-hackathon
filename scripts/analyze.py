import argparse
import asyncio
import json

from gamesight.config import AnalysisConfig, get_settings
from gamesight.gemini import close_client, create_client
from gamesight.pipeline import process_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a local gameplay video or YouTube URL with GameSight AI.")
    parser.add_argument("source", help="Local MP4 path or YouTube URL")
    parser.add_argument("--game-title", dest="game_title", default=None, help="Optional game title override")
    parser.add_argument("--game-genre", dest="game_genre", default="unknown", help="Optional game genre label")
    parser.add_argument(
        "--duration-seconds",
        dest="duration_seconds",
        type=float,
        default=None,
        help="Optional source duration override, mainly for YouTube when metadata lookup fails",
    )
    parser.add_argument("--keep-chunks", action="store_true", help="Keep local ffmpeg chunk files after analysis")
    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    client = create_client()
    try:
        result = await process_video(
            client,
            args.source,
            AnalysisConfig(
                game_title=args.game_title,
                game_genre=args.game_genre,
                duration_seconds=args.duration_seconds,
                keep_chunk_files=args.keep_chunks,
                upload_concurrency=settings.upload_concurrency,
                chunk_concurrency=settings.chunk_concurrency,
            ),
        )
    finally:
        await close_client(client)
    print(json.dumps(result.report.model_dump(mode="json"), indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
