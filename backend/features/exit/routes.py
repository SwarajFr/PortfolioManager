from fastapi import APIRouter, Request
from .service import get_exit_signals
from .settings import get_settings, save_settings, reset_settings

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
