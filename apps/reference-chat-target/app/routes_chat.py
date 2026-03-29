"""Chat API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/v1", tags=["chat"])


def _get_chat_service(request: Request):
    return request.app.state.chat_service


def _get_conversations(request: Request):
    return request.app.state.conversations


def _get_traces(request: Request):
    return request.app.state.traces


def _get_settings(request: Request):
    return request.app.state.settings


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    svc = _get_chat_service(request)

    # Reject streaming JSON
    if req.stream and req.response_mode == "json":
        raise HTTPException(
            status_code=400,
            detail="Structured JSON output is not supported with streaming. Use stream=false or response_mode=text.",
        )

    if req.stream:
        return StreamingResponse(
            svc.handle_stream(req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response = await svc.handle_chat(req)
    if response.blocked:
        headers = {
            key: value
            for key, value in response.proxy_block_headers.items()
            if value
        }
        return JSONResponse(
            status_code=200,
            content=response.model_dump(),
            headers=headers,
        )
    return response


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    svc = _get_chat_service(request)

    if req.response_mode == "json":
        raise HTTPException(
            status_code=400,
            detail="Structured JSON output is not supported with streaming.",
        )

    req.stream = True
    return StreamingResponse(
        svc.handle_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    store = _get_conversations(request)
    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.model_dump()


@router.get("/traces/{request_id}")
async def get_trace(request_id: str, request: Request):
    store = _get_traces(request)
    trace = store.get(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    # Redact canary token from API response
    data = trace.model_dump()
    data.pop("canary_token", None)
    return data
