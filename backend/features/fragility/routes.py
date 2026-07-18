from fastapi import APIRouter, HTTPException

from .service import get_diversity_analysis

router = APIRouter()


@router.get("/analysis")
async def analysis():
    try:
        return get_diversity_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
