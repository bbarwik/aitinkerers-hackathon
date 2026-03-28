import asyncio
import logging
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import google.genai as genai
from google.genai import types

from gamesight.config import AnalysisConfig, ensure_directories, get_settings, normalize_game_key
from gamesight.db.repository import Repository
from gamesight.gemini.files import delete_file, upload_chunks
from gamesight.pipeline.aggregation import build_video_report
from gamesight.pipeline.chunk_pass import run_chunk_agents
from gamesight.pipeline.dedup import deduplicate_moments
from gamesight.pipeline.executive_pass import generate_executive_summary
from gamesight.pipeline.highlights import build_highlight_reel
from gamesight.pipeline.study import build_study_report
from gamesight.pipeline.timeline_pass import run_timeline_pass
from gamesight.schemas.study import StudyReport
from gamesight.pipeline.verification import verify_moments
from gamesight.schemas.enums import VideoSourceType
from gamesight.schemas.report import ProcessedVideo
from gamesight.schemas.video import VideoInfo
from gamesight.video import chunk_video, compute_chunks, is_youtube_url, probe_video, resolve_youtube_metadata

logger = logging.getLogger(__name__)


def derive_video_id(source: str) -> str:
    normalized_source = source.strip()
    if not is_youtube_url(normalized_source):
        normalized_source = str(Path(normalized_source).expanduser().resolve())
    return uuid5(NAMESPACE_URL, normalized_source).hex


async def _cleanup_local_chunks(chunk_paths: list[str]) -> None:
    for chunk_path in chunk_paths:
        path = Path(chunk_path)
        if path.exists():
            await asyncio.to_thread(path.unlink)
    directories = {str(Path(chunk_path).parent) for chunk_path in chunk_paths}
    for directory in directories:
        dir_path = Path(directory)
        if dir_path.exists() and not any(dir_path.iterdir()):
            await asyncio.to_thread(dir_path.rmdir)


async def process_video(
    client: genai.Client,
    source: str,
    analysis_config: AnalysisConfig | None = None,
) -> ProcessedVideo:
    settings = get_settings()
    ensure_directories(settings)
    resolved_config = analysis_config or AnalysisConfig()
    video_id = derive_video_id(source)
    uploaded_files: dict[int, types.File] = {}
    chunk_file_paths: list[str] = []

    max_dur = resolved_config.max_duration_seconds

    if is_youtube_url(source):
        youtube_duration_override = resolved_config.duration_seconds
        if youtube_duration_override is None:
            youtube_duration_override = 3600.0
        metadata = await resolve_youtube_metadata(
            source,
            duration_seconds_override=youtube_duration_override,
            cookies_path=settings.youtube_cookies_path,
        )
        effective_duration = min(metadata.duration_seconds, max_dur)
        resolved_game_title = resolved_config.resolved_game_title(metadata.title)
        game_key = normalize_game_key(resolved_game_title)
        video = VideoInfo(
            video_id=video_id,
            source_type=VideoSourceType.YOUTUBE,
            source=source,
            filename=f"{metadata.video_id}.youtube",
            title=resolved_game_title,
            game_key=game_key,
            duration_seconds=effective_duration,
        )
        chunks = compute_chunks(effective_duration, youtube_url=source)
    else:
        input_path = Path(source).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        probe = await probe_video(input_path)
        effective_duration = min(probe.duration_seconds, max_dur)
        resolved_game_title = resolved_config.resolved_game_title(input_path.stem)
        game_key = normalize_game_key(resolved_game_title)
        video = VideoInfo(
            video_id=video_id,
            source_type=VideoSourceType.LOCAL,
            source=str(input_path),
            filename=input_path.name,
            title=resolved_game_title,
            game_key=game_key,
            duration_seconds=effective_duration,
        )
        output_dir = settings.chunks_dir / video_id
        chunks = await chunk_video(input_path, output_dir, max_duration_seconds=max_dur)
        chunk_file_paths = [chunk.file_path for chunk in chunks if chunk.file_path is not None]
        uploaded_files = await upload_chunks(client, chunks, concurrency=resolved_config.upload_concurrency)

    try:
        timeline = await run_timeline_pass(client, video, chunks, uploaded_files, resolved_config)
        chunk_analyses = await run_chunk_agents(client, chunks, uploaded_files, timeline, resolved_config)
        deduplicated = deduplicate_moments(chunks, chunk_analyses, timeline)
        verified = verify_moments(deduplicated)
        report = build_video_report(video=video, timeline=timeline, analyses=chunk_analyses, deduplicated=verified)
        highlights = build_highlight_reel(video, verified)
        report = report.model_copy(update={"highlights": highlights})
        try:
            executive = await generate_executive_summary(client, report, resolved_config.game_genre)
            report = report.model_copy(update={"executive": executive})
        except Exception:
            logger.warning("Executive summary generation failed, continuing without it.")
        return ProcessedVideo(video=video, timeline=timeline, chunk_analyses=chunk_analyses, report=report)
    finally:
        await asyncio.gather(
            *(delete_file(client, file_ref) for file_ref in uploaded_files.values()),
            return_exceptions=True,
        )
        if chunk_file_paths and not resolved_config.keep_chunk_files:
            try:
                await _cleanup_local_chunks(chunk_file_paths)
            except Exception:
                pass


