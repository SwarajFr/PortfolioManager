from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from features.auth.routes import router as auth_router
from features.portfolio.routes import router as portfolio_router
from features.exit.routes import router as exit_router
from features.fragility.routes import router as fragility_router
from features.screener.routes import router as screener_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(portfolio_router, prefix="/api/portfolio")
app.include_router(exit_router, prefix="/api/exit")
app.include_router(fragility_router, prefix="/api/fragility")
app.include_router(screener_router, prefix="/api/screener")
