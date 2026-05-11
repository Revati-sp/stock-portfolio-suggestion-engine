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

from core.strategies import STRATEGY_TICKERS, ticker_to_strategy
from core.quotes import _extract_price, fetch_ticker_price, fetch_previous_close, PriceQuote
from core.market_cap import compute_allocations






def extract_priced_holdings(df: pd.DataFrame) -> List[Tuple[str, float, float, float]]:
    """Ticker + shares + allocation + purchase_price quads for successfully priced rows."""
    rows: List[Tuple[str, float, float, float]] = []
    for _, row in df.iterrows():
        sym = row.get("Ticker")
        sh = row.get("Shares")
        alloc = row.get("Allocation (USD)")
        px = row.get("Purchase Price (USD)")
        if sym is None or sh is None or (isinstance(sh, float) and pd.isna(sh)):
            continue
        alloc = 0.0 if alloc is None or (isinstance(alloc, float) and pd.isna(alloc)) else float(alloc)
        px = 0.0 if px is None or (isinstance(px, float) and pd.isna(px)) else float(px)
        rows.append((str(sym), float(sh), alloc, px))
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
        elif pq.error_message:
            warnings.append(f"{ticker}: {pq.error_message}")
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
    # per_raw can be dict (new format) or float (old format)
    if isinstance(per_raw, dict):
        per = inv / max(len(holdings_raw), 1)  # Fallback; will use per_raw lookup for new format
    elif per_raw is not None:
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
        alloc = float(item[2]) if len(item) >= 3 else per
        # Purchase price stored at generation time — enables real gain/loss on re-pricing
        purchase_px = float(item[3]) if len(item) >= 4 and item[3] else None
        pq = qfetch(sym)
        if not pq.ok:
            msg = pq.error_message or "Unknown pricing error"
            warnings.append(f"{sym}: {msg}")
            rows.append(
                {
                    "Ticker": sym,
                    "Strategy": strat_map.get(sym, ""),
                    "Allocation (USD)": round(alloc, 2),
                    "Purchase Price (USD)": purchase_px,
                    "Current Price (USD)": None,
                    "Shares": round(shares, 6),
                    "Current Value (USD)": None,
                    "Day Gain/Loss (USD)": None,
                    "Total Gain/Loss (USD)": None,
                }
            )
            continue
        elif pq.error_message:
            warnings.append(f"{sym}: {pq.error_message}")
        price = float(pq.price) if pq.price is not None else 0.0
        curr_val = shares * price

        # Total gain/loss: since inception (purchase price vs current)
        if purchase_px is not None and purchase_px > 0:
            total_gl = round(curr_val - purchase_px * shares, 2)
        else:
            total_gl = round(curr_val - alloc, 2)

        # Day's gain/loss: current price vs previous close
        prev_close = fetch_previous_close(sym)
        if prev_close is not None and prev_close > 0 and shares > 0:
            day_gl = round((price - prev_close) * shares, 2)
        else:
            day_gl = None

        rows.append(
            {
                "Ticker": sym,
                "Strategy": strat_map.get(sym, ""),
                "Allocation (USD)": round(alloc, 2),
                "Purchase Price (USD)": purchase_px,
                "Current Price (USD)": round(price, 4),
                "Shares": round(shares, 6),
                "Current Value (USD)": round(curr_val, 2),
                "Day Gain/Loss (USD)": day_gl,
                "Total Gain/Loss (USD)": total_gl,
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

    strat_map = ticker_to_strategy(selected_strategies)
    warnings: List[str] = []

    # Compute market-cap weighted allocations (fallback to strategy-level for missing caps)
    allocations, alloc_warnings = compute_allocations(
        tickers, investment_usd, strategies=selected_strategies
    )
    warnings.extend(alloc_warnings)

    rows: List[Dict[str, Any]] = []
    for sym in tickers:
        per_asset = allocations[sym]
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
        elif pq.error_message:
            warnings.append(f"{sym}: {pq.error_message}")

        price = pq.price if pq.price is not None else 0.0
        shares = per_asset / price if price > 0 else 0.0
        curr_val = shares * price

        # Day's gain/loss: compare current price against previous trading day's close
        prev_close = fetch_previous_close(sym)
        if prev_close is not None and prev_close > 0 and shares > 0:
            day_gl = round((price - prev_close) * shares, 2)
        else:
            day_gl = None

        rows.append(
            {
                "Ticker": sym,
                "Strategy": strat_map.get(sym, ""),
                "Allocation (USD)": round(per_asset, 2),
                "Purchase Price (USD)": round(price, 4),
                "Current Price (USD)": round(price, 4),
                "Shares": round(shares, 6),
                "Current Value (USD)": round(curr_val, 2),
                "Day Gain/Loss (USD)": day_gl,
                "Total Gain/Loss (USD)": 0.0,  # 0 at generation; updates on reload
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
