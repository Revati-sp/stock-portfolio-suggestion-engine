#!/usr/bin/env python3
"""
backfill_with_historical_prices.py — Populate trend with REAL historical prices.

Fetches actual historical prices from Yahoo Finance for the past N days,
calculates what the current portfolio would have been worth on each date,
and inserts those values into portfolio_daily_trend.

Uses 100% REAL data from yfinance - no synthetic/mock generation.

Usage:
    python scripts/backfill_with_historical_prices.py [--username demo] [--days 10]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

# Add parent directory to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from database.connection import get_db, get_user_id


def get_current_holdings(user_id: int) -> dict[str, float]:
    """
    Fetch current portfolio holdings from database.
    Returns dict: {ticker: shares}
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT holdings
        FROM current_holdings
        WHERE user_id = ?
        ORDER BY saved_at DESC
        LIMIT 1
        """,
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        print("❌ No current holdings found for user")
        return {}

    import json
    holdings_list = json.loads(result[0])
    return {ticker: shares for ticker, shares in holdings_list}


def fetch_historical_prices(tickers: list[str], days: int) -> dict[str, dict[str, float]]:
    """
    Fetch historical prices from Yahoo Finance for the past N days.
    Returns: {date: {ticker: price, ...}, ...}
    """
    import pandas as pd

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days + 10)  # Extra days for weekends/holidays

    print(f"Fetching historical prices from {start_date} to {end_date}...")

    prices_by_date = {}

    # Fetch each ticker individually to handle various data formats reliably
    for ticker in tickers:
        try:
            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False
            )

            for date, row in data.iterrows():
                date_str = str(date.date()) if hasattr(date, 'date') else str(date)
                close_price = row["Close"]

                try:
                    price_float = float(close_price)
                    if price_float > 0:  # Valid price
                        if date_str not in prices_by_date:
                            prices_by_date[date_str] = {}
                        prices_by_date[date_str][ticker] = price_float
                except (ValueError, TypeError):
                    continue  # Skip invalid prices
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch {ticker}: {e}")

    return prices_by_date


def calculate_portfolio_value(holdings: dict[str, float], prices: dict[str, float]) -> float:
    """Calculate portfolio value given holdings and current prices."""
    total = 0.0
    for ticker, shares in holdings.items():
        if ticker in prices:
            total += shares * prices[ticker]
    return total


def backfill_with_historical_prices(username: str, days: int = 10) -> None:
    """
    Backfill portfolio_daily_trend with historical portfolio values.
    Uses real historical prices from Yahoo Finance.
    """
    user_id = get_user_id(username)
    if user_id is None:
        print(f"❌ User '{username}' not found in database")
        return

    # Get current holdings
    holdings = get_current_holdings(user_id)
    if not holdings:
        print("❌ No holdings found. Generate a portfolio first.")
        return

    tickers = list(holdings.keys())
    print(f"Current holdings: {holdings}")
    print(f"Tickers: {tickers}")
    print()

    # Fetch historical prices
    try:
        prices_by_date = fetch_historical_prices(tickers, days)
    except Exception as e:
        print(f"❌ Failed to fetch historical prices: {e}")
        return

    if not prices_by_date:
        print("❌ No historical data found")
        return

    # Calculate portfolio values for each date
    portfolio_values = []
    for date_str in sorted(prices_by_date.keys()):
        prices = prices_by_date[date_str]
        # Skip if missing prices for any ticker
        if not all(ticker in prices for ticker in tickers):
            continue

        value = calculate_portfolio_value(holdings, prices)
        portfolio_values.append((date_str, round(value, 2)))

    if not portfolio_values:
        print("❌ No complete price data available")
        return

    # Insert into database
    conn = get_db()
    cursor = conn.cursor()
    inserted = 0

    for date_str, value in portfolio_values:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO portfolio_daily_trend
                (user_id, date, total_portfolio_value)
                VALUES (?, ?, ?)
                """,
                (user_id, date_str, value)
            )
            inserted += 1
        except Exception as e:
            print(f"⚠️  Failed to insert {date_str}: {e}")

    conn.commit()
    conn.close()

    print(f"✅ Inserted {inserted} historical portfolio values")
    print(f"   Date range: {portfolio_values[0][0]} → {portfolio_values[-1][0]}")
    print(f"   Value range: ${min(v[1] for v in portfolio_values):.2f} → ${max(v[1] for v in portfolio_values):.2f}")
    print(f"   Data source: Real historical prices from Yahoo Finance")
    print()
    print("Values by date:")
    for date_str, value in portfolio_values:
        print(f"   {date_str}: ${value:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill portfolio trend with real historical prices from Yahoo Finance."
    )
    parser.add_argument(
        "--username",
        default="demo",
        help="Username to backfill (default: demo)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help="Number of past days to include (default: 10)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Portfolio Trend Backfill with Real Historical Prices")
    print("=" * 70)
    print(f"Username: {args.username}")
    print(f"Historical period: Last {args.days} days")
    print(f"Data source: Yahoo Finance (real prices, no mocks)")
    print()

    backfill_with_historical_prices(args.username, args.days)


if __name__ == "__main__":
    # Import pandas here to avoid import errors
    import pandas as pd
    main()
