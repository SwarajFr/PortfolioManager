"""HTTP surface for the Agent tab: one turn of chat per request.

Stateless by design. The full message list arrives from the browser on every
call and no conversation is stored server-side, which is what lets the frontend
own the transcript (`chatStore.js`) and survive a page unmount without the two
copies drifting apart.

The tool-calling loop runs inside `run_chat` and is finished before this returns
— the response is the completed turn, not a stream, so a slow local model shows
up as a slow request rather than a partial answer.
"""
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
