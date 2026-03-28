from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
import google.genai as genai
from pydantic import BaseModel, ConfigDict, model_validator

from gamesight.config import AnalysisConfig, DEFAULT_GAME_GENRE, ffmpeg_available, get_settings
from gamesight.db import Repository, database_ready
from gamesight.pipeline import analyze_and_store, derive_video_id
from gamesight.schemas.enums import VideoSourceType
from gamesight.schemas.report import VideoReport
from gamesight.schemas.video import VideoTimeline
from gamesight.video import is_youtube_url

router = APIRouter()


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str | None = None
    youtube_url: str | None = None
    game_title: str | None = None
    game_genre: str = DEFAULT_GAME_GENRE

    @model_validator(mode="after")
    def exactly_one_source(self) -> "AnalyzeRequest":
        if bool(self.file_path) == bool(self.youtube_url):
            raise ValueError("Provide exactly one of file_path or youtube_url.")
        return self


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    status: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_ready: bool
    ffmpeg_present: bool
    api_key_set: bool
    client_ready: bool


def _repository_from_request(request: Request) -> Repository:
    return request.app.state.repository


def _client_from_request(request: Request) -> genai.Client | None:
    return request.app.state.client


@router.post("/videos/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    request_model: AnalyzeRequest, background_tasks: BackgroundTasks, request: Request
) -> AnalyzeResponse:
    repository = _repository_from_request(request)
    client = _client_from_request(request)
    if client is None:
        raise HTTPException(
            status_code=503, detail="Gemini client is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY."
        )

    source = request_model.youtube_url or request_model.file_path or ""
    source_type = VideoSourceType.YOUTUBE if request_model.youtube_url else VideoSourceType.LOCAL
    if source_type is VideoSourceType.LOCAL:
        resolved_path = Path(source).expanduser().resolve()
        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail=f"Local file not found: {resolved_path}")
        filename = resolved_path.name
        source = str(resolved_path)
    else:
        if not is_youtube_url(source):
            raise HTTPException(status_code=400, detail="youtube_url must be a valid YouTube URL.")
        filename = source

    video_id = derive_video_id(source)
    await repository.create_pending_video(
        video_id=video_id,
        source=source,
        source_type=source_type.value,
        filename=filename,
    )
    background_tasks.add_task(
        analyze_and_store,
        client,
        repository,
        source,
        AnalysisConfig(game_title=request_model.game_title, game_genre=request_model.game_genre),
        video_id=video_id,
    )
    return AnalyzeResponse(video_id=video_id, status="queued")


@router.get("/videos")
async def list_videos(request: Request) -> list[dict[str, object]]:
    repository = _repository_from_request(request)
    return [video.model_dump() for video in await repository.list_videos()]


@router.get("/videos/{video_id}")
async def get_video(video_id: str, request: Request) -> dict[str, object]:
    repository = _repository_from_request(request)
    video = await repository.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return video.model_dump()


@router.get("/videos/{video_id}/timeline", response_model=VideoTimeline)
async def get_timeline(video_id: str, request: Request) -> VideoTimeline:
    repository = _repository_from_request(request)
    timeline = await repository.get_timeline(video_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Timeline not found.")
    return timeline


@router.get("/videos/{video_id}/report", response_model=VideoReport)
async def get_report(video_id: str, request: Request) -> VideoReport:
    repository = _repository_from_request(request)
    report = await repository.get_report(video_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.get("/videos/{video_id}/friction")
async def get_friction(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.friction_moments]


@router.get("/videos/{video_id}/clarity")
async def get_clarity(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.clarity_moments]


@router.get("/videos/{video_id}/delight")
async def get_delight(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.delight_moments]


@router.get("/videos/{video_id}/quality")
async def get_quality(video_id: str, request: Request) -> list[dict[str, object]]:
    report = await get_report(video_id, request)
    return [moment.model_dump() for moment in report.quality_issues]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    settings = get_settings()
    client = _client_from_request(request)
    return HealthResponse(
        db_ready=await database_ready(settings.database_path),
        ffmpeg_present=ffmpeg_available(),
        api_key_set=settings.gemini_api_key is not None,
        client_ready=client is not None,
    )


__all__ = ["AnalyzeRequest", "AnalyzeResponse", "HealthResponse", "router"]
