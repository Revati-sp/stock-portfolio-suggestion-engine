"""
history.py — Portfolio history and daily trend tracking via SQLite.

Replaces CSV/JSON file storage with database-backed persistence.
Public interface unchanged so callers in app.py and api.py work without modification.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterable, List, Optional, Tuple

from database.connection import get_db, get_user_id


def ensure_history_file(user_slug: str) -> None:
    """No-op for backward compatibility. User must be logged in (exists in DB)."""
    pass


def ensure_daily_trend_file(user_slug: str) -> None:
    """No-op for backward compatibility. User must be logged in (exists in DB)."""
    pass


def append_record(
    user_slug: str,
    strategies: Iterable[str],
    investment_amount: float,
    total_value: float,
) -> None:
    """Insert a new portfolio generation record."""
    user_id = get_user_id(user_slug)
    if user_id is None:
        return

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strategies_str = " + ".join(sorted(strategies))

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO portfolio_history
            (user_id, date, strategies, investment_amount, total_portfolio_value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, date_str, strategies_str, round(float(investment_amount), 2),
             round(float(total_value), 2)),
        )
        conn.commit()
    finally:
        conn.close()


def load_recent_records(user_slug: str, limit: int = 5) -> List[dict[str, Any]]:
    """Load the most recent portfolio generation records."""
    user_id = get_user_id(user_slug)
    if user_id is None:
        return []

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, strategies, investment_amount, total_portfolio_value
            FROM portfolio_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        result: List[dict[str, Any]] = []
        for row in reversed(rows):  # reverse to get chronological order
            result.append({
                "date": row[0],
                "strategies": row[1],
                "investment_amount": float(row[2]),
                "total_portfolio_value": float(row[3]),
            })
        return result
    finally:
        conn.close()


def _normalize_trend_dates(conn: Any, user_id: int) -> None:
    """
    One-time cleanup: collapse old timestamp-format entries into date-only entries.
    Keeps the most recent (last by sort order) value for each calendar day.
    No-op when all entries are already date-only.
    """
    rows = conn.execute(
        "SELECT date, total_portfolio_value FROM portfolio_daily_trend WHERE user_id = ? ORDER BY date ASC",
        (user_id,),
    ).fetchall()

    # Check if normalization is needed
    needs_norm = any(len(str(r[0])) > 10 for r in rows)
    if not needs_norm:
        return

    # Keep the last value per calendar day (rows are sorted ASC, so last wins)
    last_val: dict[str, float] = {}
    for raw_date, value in rows:
        day = str(raw_date)[:10]
        last_val[day] = float(value)

    # Rewrite the table for this user
    conn.execute("DELETE FROM portfolio_daily_trend WHERE user_id = ?", (user_id,))
    for day, value in last_val.items():
        conn.execute(
            "INSERT INTO portfolio_daily_trend (user_id, date, total_portfolio_value) VALUES (?, ?, ?)",
            (user_id, day, value),
        )


def upsert_daily_portfolio_value(
    user_slug: str, total_usd: float, *, day: Optional[date] = None
) -> None:
    """Insert or update today's portfolio value. Normalizes dates to YYYY-MM-DD on every call."""
    user_id = get_user_id(user_slug)
    if user_id is None:
        return

    day_str = (day or date.today()).isoformat()  # Always YYYY-MM-DD
    total_rounded = round(float(total_usd), 2)

    conn = get_db()
    try:
        # Normalize any old timestamp-format entries first
        _normalize_trend_dates(conn, user_id)

        conn.execute(
            """
            INSERT OR REPLACE INTO portfolio_daily_trend (user_id, date, total_portfolio_value)
            VALUES (?, ?, ?)
            """,
            (user_id, day_str, total_rounded),
        )
        conn.commit()
    finally:
        conn.close()


def load_daily_trend(user_slug: str, limit: int = 30) -> List[dict[str, Any]]:
    """Load the daily portfolio value trend."""
    user_id = get_user_id(user_slug)
    if user_id is None:
        return []

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, total_portfolio_value
            FROM portfolio_daily_trend
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        result: List[dict[str, Any]] = []
        for row in reversed(rows):  # reverse to get chronological order
            result.append({
                "date": row[0],
                "total_portfolio_value": float(row[1]),
            })
        return result
    finally:
        conn.close()


