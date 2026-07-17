from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.kite import kite, set_access_token, is_authenticated
from config import API_SECRET, FRONTEND_URL
from features.screener.service import screener_on_login

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
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        set_access_token(data["access_token"])
        screener_on_login()  # non-blocking background history/incremental refresh

        return RedirectResponse(f"{FRONTEND_URL}/")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))