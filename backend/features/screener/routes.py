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
    return run_scan(
        strategies=body.get("strategies"),
        weights=body.get("weights"),
        k=body.get("k"),
        fallback_n=body.get("fallback_n"),
    )


@router.post("/refresh")
def refresh():
    try:
        return trigger_refresh()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def status():
    return get_status()
