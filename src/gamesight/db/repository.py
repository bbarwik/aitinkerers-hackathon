import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from gamesight.config import get_settings
from gamesight.db.database import get_connection
from gamesight.schemas.report import VideoReport
from gamesight.schemas.study import StudyReport
from gamesight.schemas.video import VideoInfo, VideoTimeline


class StoredVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    source_type: str
    filename: str
    duration_seconds: float
    status: str
    error_message: str | None
    created_at: str


class Repository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or get_settings().database_path)

    async def _fetch_one(self, query: str, parameters: tuple[object, ...]) -> dict[str, object] | None:
        async with await get_connection(self.database_path) as db:
            async with db.execute(query, parameters) as cursor:
                row = await cursor.fetchone()
        return None if row is None else dict(row)

    async def create_pending_video(
        self,
        *,
        video_id: str,
        source: str,
        source_type: str,
        filename: str,
    ) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO videos (id, source, source_type, filename, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, 'pending', NULL)
                ON CONFLICT(id) DO UPDATE SET
                    source = excluded.source,
                    source_type = excluded.source_type,
                    filename = excluded.filename,
                    status = 'pending',
                    error_message = NULL
                """,
                (video_id, source, source_type, filename, 0.0),
            )
            await db.commit()

    async def upsert_video_info(self, video: VideoInfo, *, status: str, error_message: str | None) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO videos (id, source, source_type, filename, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source = excluded.source,
                    source_type = excluded.source_type,
                    filename = excluded.filename,
                    duration_seconds = excluded.duration_seconds,
                    status = excluded.status,
                    error_message = excluded.error_message
                """,
                (
                    video.video_id,
                    video.source,
                    video.source_type.value,
                    video.filename,
                    video.duration_seconds,
                    status,
                    error_message,
                ),
            )
            await db.commit()

    async def update_video_status(self, video_id: str, *, status: str, error_message: str | None) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                "UPDATE videos SET status = ?, error_message = ? WHERE id = ?",
                (status, error_message, video_id),
            )
            await db.commit()

    async def save_chunk_analysis(
        self,
        video_id: str,
        *,
        chunk_index: int,
        chunk_start_seconds: float,
        chunk_end_seconds: float,
        agent_type: str,
        analysis: BaseModel,
    ) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO chunk_analyses (
                    video_id, chunk_index, chunk_start_seconds, chunk_end_seconds, agent_type, analysis_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id, chunk_index, agent_type) DO UPDATE SET
                    analysis_json = excluded.analysis_json,
                    chunk_start_seconds = excluded.chunk_start_seconds,
                    chunk_end_seconds = excluded.chunk_end_seconds
                """,
                (
                    video_id,
                    chunk_index,
                    chunk_start_seconds,
                    chunk_end_seconds,
                    agent_type,
                    analysis.model_dump_json(),
                ),
            )
            await db.commit()

    async def save_timeline(self, video_id: str, timeline: VideoTimeline) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO video_timelines (video_id, timeline_json, game_title)
                VALUES (?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    timeline_json = excluded.timeline_json,
                    game_title = excluded.game_title
                """,
                (video_id, timeline.model_dump_json(), timeline.game_title),
            )
            await db.commit()

    async def save_report(self, video_id: str, report: VideoReport) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO video_reports (
                    video_id, report_json, overall_friction, overall_engagement, overall_stop_risk, bug_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    report_json = excluded.report_json,
                    overall_friction = excluded.overall_friction,
                    overall_engagement = excluded.overall_engagement,
                    overall_stop_risk = excluded.overall_stop_risk,
                    bug_count = excluded.bug_count
                """,
                (
                    video_id,
                    report.model_dump_json(),
                    report.overall_friction,
                    report.overall_engagement,
                    report.overall_stop_risk,
                    report.bug_count,
                ),
            )
            await db.commit()

    async def list_videos(self) -> list[StoredVideo]:
        async with await get_connection(self.database_path) as db:
            rows = await db.execute_fetchall("SELECT * FROM videos ORDER BY created_at DESC")
        return [StoredVideo.model_validate(dict(row)) for row in rows]

    async def get_video(self, video_id: str) -> StoredVideo | None:
        row = await self._fetch_one("SELECT * FROM videos WHERE id = ?", (video_id,))
        return None if row is None else StoredVideo.model_validate(row)

    async def get_timeline(self, video_id: str) -> VideoTimeline | None:
        row = await self._fetch_one("SELECT timeline_json FROM video_timelines WHERE video_id = ?", (video_id,))
        if row is None:
            return None
        timeline_json = row["timeline_json"]
        if not isinstance(timeline_json, str):
            raise TypeError("timeline_json must be stored as TEXT in SQLite.")
        payload = json.loads(timeline_json)
        return VideoTimeline.model_validate(payload)

    async def get_report(self, video_id: str) -> VideoReport | None:
        row = await self._fetch_one("SELECT report_json FROM video_reports WHERE video_id = ?", (video_id,))
        if row is None:
            return None
        report_json = row["report_json"]
        if not isinstance(report_json, str):
            raise TypeError("report_json must be stored as TEXT in SQLite.")
        payload = json.loads(report_json)
        return VideoReport.model_validate(payload)

    async def get_all_reports(self, game_key: str | None = None) -> list[VideoReport]:
        async with await get_connection(self.database_path) as db:
            if game_key:
                rows = await db.execute_fetchall(
                    "SELECT report_json FROM video_reports WHERE json_extract(report_json, '$.game_key') = ?",
                    (game_key,),
                )
            else:
                rows = await db.execute_fetchall("SELECT report_json FROM video_reports")
        reports: list[VideoReport] = []
        for row in rows:
            report_json = row["report_json"]
            if not isinstance(report_json, str):
                raise TypeError("report_json must be stored as TEXT in SQLite.")
            reports.append(VideoReport.model_validate_json(report_json))
        return reports

    async def save_study_report(self, game_key: str, study: StudyReport) -> None:
        async with await get_connection(self.database_path) as db:
            await db.execute(
                """INSERT INTO study_reports (game_key, game_title, report_json, session_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(game_key) DO UPDATE SET
                       game_title = excluded.game_title,
                       report_json = excluded.report_json,
                       session_count = excluded.session_count""",
                (game_key, study.game_title, study.model_dump_json(), study.total_sessions),
            )
            await db.commit()

    async def get_study_report(self, game_key: str) -> StudyReport | None:
        row = await self._fetch_one("SELECT report_json FROM study_reports WHERE game_key = ?", (game_key,))
        if row is None:
            return None
        report_json = row["report_json"]
        if not isinstance(report_json, str):
            raise TypeError("report_json must be stored as TEXT in SQLite.")
        return StudyReport.model_validate_json(report_json)


__all__ = ["Repository", "StoredVideo"]
