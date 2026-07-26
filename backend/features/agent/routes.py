from fastapi import APIRouter, HTTPException, Request

from .service import run_chat

router = APIRouter()


@router.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages (a non-empty list) is required")
    return run_chat(messages)
