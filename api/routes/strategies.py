"""
api/routes/strategies.py — Investment strategy endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import StrategyInfo
from core.strategies import STRATEGY_TICKERS

router = APIRouter()


@router.get("/api/strategies")
def get_strategies() -> dict[str, list[StrategyInfo]]:
    """List all investment strategies with their tickers."""
    strategies = [
        StrategyInfo(name=name, tickers=tickers)
        for name, tickers in STRATEGY_TICKERS.items()
    ]
    return {"strategies": strategies}
