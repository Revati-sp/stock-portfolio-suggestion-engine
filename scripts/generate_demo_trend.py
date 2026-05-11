#!/usr/bin/env python3
"""
generate_demo_trend.py — Populate portfolio_daily_trend with synthetic 14-day demo data.

Creates realistic historical portfolio values with ±2-3% daily variations
simulating natural market movements. Use this to populate the trend chart
immediately after migration.

Usage:
    python scripts/generate_demo_trend.py [--username demo] [--days 14] [--base-value 10000]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from database.connection import get_db, get_user_id
import random


def generate_demo_trend(
    username: str,
    days: int = 14,
    base_value: float = 10000.0,
    daily_volatility: float = 0.025
) -> None:
    """
    Generate synthetic daily portfolio values with realistic market movements.

    Args:
        username: Target user (must exist in database)
        days: Number of historical days to generate (default 14)
        base_value: Starting portfolio value (default 10000)
        daily_volatility: Daily change magnitude (default ±2.5%)
    """
    user_id = get_user_id(username)
    if user_id is None:
        print(f"❌ User '{username}' not found in database")
        return

    conn = get_db()
    cursor = conn.cursor()

    # Generate dates going backwards from today
    today = datetime.now().date()
    start_date = today - timedelta(days=days - 1)

    # Start with base value and apply daily random walk
    current_value = base_value
    values_by_date = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)

        # Random daily change: ±daily_volatility (default ±2.5%)
        daily_return = random.gauss(0, daily_volatility)  # Realistic normal distribution
        current_value *= (1 + daily_return)
        current_value = max(current_value, base_value * 0.8)  # Floor at 80% of base

        values_by_date.append((current_date.isoformat(), round(current_value, 2)))

    # Insert into database
    inserted = 0
    for date_str, value in values_by_date:
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

    print(f"✅ Generated {inserted} daily trend entries for '{username}'")
    print(f"   Date range: {values_by_date[0][0]} → {values_by_date[-1][0]}")
    print(f"   Value range: ${min(v[1] for v in values_by_date):.2f} → ${max(v[1] for v in values_by_date):.2f}")
    print(f"   Base value: ${base_value:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic 14-day portfolio trend data for demo purposes."
    )
    parser.add_argument(
        "--username",
        default="demo",
        help="Username to populate trend for (default: demo)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of historical days to generate (default: 14)"
    )
    parser.add_argument(
        "--base-value",
        type=float,
        default=10000.0,
        help="Starting portfolio value (default: 10000)"
    )
    parser.add_argument(
        "--volatility",
        type=float,
        default=0.025,
        help="Daily volatility as decimal (default: 0.025 = ±2.5%)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Portfolio Trend Demo Data Generator")
    print("=" * 60)
    print(f"Username: {args.username}")
    print(f"Days: {args.days}")
    print(f"Base value: ${args.base_value:.2f}")
    print(f"Daily volatility: ±{args.volatility * 100:.1f}%")
    print()

    generate_demo_trend(
        username=args.username,
        days=args.days,
        base_value=args.base_value,
        daily_volatility=args.volatility
    )


if __name__ == "__main__":
    main()
