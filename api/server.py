"""
api/server.py — FastAPI application instance.

Wires up routers, dependencies, and startup/shutdown handlers.
"""

from __future__ import annotations

from fastapi import FastAPI

from database.connection import init_db
from api.routes import auth, portfolio, strategies, health

app = FastAPI(
    title="Stock Portfolio Suggestion Engine API",
    description="REST API for portfolio simulation and management",
    version="1.0.0",
)


@app.on_event("startup")
def startup_event() -> None:
    """Initialize database on startup."""
    init_db()


# Register routers
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(strategies.router)
app.include_router(health.router)
