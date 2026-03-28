from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gamesight.api.routes import router
from gamesight.config import APP_NAME, ensure_directories, get_settings
from gamesight.db import Repository, init_db
from gamesight.gemini import close_client, create_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ensure_directories(settings)
    await init_db(settings.database_path)
    app.state.repository = Repository(settings.database_path)
    app.state.client = create_client() if settings.gemini_api_key is not None else None
    try:
        yield
    finally:
        client = app.state.client
        if client is not None:
            await close_client(client)


app = FastAPI(title=APP_NAME, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

__all__ = ["app", "lifespan"]
