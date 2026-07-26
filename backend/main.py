from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from features.auth.routes import router as auth_router
from features.portfolio.routes import router as portfolio_router
from features.exit.routes import router as exit_router
from features.fragility.routes import router as fragility_router
from features.screener.routes import router as screener_router
from features.agent.routes import router as agent_router
from features.mcp.server import mcp_app

# The MCP ASGI app's lifespan runs its streamable-HTTP session manager; it MUST
# be attached to the parent app or MCP requests fail.
app = FastAPI(lifespan=mcp_app.lifespan)

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
app.include_router(agent_router, prefix="/api/agent")

# Streamable-HTTP MCP endpoint at http://localhost:8000/mcp/
app.mount("/mcp", mcp_app)
