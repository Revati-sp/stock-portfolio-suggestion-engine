"""
api/routes/portfolio.py — Portfolio generation and management endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from api.schemas import (
    PortfolioGenerateRequest,
    PortfolioGenerateResponse,
    PortfolioHoldingsResponse,
    MarkToMarketResponse,
    HistoryRecord,
    TrendRecord,
)
from core.portfolio import (
    build_portfolio_table,
    build_portfolio_table_from_saved,
    extract_priced_holdings,
    portfolio_totals,
)
from core.strategies import STRATEGY_TICKERS
from database.repositories import (
    append_record,
    backfill_trend_from_holdings,
    ensure_daily_trend_file,
    ensure_history_file,
    load_current_holdings,
    load_daily_trend,
    load_recent_records,
    save_current_holdings,
    upsert_daily_portfolio_value,
)

router = APIRouter()


@router.post("/api/portfolio/generate", response_model=PortfolioGenerateResponse)
def generate_portfolio(
    req: PortfolioGenerateRequest,
    user_slug: str = Depends(get_current_user),
) -> PortfolioGenerateResponse:
    """Generate a new portfolio from strategies and investment amount."""
    # Validate inputs
    issues = []
    if req.investment_amount < 5000:
        issues.append("Investment amount must be at least $5,000")
    if len(req.strategies) < 1 or len(req.strategies) > 2:
        issues.append("Please pick either one or exactly two investment strategies")

    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(issues),
        )

    # Build portfolio
    df, warnings = build_portfolio_table(req.strategies, req.investment_amount)

    # Calculate totals
    basis, marked, gain_loss = portfolio_totals(df, req.investment_amount)

    # Extract priced holdings and save
    holdings = extract_priced_holdings(df)
    # Extract per-ticker allocations from DataFrame
    dollar_per_ticker_map = dict(zip(df["Ticker"], df["Allocation (USD)"]))

    ensure_history_file(user_slug)
    save_current_holdings(
        user_slug,
        req.strategies,
        req.investment_amount,
        holdings,
        dollar_per_ticker=dollar_per_ticker_map,
    )
    append_record(user_slug, req.strategies, req.investment_amount, marked)

    # Update daily trend and backfill real historical prices
    ensure_daily_trend_file(user_slug)
    upsert_daily_portfolio_value(user_slug, marked)
    try:
        backfill_trend_from_holdings(user_slug, holdings, days=14)
    except Exception:
        pass  # Backfill is best-effort; never block portfolio generation

    return PortfolioGenerateResponse(
        rows=df.to_dict("records"),
        dollar_per_ticker=dollar_per_ticker_map,
        total_portfolio_value=marked,
        failed_tickers=warnings,
    )


@router.get("/api/portfolio/holdings", response_model=PortfolioHoldingsResponse)
def get_holdings(user_slug: str = Depends(get_current_user)) -> PortfolioHoldingsResponse:
    """Load the user's current holdings from saved JSON."""
    payload = load_current_holdings(user_slug)
    if payload is None:
        return PortfolioHoldingsResponse(
            holdings=None,
            strategies=None,
            investment_amount=None,
            dollar_per_ticker=None,
            saved_at=None,
        )
    return PortfolioHoldingsResponse(
        holdings=payload.get("holdings"),
        strategies=payload.get("strategies"),
        investment_amount=payload.get("investment_amount"),
        dollar_per_ticker=payload.get("dollar_per_ticker"),
        saved_at=payload.get("saved_at"),
    )


@router.post("/api/portfolio/mark-to-market", response_model=MarkToMarketResponse)
def mark_to_market(user_slug: str = Depends(get_current_user)) -> MarkToMarketResponse:
    """Re-price saved holdings and update daily trend."""
    payload = load_current_holdings(user_slug)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved holdings found for user",
        )

    # Rebuild table with fresh prices
    df, warnings = build_portfolio_table_from_saved(payload)
    basis, marked, gain_loss = portfolio_totals(df, payload.get("investment_amount", 0))

    # Update daily trend
    ensure_daily_trend_file(user_slug)
    upsert_daily_portfolio_value(user_slug, marked)

    rows = df.to_dict("records")
    gains = [
        {
            "ticker": row.get("Ticker"),
            "gain_loss": row.get("Gain/Loss (USD)"),
        }
        for row in rows
    ]

    return MarkToMarketResponse(
        rows=rows,
        total_portfolio_value=marked,
        gains=gains,
    )


@router.get("/api/portfolio/history", response_model=list[HistoryRecord])
def get_history(
    limit: int = 5, user_slug: str = Depends(get_current_user)
) -> list[HistoryRecord]:
    """Load recent portfolio generation records."""
    records = load_recent_records(user_slug, limit=limit)
    return [HistoryRecord(**r) for r in records]


@router.get("/api/portfolio/trend", response_model=list[TrendRecord])
def get_trend(
    limit: int = 5, user_slug: str = Depends(get_current_user)
) -> list[TrendRecord]:
    """Load daily portfolio value trend."""
    rows = load_daily_trend(user_slug, limit=limit)
    return [TrendRecord(**r) for r in rows]


@router.post("/api/portfolio/trend")
def update_trend(
    data: dict[str, float], user_slug: str = Depends(get_current_user)
) -> dict[str, str]:
    """Update today's portfolio value in the trend."""
    total_value = data.get("total_portfolio_value", 0.0)
    ensure_daily_trend_file(user_slug)
    upsert_daily_portfolio_value(user_slug, total_value)
    return {"status": "updated"}
