"""
core/quotes.py — Reliable quote fetching with caching, rate limiting, retries, and offline fallback.

Replaces the yfinance fetch logic from core/portfolio.py with a robust layer that:
- Caches prices with TTL (15 min default) to avoid repeated network calls
- Rate-limits yfinance calls (250ms minimum between calls globally)
- Retries with exponential backoff on transient network failures
- Falls back to stale prices when offline or rate-limited
- Maintains thread-safe module-level state for Streamlit reruns and FastAPI concurrent requests
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Sequence, Tuple

import yfinance as yf

# Module-level constants (monkey-patchable for testing)
CACHE_TTL_SECONDS = 900  # 15 minutes
RATE_LIMIT_INTERVAL = 0.25  # 250 ms minimum between yfinance HTTP calls
RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = [1.0, 2.0, 4.0]

# Thread-safe cache state
_cache_lock = threading.Lock()
_price_cache: Dict[str, Tuple[float, float]] = {}  # ticker -> (price, monotonic_time)
_stale_cache: Dict[str, float] = {}  # ticker -> last_known_price (persists after TTL)

# Thread-safe rate limiter state
_rate_lock = threading.Lock()
_last_call_time = 0.0


class PriceQuote:
    """Quote result with price and optional error message. Moved from core/portfolio."""

    def __init__(self, price: Optional[float], error_message: Optional[str] = None):
        self.price = price
        self.error_message = error_message

    @property
    def ok(self) -> bool:
        return self.price is not None and self.price > 0

    def __repr__(self) -> str:
        return f"PriceQuote(price={self.price}, error={self.error_message})"


def _extract_price(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    """
    Try several common Yahoo fields; return (price_or_none, error_or_none).

    Avoids brittle reliance on any single Yahoo JSON key changing.
    Moved verbatim from core/portfolio.py.
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


def _get_cached(ticker: str) -> Optional[PriceQuote]:
    """Returns cached PriceQuote if within TTL, else None. Fast path (no network)."""
    with _cache_lock:
        if ticker in _price_cache:
            price, inserted_time = _price_cache[ticker]
            elapsed = time.monotonic() - inserted_time
            if elapsed < CACHE_TTL_SECONDS:
                return PriceQuote(price=price)
    return None


def _set_cache(ticker: str, price: float) -> None:
    """Write to both TTL cache and stale fallback cache."""
    with _cache_lock:
        _price_cache[ticker] = (price, time.monotonic())
        _stale_cache[ticker] = price


def _get_stale(ticker: str) -> Optional[PriceQuote]:
    """Returns last known price with stale warning, or None if no entry exists."""
    with _cache_lock:
        if ticker in _stale_cache:
            price = _stale_cache[ticker]
            return PriceQuote(
                price=price,
                error_message="Stale price (live fetch failed): using last known price"
            )
    return None


def _rate_limited_sleep() -> None:
    """
    Enforce RATE_LIMIT_INTERVAL as a global minimum between yfinance HTTP calls.

    Acquires _rate_lock and sleeps for the remainder of the interval.
    Thread-safe: concurrent calls will serialize at this lock.
    """
    with _rate_lock:
        global _last_call_time
        elapsed = time.monotonic() - _last_call_time
        if elapsed < RATE_LIMIT_INTERVAL:
            time.sleep(RATE_LIMIT_INTERVAL - elapsed)
        _last_call_time = time.monotonic()


def _fetch_live(ticker: str) -> PriceQuote:
    """
    Fetch price from yfinance with three-tier fallback (info → fast_info → history).
    Does NOT write to cache — that responsibility belongs to fetch_ticker_price.
    Moved verbatim from core/portfolio.py.
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


def fetch_ticker_price(ticker: str) -> PriceQuote:
    """
    Main public function: fetch price with caching, rate limiting, retries, and stale fallback.

    Order:
    1. Check cache (TTL) — return immediately if fresh (no network, no rate-limit)
    2. Rate-limit enforcement (250ms global minimum)
    3. Retry loop (3 attempts with exponential backoff)
    4. Stale fallback (return last known price if available)
    5. Total failure (return error)
    """
    # Step 1: Fast cache hit (no network, no rate-limit)
    cached = _get_cached(ticker)
    if cached is not None:
        return cached

    # Step 2: Rate-limit enforcement
    _rate_limited_sleep()

    # Step 3: Retry loop (3 attempts with exponential backoff)
    for attempt in range(RETRY_COUNT):
        try:
            pq = _fetch_live(ticker)
            if pq.ok:
                _set_cache(ticker, pq.price)
                return pq
            # Non-ok but no exception (e.g., empty history) — data absence, don't retry
            break
        except Exception:
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                _rate_limited_sleep()  # Enforce spacing before retry

    # Step 4: Stale fallback
    stale = _get_stale(ticker)
    if stale is not None:
        return stale

    # Step 5: Total failure (no cached price, all retries exhausted)
    return PriceQuote(
        price=None,
        error_message="All fetch attempts failed; no cached price available"
    )


def fetch_previous_close(ticker: str) -> Optional[float]:
    """
    Return the most recent previous-day closing price for a ticker.

    Used to compute day's gain/loss (current price vs yesterday's close).
    Tries info["regularMarketPreviousClose"] first, then history fallback.
    Not cached — only called once per portfolio generation.
    """
    _rate_limited_sleep()
    try:
        t = yf.Ticker(ticker)
        info = getattr(t, "info", {}) or {}
        prev = info.get("regularMarketPreviousClose")
        if prev is not None:
            val = float(prev)
            if val > 0:
                return val
        # History fallback: second-to-last close
        hist = t.history(period="5d", auto_adjust=False)
        if hist is not None and len(hist) >= 2:
            val = float(hist["Close"].iloc[-2])
            if val > 0:
                return val
    except Exception:
        pass
    return None


def warm_cache(tickers: Sequence[str]) -> Dict[str, PriceQuote]:
    """
    Preload cache with prices for all specified tickers.
    Rate-limiter is enforced between calls, spacing them to 250ms intervals.
    Useful for API startup or eager loading.
    """
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_ticker_price(ticker)
    return results


def clear_cache() -> None:
    """Clear both TTL and stale caches. Primarily for testing."""
    with _cache_lock:
        _price_cache.clear()
        _stale_cache.clear()


def cache_stats() -> Dict[str, Any]:
    """Return cache statistics for debugging and monitoring."""
    with _cache_lock:
        return {
            "cached_tickers": len(_price_cache),
            "stale_tickers": len(_stale_cache),
            "cache_ttl_seconds": CACHE_TTL_SECONDS,
            "rate_limit_interval": RATE_LIMIT_INTERVAL,
        }
