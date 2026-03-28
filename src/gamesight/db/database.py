from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from gamesight.config import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunk_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL REFERENCES videos(id),
    chunk_index INTEGER NOT NULL,
    chunk_start_seconds REAL NOT NULL,
    chunk_end_seconds REAL NOT NULL,
    agent_type TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, chunk_index, agent_type)
);

CREATE TABLE IF NOT EXISTS video_timelines (
    video_id TEXT PRIMARY KEY REFERENCES videos(id),
    timeline_json TEXT NOT NULL,
    game_title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_reports (
    video_id TEXT PRIMARY KEY REFERENCES videos(id),
    report_json TEXT NOT NULL,
    overall_friction TEXT,
    overall_engagement TEXT,
    overall_stop_risk TEXT,
    bug_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_reports (
    game_key TEXT PRIMARY KEY,
    game_title TEXT NOT NULL,
    report_json TEXT NOT NULL,
    session_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db(database_path: str | Path | None = None) -> None:
    resolved_path = Path(database_path or get_settings().database_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(resolved_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript(SCHEMA_SQL)
        await db.commit()


DB_BUSY_TIMEOUT_MS = 30_000


@asynccontextmanager
async def get_connection(database_path: str | Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    resolved_path = Path(database_path or get_settings().database_path)
    async with aiosqlite.connect(resolved_path) as connection:
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys=ON")
        await connection.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
        yield connection


async def database_ready(database_path: str | Path | None = None) -> bool:
    try:
        async with aiosqlite.connect(Path(database_path or get_settings().database_path)) as db:
            await db.execute("SELECT 1")
        return True
    except aiosqlite.Error:
        return False


__all__ = ["SCHEMA_SQL", "database_ready", "get_connection", "init_db"]
