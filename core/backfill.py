"""
core/backfill.py — Real historical portfolio-value backfill using Yahoo Finance.

Computes what the current portfolio would have been worth on each of the past N
trading days using real close prices from yfinance — no synthetic data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple

import pandas as pd
import yfinance as yf


def fetch_historical_values(
    holdings: List[Tuple[str, float]],
    days: int = 14,
) -> List[Tuple[str, float]]:
    """
    Fetch real historical prices from Yahoo Finance and compute portfolio values.

    For each trading day in the past `days` calendar days, calculates the total
    portfolio value (sum of shares × closing price) using the fixed holdings.

    Args:
        holdings: [(ticker, shares), ...] — shares are fixed at current allocation
        days: Number of calendar days to look back (fetches extras to cover weekends)

    Returns:
        [(date_str, portfolio_value), ...] sorted oldest-first, only days where
        ALL tickers have price data (no partial days).
    """
    if not holdings:
        return []

    tickers = [t for t, _ in holdings]
    shares_map = {t: s for t, s in holdings}

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days + 10)  # Extra buffer for weekends/holidays

    prices_by_date: dict[str, dict[str, float]] = {}

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if data is None or data.empty:
                continue
            # Flatten multi-index columns from newer yfinance (e.g. ('Close', 'BND') → 'Close')
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
            for date_idx, row in data.iterrows():
                date_str = str(date_idx.date()) if hasattr(date_idx, "date") else str(date_idx)
                try:
                    close = float(row["Close"])
                    if close > 0:
                        if date_str not in prices_by_date:
                            prices_by_date[date_str] = {}
                        prices_by_date[date_str][ticker] = close
                except (ValueError, TypeError):
                    continue
        except Exception:
            continue

    # Only keep dates where ALL tickers have price data
    complete_dates = sorted(
        date_str
        for date_str, prices in prices_by_date.items()
        if all(t in prices for t in tickers)
    )

    # Trim to the requested number of days
    recent_dates = complete_dates[-days:] if len(complete_dates) > days else complete_dates

    results = []
    for date_str in recent_dates:
        prices = prices_by_date[date_str]
        value = sum(shares_map[t] * prices[t] for t in tickers)
        results.append((date_str, round(value, 2)))

    return results
