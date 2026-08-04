"""HTTP surface for the screener: strategy metadata, screens, and refresh.

The status-code split reflects whose fault the failure is. `/scan` turns
`ValueError` into 400 because the service raises it for an unknown strategy
name, which is the caller's input. `/refresh` returns 500 for anything, because
by then the only failures left are broker or storage problems.

`/scan` and `/individual` read the precomputed `signals` table and never fetch;
only `/refresh` touches the network, which is what keeps a screen fast and
usable on a cold token.
"""
from fastapi import APIRouter, HTTPException, Request

from .service import (
    get_individual,
    get_status,
    get_strategies,
    run_scan,
    trigger_refresh,
)

router = APIRouter()


@router.get("/strategies")
def strategies():
    return get_strategies()


@router.get("/individual")
def individual(strategy: str):
    return get_individual(strategy)


@router.post("/scan")
async def scan(request: Request):
    body = await request.json() if await request.body() else {}
    try:
        return run_scan(
            strategies=body.get("strategies"),
            weights=body.get("weights"),
            k=body.get("k"),
            fallback_n=body.get("fallback_n"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/refresh")
def refresh():
    try:
        return trigger_refresh()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status")
def status():
    return get_status()
