"""HTTP surface for the fragility analysis.

One read-only endpoint. The blanket 500 handler is deliberate: the engine is a
chain of linear algebra over live holdings, and a singular covariance matrix or
an unpriceable position surfaces as an arbitrary numpy/pandas exception. Letting
those escape as an unhandled error would return no body at all, so they are
converted into a 500 the frontend can display.

Note there is deliberately no settings endpoint here yet: `long_window` is
readable and writable in `settings.py` but nothing is wired to HTTP, so it is
currently changeable only in storage. See that module's note.
"""
from fastapi import APIRouter, HTTPException

from .service import get_diversity_analysis

router = APIRouter()


@router.get("/analysis")
async def analysis():
    try:
        return get_diversity_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
