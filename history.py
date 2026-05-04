"""
history.py — Append and load portfolio simulation history from CSV.

Each time the user generates a portfolio, we append one row so the app can show
the most recent suggestion runs as a simple "5‑record portfolio trend".
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List


# Columns stored in portfolio_history.csv
FIELDNAMES = [
    "date",
    "strategies",
    "investment_amount",
    "total_portfolio_value",
]


def _csv_path() -> Path:
    """Resolve CSV next to this package regardless of cwd."""
    return Path(__file__).resolve().parent / "portfolio_history.csv"


def ensure_history_file() -> None:
    """Create portfolio_history.csv with header if missing."""
    path = _csv_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def append_record(strategies: Iterable[str], investment_amount: float, total_value: float) -> Path:
    """
    Append one history row using today's ISO date plus selected metadata.

    Strategies are joined with " + " so a single CSV cell stays readable.
    """
    ensure_history_file()
    path = _csv_path()
    row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategies": " + ".join(sorted(strategies)),
        "investment_amount": round(float(investment_amount), 2),
        "total_portfolio_value": round(float(total_value), 2),
    }
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)
    return path


def load_recent_records(limit: int = 5) -> List[dict[str, Any]]:
    """
    Load the newest `limit` rows from CSV (by file row order).

    Empty or missing files return [].
    """
    path = _csv_path()
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    tail = rows[-limit:] if limit > 0 else []
    parsed: List[dict[str, Any]] = []
    for r in tail:
        parsed.append(
            {
                "date": r.get("date", ""),
                "strategies": r.get("strategies", ""),
                "investment_amount": float(r.get("investment_amount", 0) or 0),
                "total_portfolio_value": float(r.get("total_portfolio_value", 0) or 0),
            }
        )
    return parsed


