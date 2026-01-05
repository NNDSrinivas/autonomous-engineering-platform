from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
from typing import AsyncGenerator
from backend.services.review_service import generate_review_stream

router = APIRouter(prefix="/api/review")


@router.get("/stream")
async def review_stream(request: Request):
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in generate_review_stream():
                # Stop if client disconnects
                if await request.is_disconnected():
                    break

                yield f"event: {event['type']}\n"
                yield f"data: {event['data']}\n\n"

                await asyncio.sleep(0.01)

        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
