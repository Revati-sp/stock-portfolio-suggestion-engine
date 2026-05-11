"""
api/schemas.py — Pydantic models for FastAPI request/response validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PortfolioGenerateRequest(BaseModel):
    investment_amount: float
    strategies: list[str]


class StrategyInfo(BaseModel):
    name: str
    tickers: list[str]


class PortfolioRow(BaseModel):
    Ticker: str
    Strategy: str
    allocation_usd: float
    current_price: float | None
    shares: float | None
    current_value: float | None
    gain_loss: float | None


class PortfolioGenerateResponse(BaseModel):
    rows: list[dict[str, Any]]
    dollar_per_ticker: dict[str, float]
    total_portfolio_value: float
    failed_tickers: list[str]


class PortfolioHoldingsResponse(BaseModel):
    holdings: list[list[str | float]] | None
    strategies: list[str] | None
    investment_amount: float | None
    dollar_per_ticker: dict[str, float] | None
    saved_at: str | None


class MarkToMarketResponse(BaseModel):
    rows: list[dict[str, Any]]
    total_portfolio_value: float
    gains: list[dict[str, Any]]


class HistoryRecord(BaseModel):
    date: str
    strategies: str
    investment_amount: float
    total_portfolio_value: float


class TrendRecord(BaseModel):
    date: str
    total_portfolio_value: float