def save_current_holdings(
    user_slug: str,
    strategies: Iterable[str],
    investment_amount: float,
    holdings: List[Tuple],
    *,
    dollar_per_ticker: dict[str, float] | float,
) -> None:
    """Save the current portfolio holdings for daily re-pricing.

    Holdings are stored as quads [ticker, shares, allocation, purchase_price] in JSON.
    dollar_per_ticker (dict) is stored within holdings allocations; REAL column is 0.0 placeholder.
    """
    user_id = get_user_id(user_slug)
    if user_id is None:
        return

    from datetime import datetime
    saved_at = datetime.now().isoformat(timespec="seconds")
    strategies_json = json.dumps(list(strategies))
    # Store holdings as quads: [ticker, shares, allocation, purchase_price]
    rows = []
    for item in holdings:
        t, s, a = str(item[0]), float(item[1]), float(item[2])
        px = float(item[3]) if len(item) >= 4 else 0.0
        rows.append([t, s, a, px])
    holdings_json = json.dumps(rows)

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO current_holdings
            (user_id, saved_at, strategies, investment_amount, dollar_per_ticker, holdings)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                saved_at,
                strategies_json,
                round(float(investment_amount), 2),
                0.0,  # Placeholder: allocations stored in holdings triplets
                holdings_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_current_holdings(user_slug: str) -> Optional[dict[str, Any]]:
    """Load the currently saved holdings for a user.

    Handles both old format (2-element holdings, float dollar_per_ticker) and
    new format (3-element holdings with allocation, reconstructs dict dollar_per_ticker).
    """
    user_id = get_user_id(user_slug)
    if user_id is None:
        return None

    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT saved_at, strategies, investment_amount, dollar_per_ticker, holdings
            FROM current_holdings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        holdings_list = json.loads(row[4])

        # Reconstruct dollar_per_ticker dict from holdings (3- or 4-element new format)
        # or use REAL column for old 2-element format
        if holdings_list and len(holdings_list[0]) >= 3:
            dollar_per_ticker = {str(h[0]): float(h[2]) for h in holdings_list}
        else:
            dollar_per_ticker = float(row[3]) if row[3] else None

        return {
            "saved_at": row[0],
            "strategies": json.loads(row[1]),
            "investment_amount": float(row[2]),
            "dollar_per_ticker": dollar_per_ticker,
            "holdings": holdings_list,
        }
    finally:
        conn.close()


def backfill_trend_from_holdings(
    user_slug: str,
    holdings: List[Tuple],
    days: int = 14,
) -> int:
    """
    Backfill portfolio_daily_trend with real Yahoo Finance historical prices.

    For each trading day in the past `days` calendar days, computes what the
    given holdings would have been worth using actual closing prices.
    Returns the number of rows inserted.
    """
    from core.backfill import fetch_historical_values

    user_id = get_user_id(user_slug)
    if user_id is None:
        return 0

    # Build (ticker, shares) pairs — works with 2-, 3-, or 4-element holdings
    pairs = [(str(h[0]), float(h[1])) for h in holdings if len(h) >= 2]
    if not pairs:
        return 0

    historical = fetch_historical_values(pairs, days=days)
    if not historical:
        return 0

    conn = get_db()
    inserted = 0
    try:
        # Clean up old timestamp-format entries first
        _normalize_trend_dates(conn, user_id)
        for date_str, value in historical:
            conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_daily_trend
                (user_id, date, total_portfolio_value)
                VALUES (?, ?, ?)
                """,
                (user_id, date_str, value),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()

    return inserted


def clear_current_holdings(user_slug: str) -> None:
    """Clear the currently saved holdings for a user."""
    user_id = get_user_id(user_slug)
    if user_id is None:
        return

    conn = get_db()
    try:
        conn.execute("DELETE FROM current_holdings WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
