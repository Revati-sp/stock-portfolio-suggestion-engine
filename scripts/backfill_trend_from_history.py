#!/usr/bin/env python3
"""
backfill_trend_from_history.py — Populate portfolio_daily_trend from actual portfolio_history.

Uses real portfolio generation records from your audit log to backfill the daily trend.
For each day with portfolio generations, uses the latest portfolio value as that day's trend.

Usage:
    python scripts/backfill_trend_from_history.py [--username demo]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from database.connection import get_db, get_user_id


def backfill_trend_from_history(username: str) -> None:
    """
    Extract daily portfolio values from portfolio_history and populate portfolio_daily_trend.

    For each date, takes the LATEST (most recent) portfolio generation value as that day's trend.
    """
    user_id = get_user_id(username)
    if user_id is None:
        print(f"❌ User '{username}' not found in database")
        return

    conn = get_db()
    cursor = conn.cursor()

    # Get all portfolio history records for this user, ordered by date and time
    cursor.execute(
        """
        SELECT date, total_portfolio_value
        FROM portfolio_history
        WHERE user_id = ?
        ORDER BY date DESC, rowid DESC
        """,
        (user_id,)
    )
    records = cursor.fetchall()

    if not records:
        print(f"⚠️  No portfolio history found for user '{username}'")
        conn.close()
        return

    # Group by date and take the latest value for each date
    dates_seen = set()
    inserted = 0

    for date_str, value in records:
        if date_str in dates_seen:
            continue  # Already processed latest value for this date

        dates_seen.add(date_str)

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

    # Get trend stats
    cursor.execute(
        """
        SELECT COUNT(*), MIN(total_portfolio_value), MAX(total_portfolio_value)
        FROM portfolio_daily_trend
        WHERE user_id = ?
        """,
        (user_id,)
    )
    count, min_val, max_val = cursor.fetchone()

    conn.close()

    print(f"✅ Backfilled {inserted} daily trend entries from portfolio_history")
    print(f"   Total trend days: {count}")
    print(f"   Value range: ${min_val:.2f} → ${max_val:.2f}")
    print(f"   Data source: Actual portfolio generation records (audit log)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill portfolio daily trend from actual portfolio history records."
    )
    parser.add_argument(
        "--username",
        default="demo",
        help="Username to backfill trend for (default: demo)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Portfolio Trend Backfill from History")
    print("=" * 60)
    print(f"Username: {args.username}")
    print()

    backfill_trend_from_history(args.username)


if __name__ == "__main__":
    main()
