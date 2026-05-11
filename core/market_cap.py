"""
core/market_cap.py — Market cap fetching with caching, rate limiting, and fallback.

Provides market-cap weighted allocation computation with:
- TTL caching for market caps (1 hour: they change slowly)
- Rate-limit sharing with core/quotes (same global 250ms enforcement)
- Fallback to equal-weight when market cap data unavailable
- Thread-safe module-level state matching core/quotes pattern
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import yfinance as yf

from core.quotes import _rate_limited_sleep
from core.strategies import STRATEGY_TICKERS

# Module-level constants
MARKET_CAP_CACHE_TTL = 3600  # 1 hour (market caps change slowly)

# Thread-safe cache state (mirrors core/quotes pattern)
_cap_lock = threading.Lock()
_cap_cache: Dict[str, Tuple[float, float]] = {}  # ticker -> (market_cap, monotonic_time)
_stale_cap_cache: Dict[str, float] = {}  # ticker -> last_known_cap (never expires)


def _fetch_market_cap(ticker: str) -> Optional[float]:
    """
    Fetch market cap from yfinance via two-tier fallback (info → fast_info).
    Returns market cap value or None if unavailable.
    """
    try:
        t = yf.Ticker(ticker)

        # 1) Primary: full info blob
        try:
            info = getattr(t, "info", {}) or {}
            if isinstance(info, dict) and info:
                cap = info.get("marketCap")
                if cap is not None:
                    val = float(cap)
                    if val > 0:
                        return val
        except Exception:
            pass

        # 2) Lightweight fast_info dict
        try:
            fi = getattr(t, "fast_info", None)
            cap = getattr(fi, "market_cap", None) if fi is not None else None
            if cap is not None:
                val = float(cap)
                if val > 0:
                    return val
        except Exception:
            pass

        return None
    except Exception:
        return None


def _get_cached_cap(ticker: str) -> Optional[float]:
    """Returns cached market cap if within TTL, else None. Fast path (no network)."""
    with _cap_lock:
        if ticker in _cap_cache:
            cap, inserted_time = _cap_cache[ticker]
            elapsed = time.monotonic() - inserted_time
            if elapsed < MARKET_CAP_CACHE_TTL:
                return cap
    return None


def _set_cap_cache(ticker: str, cap: float) -> None:
    """Write to both TTL cache and stale fallback cache."""
    with _cap_lock:
        _cap_cache[ticker] = (cap, time.monotonic())
        _stale_cap_cache[ticker] = cap


def _get_stale_cap(ticker: str) -> Optional[float]:
    """Returns last known market cap, or None if no entry exists."""
    with _cap_lock:
        return _stale_cap_cache.get(ticker)


def get_market_cap(ticker: str) -> Optional[float]:
    """
    Main public function: fetch market cap with caching, rate limiting, and stale fallback.

    Order:
    1. Check cache (TTL) — return immediately if fresh (no network, no rate-limit)
    2. Rate-limit enforcement (250ms global minimum, shared with core/quotes)
    3. Fetch live from yfinance
    4. Stale fallback (return last known cap if available)
    5. Total failure (return None)
    """
    # Step 1: Fast cache hit (no network, no rate-limit)
    cached = _get_cached_cap(ticker)
    if cached is not None:
        return cached

    # Step 2: Rate-limit enforcement (shared with core/quotes)
    _rate_limited_sleep()

    # Step 3: Fetch live
    cap = _fetch_market_cap(ticker)
    if cap is not None:
        _set_cap_cache(ticker, cap)
        return cap

    # Step 4: Stale fallback
    stale = _get_stale_cap(ticker)
    if stale is not None:
        return stale

    # Step 5: Total failure
    return None


def _allocate_by_strategy(
    tickers: Sequence[str],
    strategies: Sequence[str],
    investment_usd: float
) -> Dict[str, float]:
    """
    Allocate proportionally by strategy: divide budget by strategy count,
    then split each strategy's budget evenly among its tickers.
    """
    allocations: Dict[str, float] = {}

    if not strategies:
        # Fallback to equal-weight if no strategies provided
        per_ticker = investment_usd / len(tickers) if tickers else 0.0
        for ticker in tickers:
            allocations[ticker] = per_ticker
        return allocations

    # Budget per strategy
    budget_per_strategy = investment_usd / len(strategies)

    # For each strategy, count how many unique tickers belong to it (from our ticker list)
    for strategy in strategies:
        strategy_tickers = STRATEGY_TICKERS.get(strategy, [])
        tickers_in_strategy = [t for t in strategy_tickers if t in tickers]

        if not tickers_in_strategy:
            continue

        # Split strategy budget evenly among its tickers
        per_ticker_in_strategy = budget_per_strategy / len(tickers_in_strategy)
        for ticker in tickers_in_strategy:
            allocations[ticker] = allocations.get(ticker, 0.0) + per_ticker_in_strategy

    return allocations


def compute_allocations(
    tickers: Sequence[str],
    investment_usd: float,
    *,
    strategies: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, float], list[str]]:
    """
    Compute per-ticker dollar allocations weighted by market cap.

    Fallback to strategy-level allocation for tickers with unavailable market cap data.
    Strategy-level fallback: divide budget by # strategies, allocate equally within each strategy.

    Args:
        tickers: List of ticker symbols
        investment_usd: Total lump sum to allocate
        strategies: List of strategy names (used for fallback allocation)

    Returns:
        (allocations_dict, warnings_list) where:
        - allocations_dict[ticker] = dollar allocation for that ticker
        - warnings_list contains fallback messages
    """
    if not tickers:
        return {}, []

    warnings = []
    allocations = {}

    # Fetch market caps for all tickers
    caps = {}
    for ticker in tickers:
        cap = get_market_cap(ticker)
        if cap is not None:
            caps[ticker] = cap

    # Separate tickers by cap availability
    caps_known = {t: caps[t] for t in tickers if t in caps}
    caps_missing = [t for t in tickers if t not in caps]

    # Case 1: All tickers have market cap data — full market-cap weighting
    if not caps_missing:
        total_cap = sum(caps_known.values())
        if total_cap > 0:
            for ticker in tickers:
                allocations[ticker] = (caps[ticker] / total_cap) * investment_usd
        else:
            # Shouldn't happen but fallback to strategy-level allocation
            allocations = _allocate_by_strategy(tickers, strategies or [], investment_usd)
        return allocations, warnings

    # Case 2: All tickers missing market cap data — use strategy-level allocation
    if not caps_known:
        allocations = _allocate_by_strategy(tickers, strategies or [], investment_usd)
        warnings.append(
            f"Used strategy-level allocation for all {len(tickers)} tickers: "
            "market cap data unavailable"
        )
        return allocations, warnings

    # Case 3: Some caps known, some missing — market-cap weight known tickers,
    # strategy-level allocation for missing tickers
    # First, allocate to known tickers by market cap
    total_cap_known = sum(caps_known.values())
    budget_for_known = investment_usd * (len(caps_known) / len(tickers))  # proportional budget

    if total_cap_known > 0:
        for ticker in caps_known:
            allocations[ticker] = (caps_known[ticker] / total_cap_known) * budget_for_known
    else:
        # Shouldn't happen; fallback to strategy-level
        allocations = _allocate_by_strategy(tickers, strategies or [], investment_usd)
        missing_names = ", ".join(caps_missing)
        warnings.append(
            f"Used strategy-level allocation for missing caps ({missing_names}); "
            "all tickers allocated by strategy"
        )
        return allocations, warnings

    # For missing tickers, use strategy-level allocation with remaining budget
    budget_for_missing = investment_usd - sum(allocations.values())
    missing_strategy_allocs = _allocate_by_strategy(caps_missing, strategies or [], budget_for_missing)
    allocations.update(missing_strategy_allocs)

    missing_names = ", ".join(caps_missing)
    warnings.append(
        f"Used strategy-level allocation for missing caps ({missing_names}); "
        "other tickers weighted by market cap"
    )

    return allocations, warnings


def clear_cache() -> None:
    """Clear both TTL and stale caches. Primarily for testing."""
    with _cap_lock:
        _cap_cache.clear()
        _stale_cap_cache.clear()


def cap_cache_stats() -> Dict[str, Any]:
    """Return market cap cache statistics for debugging and monitoring."""
    with _cap_lock:
        return {
            "cached_tickers": len(_cap_cache),
            "stale_tickers": len(_stale_cap_cache),
            "cache_ttl_seconds": MARKET_CAP_CACHE_TTL,
        }
