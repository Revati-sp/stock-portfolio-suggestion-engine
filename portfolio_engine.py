"""
portfolio_engine.py — Core calculations and Yahoo Finance quotes.

Splits the user's lump sum evenly across unique tickers from chosen strategies,
sizes fractional shares from live-ish quotes, and reports gain/loss vs each slice
of invested dollars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import yfinance as yf

from data import STRATEGY_TICKERS, ticker_to_strategy


@dataclass
class PriceQuote:
    """Single ticker's fetched price outcome."""

    price: Optional[float]
    error_message: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.price is not None and self.price > 0


def _extract_price(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    """
    Try several common Yahoo fields; return (price_or_none, error_or_none).

    Avoids brittle reliance on any single Yahoo JSON key changing.
    """
    candidates = [
        ("regularMarketPrice", payload.get("regularMarketPrice")),
        ("previousClose", payload.get("regularMarketPreviousClose")),
        ("postMarketPrice", payload.get("postMarketPrice")),
        ("preMarketPrice", payload.get("preMarketPrice")),
    ]
    for label, raw in candidates:
        try:
            if raw is None:
                continue
            val = float(raw)
            if val > 0:
                return val, None
        except (TypeError, ValueError):
            continue
    return None, "No usable price fields in ticker info"


def fetch_ticker_price(ticker: str) -> PriceQuote:
    """
    Latest available price via yfinance, with graceful fallbacks.

    Order: ticker.info shortcuts -> fast_info -> recent daily close history.
    """
    t = yf.Ticker(ticker)
    # 1) Primary: full info blob (often has regularMarketPrice)
    try:
        info = getattr(t, "info", {}) or {}
        if isinstance(info, dict) and info:
            px, _err = _extract_price(info)
            if px is not None:
                return PriceQuote(price=px, error_message=None)
    except Exception:
        pass

    # 2) Lightweight fast_info dict (fewer keys, quicker)
    try:
        fi = getattr(t, "fast_info", None)
        last = getattr(fi, "last_price", None) if fi is not None else None
        if last is not None:
            val = float(last)
            if val > 0:
                return PriceQuote(price=val, error_message=None)
    except Exception:
        pass

    # 3) Last resort: closing price from compact history window
    try:
        hist = t.history(period="5d", auto_adjust=False)
        if hist is None or hist.empty:
            return PriceQuote(
                price=None,
                error_message="Empty price history returned by Yahoo Finance",
            )
        close = float(hist["Close"].iloc[-1])
        if close > 0:
            return PriceQuote(price=close, error_message=None)
    except Exception as exc:
        return PriceQuote(price=None, error_message=f"history fallback failed: {exc}")

    return PriceQuote(price=None, error_message="Could not derive a positive price")


def extract_priced_holdings(df: pd.DataFrame) -> List[Tuple[str, float]]:
    """Ticker + share pairs for rows that were successfully priced."""
    rows: List[Tuple[str, float]] = []
    for _, row in df.iterrows():
        sym = row.get("Ticker")
        sh = row.get("Shares")
        if sym is None or sh is None or (isinstance(sh, float) and pd.isna(sh)):
            continue
        rows.append((str(sym), float(sh)))
    return rows


def mark_to_market_holdings(
    holdings: Sequence[Tuple[str, float]],
    *,
    quote_fn: Optional[Callable[[str], PriceQuote]] = None,
) -> Tuple[float, List[str]]:
    """
    Sum shares × fresh quote for each line; skip missing prices with warnings.

    Returns (total_usd, warning_messages).
    """
    qfetch = quote_fn or fetch_ticker_price
    warnings: List[str] = []
    total = 0.0
    for ticker, shares in holdings:
        pq = qfetch(ticker)
        if not pq.ok or pq.price is None:
            msg = pq.error_message or "no price"
            warnings.append(f"{ticker}: {msg}")
            continue
        total += float(shares) * float(pq.price)
    return round(total, 2), warnings


def build_portfolio_table_from_saved(
    payload: Dict[str, Any],
    *,
    quote_fn: Optional[Callable[[str], PriceQuote]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Rebuild the same table shape as `build_portfolio_table` from `current_holdings.json`
    using fresh quotes. `dollar_per_ticker` is optional in older JSON (fallback heuristic).
    """
    qfetch = quote_fn or fetch_ticker_price
    strategies = list(payload.get("strategies") or [])
    holdings_raw = payload.get("holdings") or []
    inv = float(payload.get("investment_amount") or 0.0)
    per_raw = payload.get("dollar_per_ticker")
    if per_raw is not None:
        per = float(per_raw)
    else:
        per = inv / max(len(holdings_raw), 1)

    strat_map = ticker_to_strategy(strategies)
    warnings: List[str] = []
    rows: List[Dict[str, Any]] = []

    for item in holdings_raw:
        if not item or len(item) < 2:
            continue
        sym, shares = str(item[0]), float(item[1])
        pq = qfetch(sym)
        if not pq.ok:
            msg = pq.error_message or "Unknown pricing error"
            warnings.append(f"{sym}: {msg}")
            rows.append(
                {
                    "Ticker": sym,
                    "Strategy": strat_map.get(sym, ""),
                    "Allocation (USD)": round(per, 2),
                    "Current Price (USD)": None,
                    "Shares": round(shares, 6),
                    "Current Value (USD)": None,
                    "Gain/Loss (USD)": None,
                }
            )
            continue
        price = float(pq.price) if pq.price is not None else 0.0
        curr_val = shares * price
        gain_loss = curr_val - per
        rows.append(
            {
                "Ticker": sym,
                "Strategy": strat_map.get(sym, ""),
                "Allocation (USD)": round(per, 2),
                "Current Price (USD)": round(price, 4),
                "Shares": round(shares, 6),
                "Current Value (USD)": round(curr_val, 2),
                "Gain/Loss (USD)": round(gain_loss, 2),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(by="Ticker", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df, warnings


def unique_tickers_for_strategies(selected: Sequence[str]) -> List[str]:
    """Preserve original strategy order while de-duplicating tickers."""
    seen = set()
    ordered: List[str] = []
    for strat in selected:
        for sym in STRATEGY_TICKERS[strat]:
            if sym not in seen:
                seen.add(sym)
                ordered.append(sym)
    return ordered


def build_portfolio_table(
    selected_strategies: Sequence[str],
    investment_usd: float,
    *,
    quote_fn: Optional[Callable[[str], PriceQuote]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Main engine: allocations, fractional shares, mark-to-market, warnings.

    Returns (table DataFrame sorted by ticker, warning strings for UI).
    """
    qfetch = quote_fn or fetch_ticker_price
    tickers = unique_tickers_for_strategies(selected_strategies)
    n = len(tickers)
    if n == 0:
        return pd.DataFrame(), ["No tickers resolved for chosen strategies"]

    per_asset = investment_usd / float(n)
    strat_map = ticker_to_strategy(selected_strategies)
    warnings: List[str] = []

    rows: List[Dict[str, Any]] = []
    for sym in tickers:
        pq = qfetch(sym)  # Isolate quote lookup so malformed JSON never crashes Streamlit reruns.

        # Yahoo occasionally omits realtime keys; record the failure but keep the ticker row printable.
        if not pq.ok:
            msg = pq.error_message or "Unknown pricing error"
            warnings.append(f"{sym}: {msg}")
            rows.append(
                {
                    "Ticker": sym,
                    "Strategy": strat_map.get(sym, ""),
                    "Allocation (USD)": round(per_asset, 2),
                    "Current Price (USD)": None,
                    "Shares": None,
                    "Current Value (USD)": None,
                    "Gain/Loss (USD)": None,
                }
            )
            continue

        price = pq.price if pq.price is not None else 0.0
        shares = per_asset / price if price > 0 else 0.0
        curr_val = shares * price
        gain_loss = curr_val - per_asset

        rows.append(
            {
                "Ticker": sym,
                "Strategy": strat_map.get(sym, ""),
                "Allocation (USD)": round(per_asset, 2),
                "Current Price (USD)": round(price, 4),
                "Shares": round(shares, 6),
                "Current Value (USD)": round(curr_val, 2),
                "Gain/Loss (USD)": round(gain_loss, 2),
            }
        )

    df = pd.DataFrame(rows)
    df.sort_values(by="Ticker", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df, warnings


def portfolio_totals(df: pd.DataFrame, lump_sum_usd: float) -> Tuple[float, float, float]:
    """
    Portfolio-level rollups suitable for KPI cards.

    Returns (basis_shown_as_invested, marked_value_sum, aggregate_gain_loss):
    - basis uses the simulator lump sum (`lump_sum_usd`) shown as total invested card
    - marked value ignores rows where Yahoo returned no usable quote
    - gain/loss = marked value minus allocation actually placed into priced holdings
      (sums to `lump_sum_usd` whenever every ticker succeeds)
    """
    basis = round(float(lump_sum_usd), 2)

    vals = pd.to_numeric(df["Current Value (USD)"], errors="coerce")
    alloc = pd.to_numeric(df["Allocation (USD)"], errors="coerce")
    priced = vals.notna()

    marked = round(float(vals[priced].sum()), 2)
    placed = round(float(alloc[priced].sum()), 2)
    total_gain_loss = round(marked - placed, 2)
    return basis, marked, total_gain_loss
