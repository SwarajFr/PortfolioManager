"""REST surface for the advisor.

Exists so the recommendations can be inspected — and regression-tested — without
an LLM anywhere in the loop, and so the frontend can edit the investor profile.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from core.data import NotAuthenticatedError

from .service import advice_history, buy_ideas, portfolio_actions
from .settings import get_settings, reset_advisor_settings, save_advisor_settings

router = APIRouter()

_LOGIN_REQUIRED = "Kite session missing or expired. Log in, then try again."


@router.get("/actions")
def actions(
    horizon_months: float | None = Query(None, gt=0),
    target_gain_pct: float | None = Query(None, gt=0),
    limit: int | None = Query(None, gt=0),
):
    try:
        return portfolio_actions(horizon_months, target_gain_pct, limit)
    except NotAuthenticatedError:
        # A cold token is a login problem, not a server fault — say which.
        raise HTTPException(status_code=401, detail=_LOGIN_REQUIRED)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ideas")
def ideas(
    horizon_months: float | None = Query(None, gt=0),
    target_gain_pct: float | None = Query(None, gt=0),
    limit: int = Query(10, gt=0, le=50),
    exclude_held: bool = True,
):
    try:
        return buy_ideas(horizon_months, target_gain_pct, limit, exclude_held)
    except NotAuthenticatedError:
        raise HTTPException(status_code=401, detail=_LOGIN_REQUIRED)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/journal")
def read_journal(limit: int = Query(20, gt=0, le=200), kind: str | None = None):
    return advice_history(limit, kind)


@router.get("/profile")
def read_profile():
    return {"config": get_settings()}


@router.put("/profile")
async def update_profile(request: Request):
    body = await request.json()
    save_advisor_settings(body)
    return {"config": get_settings()}


@router.post("/profile/reset")
def do_reset_profile():
    return {"config": reset_advisor_settings()}
