import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.research.models import DiscoveryResult, ResearchDiscoverRequest

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/discover", response_model=DiscoveryResult)
async def discover_videos(request: Request, payload: ResearchDiscoverRequest) -> DiscoveryResult:
    """Run discovery and return the final result as JSON."""
    discoverer = request.app.state.research_discoverer
    try:
        return await asyncio.wait_for(
            discoverer.discover(payload.game_name, refresh=payload.refresh),
            timeout=120,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Discovery timed out after 120s")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/discover/stream")
async def discover_videos_stream(request: Request, payload: ResearchDiscoverRequest) -> StreamingResponse:
    """Run discovery with SSE progress updates. Each event is a JSON line.

    Progress events: {"type": "progress", "message": "..."}
    Final result:    {"type": "result", "data": { ...DiscoveryResult... }}
    Error:           {"type": "error", "message": "..."}
    """
    discoverer = request.app.state.research_discoverer

    async def event_stream() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_progress(message: str) -> None:
            await progress_queue.put(message)

        async def run_discovery() -> DiscoveryResult:
            return await discoverer.discover(payload.game_name, refresh=payload.refresh, on_progress=on_progress)

        task = asyncio.create_task(run_discovery())

        # Stream progress events until discovery finishes
        while not task.done():
            try:
                message = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                yield json.dumps({"type": "progress", "message": message}) + "\n"
            except asyncio.TimeoutError:
                continue

        # Drain any remaining progress messages
        while not progress_queue.empty():
            message = await progress_queue.get()
            yield json.dumps({"type": "progress", "message": message}) + "\n"

        # Send final result or error
        try:
            result = task.result()
            yield json.dumps({"type": "result", "data": json.loads(result.model_dump_json())}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
