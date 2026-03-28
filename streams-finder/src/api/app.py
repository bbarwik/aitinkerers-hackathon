import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from src.api.routes.research import router as research_router
from src.research.discoverer import ResearchDiscoverer
from src.research.query_generator import QueryGenerator
from src.research.twitch_provider import TwitchProvider
from src.research.youtube_provider import YouTubeProvider

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = genai.Client()
    query_gen = QueryGenerator(client=client)
    youtube = YouTubeProvider()

    twitch_id = os.environ.get("TWITCH_CLIENT_ID")
    twitch_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    twitch = TwitchProvider(client_id=twitch_id, client_secret=twitch_secret) if twitch_id and twitch_secret else None

    app.state.research_discoverer = ResearchDiscoverer(query_generator=query_gen, youtube=youtube, twitch=twitch)

    yield
    client.close()


app = FastAPI(title="Streams Finder", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(research_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
