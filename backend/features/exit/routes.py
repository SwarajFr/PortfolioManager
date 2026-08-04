"""HTTP surface for exit signals and their tuning.

Settings responses are wrapped in `{"config": ...}` rather than returned bare so
the payload has somewhere to grow — the same shape the portfolio router already
uses, where a second key was needed later.
"""
from fastapi import APIRouter, Request

from .service import get_exit_signals
from .settings import get_settings, reset_settings, save_settings

router = APIRouter()


@router.get("/signals")
def exit_signals():
    return get_exit_signals()


@router.get("/settings")
def read_settings():
    return {"config": get_settings()}


@router.put("/settings")
async def update_settings(request: Request):
    body = await request.json()
    save_settings(body)
    return {"status": "ok"}


@router.post("/settings/reset")
def do_reset_settings():
    return {"config": reset_settings()}