async def analyze_and_store(
    client: genai.Client,
    repository: Repository,
    source: str,
    analysis_config: AnalysisConfig | None = None,
    *,
    video_id: str | None = None,
) -> ProcessedVideo:
    resolved_video_id = video_id or derive_video_id(source)
    source_type = "youtube" if is_youtube_url(source) else "local"
    await repository.create_pending_video(
        video_id=resolved_video_id, source=source, source_type=source_type, filename=source,
    )
    await repository.update_video_status(resolved_video_id, status="analyzing", error_message=None)
    try:
        processed = await process_video(client, source, analysis_config)
        await repository.upsert_video_info(processed.video, status="complete", error_message=None)
        for chunk in processed.chunk_analyses:
            timeline_chunk = processed.timeline.chunks[chunk.chunk_index]
            await repository.save_chunk_analysis(
                processed.video.video_id,
                chunk_index=chunk.chunk_index,
                chunk_start_seconds=timeline_chunk.start_seconds,
                chunk_end_seconds=timeline_chunk.end_seconds,
                agent_type="friction",
                analysis=chunk.friction,
            )
            await repository.save_chunk_analysis(
                processed.video.video_id,
                chunk_index=chunk.chunk_index,
                chunk_start_seconds=timeline_chunk.start_seconds,
                chunk_end_seconds=timeline_chunk.end_seconds,
                agent_type="clarity",
                analysis=chunk.clarity,
            )
            await repository.save_chunk_analysis(
                processed.video.video_id,
                chunk_index=chunk.chunk_index,
                chunk_start_seconds=timeline_chunk.start_seconds,
                chunk_end_seconds=timeline_chunk.end_seconds,
                agent_type="delight",
                analysis=chunk.delight,
            )
            await repository.save_chunk_analysis(
                processed.video.video_id,
                chunk_index=chunk.chunk_index,
                chunk_start_seconds=timeline_chunk.start_seconds,
                chunk_end_seconds=timeline_chunk.end_seconds,
                agent_type="quality",
                analysis=chunk.quality,
            )
            if chunk.sentiment:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="sentiment",
                    analysis=chunk.sentiment,
                )
            if chunk.retry:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="retry",
                    analysis=chunk.retry,
                )
            if chunk.verbal:
                await repository.save_chunk_analysis(
                    processed.video.video_id,
                    chunk_index=chunk.chunk_index,
                    chunk_start_seconds=timeline_chunk.start_seconds,
                    chunk_end_seconds=timeline_chunk.end_seconds,
                    agent_type="verbal",
                    analysis=chunk.verbal,
                )
        await repository.save_timeline(processed.video.video_id, processed.timeline)
        await repository.save_report(processed.video.video_id, processed.report)
        return processed
    except Exception as exc:
        await repository.update_video_status(resolved_video_id, status="failed", error_message=str(exc))
        raise


async def process_study(
    client: genai.Client,
    repository: Repository,
    game_key: str,
) -> StudyReport:
    reports = await repository.get_all_reports(game_key)
    if not reports:
        raise ValueError(f"No completed reports found for game_key: {game_key}")
    study = await build_study_report(client, reports, game_key)
    await repository.save_study_report(game_key, study)
    return study


__all__ = ["analyze_and_store", "derive_video_id", "process_study", "process_video"]
