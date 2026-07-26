from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.kite import kite, is_authenticated
from config import FRONTEND_URL
from .service import complete_login

router = APIRouter()


@router.get("/status")
def status():
    return {"authenticated": is_authenticated()}


@router.get("/login")
def login():
    return RedirectResponse(kite.login_url())


@router.get("/callback")
def callback(request_token: str):
    try:
        complete_login(request_token)
        return RedirectResponse(f"{FRONTEND_URL}/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
