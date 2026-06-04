from fastapi import APIRouter, HTTPException, Query
from .service import get_fragility_analysis, get_fragility_whatif

router = APIRouter()


@router.get("/analysis")
async def analysis():
    try:
        return get_fragility_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatif")
async def whatif(
    ticker: str = Query(..., description="Ticker symbol to override"),
    new_weight: float = Query(..., ge=1, le=50, description="New weight as a percentage 1-50"),
):
    try:
        return get_fragility_whatif(ticker, new_weight)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
