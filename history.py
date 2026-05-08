"""
history.py — Append and load portfolio simulation history from CSV.

Per user, data lives under `user_data/<user_slug>/`:
- portfolio_history.csv — audit log of Generate runs
- portfolio_daily_trend.csv — up to five calendar days of total portfolio value
- current_holdings.json — last priced basket for daily re-marking
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple


# Columns stored in portfolio_history.csv
FIELDNAMES = [
    "date",
    "strategies",
    "investment_amount",
    "total_portfolio_value",
]

DAILY_FIELDNAMES = ["date", "total_portfolio_value"]


def _user_root(user_slug: str) -> Path:
    root = Path(__file__).resolve().parent / "user_data" / user_slug
    root.mkdir(parents=True, exist_ok=True)
    return root


def _csv_path(user_slug: str) -> Path:
    return _user_root(user_slug) / "portfolio_history.csv"


def ensure_history_file(user_slug: str) -> None:
    path = _csv_path(user_slug)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def append_record(
    user_slug: str,
    strategies: Iterable[str],
    investment_amount: float,
    total_value: float,
) -> Path:
    ensure_history_file(user_slug)
    path = _csv_path(user_slug)
    row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategies": " + ".join(sorted(strategies)),
        "investment_amount": round(float(investment_amount), 2),
        "total_portfolio_value": round(float(total_value), 2),
    }
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writerow(row)
    return path


def load_recent_records(user_slug: str, limit: int = 5) -> List[dict[str, Any]]:
    path = _csv_path(user_slug)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
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


def _daily_trend_path(user_slug: str) -> Path:
    return _user_root(user_slug) / "portfolio_daily_trend.csv"


def _holdings_json_path(user_slug: str) -> Path:
    return _user_root(user_slug) / "current_holdings.json"


def ensure_daily_trend_file(user_slug: str) -> None:
    path = _daily_trend_path(user_slug)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=DAILY_FIELDNAMES).writeheader()


def upsert_daily_portfolio_value(
    user_slug: str, total_usd: float, *, day: Optional[date] = None
) -> Path:
    ensure_daily_trend_file(user_slug)
    path = _daily_trend_path(user_slug)
    key = (day or date.today()).isoformat()
    rows: dict[str, float] = {}
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                d = (r.get("date") or "").strip()
                if not d:
                    continue
                try:
                    rows[d] = float(r.get("total_portfolio_value", 0) or 0)
                except ValueError:
                    continue
    rows[key] = round(float(total_usd), 2)
    sorted_days = sorted(rows.keys())[-5:]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DAILY_FIELDNAMES)
        w.writeheader()
        for d in sorted_days:
            w.writerow({"date": d, "total_portfolio_value": rows[d]})
    return path


def load_daily_trend(user_slug: str, limit: int = 5) -> List[dict[str, Any]]:
    path = _daily_trend_path(user_slug)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        raw = list(csv.DictReader(f))
    tail = raw[-limit:] if limit > 0 else []
    out: List[dict[str, Any]] = []
    for r in tail:
        try:
            out.append(
                {
                    "date": r.get("date", ""),
                    "total_portfolio_value": float(r.get("total_portfolio_value", 0) or 0),
                }
            )
        except ValueError:
            continue
    return out


def save_current_holdings(
    user_slug: str,
    strategies: Iterable[str],
    investment_amount: float,
    holdings: List[Tuple[str, float]],
    *,
    dollar_per_ticker: float,
) -> Path:
    path = _holdings_json_path(user_slug)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "strategies": list(strategies),
        "investment_amount": round(float(investment_amount), 2),
        "dollar_per_ticker": round(float(dollar_per_ticker), 2),
        "holdings": [[t, s] for t, s in holdings],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_current_holdings(user_slug: str) -> Optional[dict[str, Any]]:
    path = _holdings_json_path(user_slug)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_current_holdings(user_slug: str) -> None:
    path = _holdings_json_path(user_slug)
    if path.exists():
        path.unlink()
