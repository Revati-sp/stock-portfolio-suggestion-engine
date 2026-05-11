"""
tests/test_quotes.py — Comprehensive tests for quote reliability layer.

Tests cover:
- Cache hits avoiding network
- Cache expiry triggering refetch
- Rate limiter enforcement
- Retry logic with exponential backoff
- Stale fallback when all retries fail
- Total failure when no stale entry exists
- Thread-safe concurrent access
- Warm cache preloading
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import core.quotes as quotes


class TestQuoteCache(unittest.TestCase):
    """Test quote caching and reliability features."""

    def setUp(self):
        """Clear all caches before each test."""
        quotes.clear_cache()
        quotes._last_call_time = 0.0

    def tearDown(self):
        """Clean up after each test."""
        quotes.clear_cache()
        quotes._last_call_time = 0.0

    def test_cache_hit_skips_network(self):
        """
        Second call for same ticker should use cache, not call _fetch_live.
        """
        # Prime the cache with a manual write
        quotes._set_cache("AAPL", 150.0)

        # Mock _fetch_live to track if it's called
        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.return_value = quotes.PriceQuote(price=999.0)

            # First call hits cache
            result1 = quotes.fetch_ticker_price("AAPL")
            self.assertEqual(result1.price, 150.0)

            # _fetch_live should not be called (cache hit)
            mock_fetch.assert_not_called()

            # Second call also hits cache
            result2 = quotes.fetch_ticker_price("AAPL")
            self.assertEqual(result2.price, 150.0)
            mock_fetch.assert_not_called()

    def test_cache_expiry_refetches(self):
        """
        After cache TTL expires, should refetch from live source.
        """
        # Prime cache with old timestamp
        with quotes._cache_lock:
            quotes._price_cache["MSFT"] = (
                200.0,
                time.monotonic() - quotes.CACHE_TTL_SECONDS - 1.0
            )

        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.return_value = quotes.PriceQuote(price=210.0)

            # First call finds cache expired, calls _fetch_live
            result1 = quotes.fetch_ticker_price("MSFT")
            self.assertEqual(result1.price, 210.0)
            mock_fetch.assert_called_once()

    def test_rate_limit_enforces_interval(self):
        """
        Two different tickers should take >= RATE_LIMIT_INTERVAL total.
        """
        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.return_value = quotes.PriceQuote(price=100.0)

            start = time.monotonic()
            quotes.fetch_ticker_price("AAPL")
            quotes.fetch_ticker_price("MSFT")
            elapsed = time.monotonic() - start

            # Should have taken at least RATE_LIMIT_INTERVAL
            # (Note: might be slightly longer due to Python scheduling)
            self.assertGreaterEqual(
                elapsed,
                quotes.RATE_LIMIT_INTERVAL * 0.9,  # Allow 10% tolerance
                f"Expected >= {quotes.RATE_LIMIT_INTERVAL}s, got {elapsed}s"
            )

    def test_retry_on_exception(self):
        """
        Transient exceptions should be retried, eventually succeeding.
        """
        # Patch to fail twice, succeed third time
        call_count = [0]

        def side_effect(ticker):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Network error")
            return quotes.PriceQuote(price=150.0)

        with patch("core.quotes._fetch_live", side_effect=side_effect):
            # Patch sleep to speed up test
            with patch("time.sleep"):
                result = quotes.fetch_ticker_price("AAPL")

        self.assertEqual(result.price, 150.0)
        self.assertEqual(call_count[0], 3)

    def test_stale_fallback_after_all_retries_fail(self):
        """
        When all retries fail, should return stale price with warning.
        """
        # Prime stale cache
        quotes._set_cache("NVDA", 500.0)
        # Expire TTL so it's stale but in fallback cache
        quotes.clear_cache()
        with quotes._cache_lock:
            quotes._stale_cache["NVDA"] = 500.0

        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("Network unavailable")

            with patch("time.sleep"):
                result = quotes.fetch_ticker_price("NVDA")

        self.assertEqual(result.price, 500.0)
        self.assertTrue(result.ok)
        self.assertIn("Stale price", result.error_message)

    def test_total_failure_no_stale(self):
        """
        When no stale cache exists and all fetches fail, should return error.
        """
        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("Network unavailable")

            with patch("time.sleep"):
                result = quotes.fetch_ticker_price("ZZZZ")

        self.assertIsNone(result.price)
        self.assertFalse(result.ok)
        self.assertIn("no cached price available", result.error_message)

    def test_concurrent_thread_safety(self):
        """
        Multiple concurrent threads should serialize at rate-limit without crashes.
        """
        results = []
        exceptions = []

        def fetch_and_store():
            try:
                # Each thread fetches a different ticker to avoid trivial cache hits
                ticker = f"T{threading.current_thread().ident % 1000}"
                result = quotes.fetch_ticker_price(ticker)
                results.append(result)
            except Exception as e:
                exceptions.append(e)

        # Patch _fetch_live at module level for all threads
        with patch("core.quotes._fetch_live") as mock_fetch:
            mock_fetch.return_value = quotes.PriceQuote(price=150.0)

            # Launch 4 concurrent threads
            threads = [threading.Thread(target=fetch_and_store) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # All threads should complete without exception
        self.assertEqual(len(exceptions), 0, f"Exceptions: {exceptions}")
        # All should have gotten a price
        self.assertEqual(len(results), 4)
        for result in results:
            self.assertTrue(result.ok)

    def test_warm_cache_preloads_tickers(self):
        """
        warm_cache should preload all provided tickers into cache.
        """
        tickers = ["AAPL", "MSFT", "NVDA"]

        with patch("core.quotes.fetch_ticker_price") as mock_fetch:
            mock_fetch.return_value = quotes.PriceQuote(price=100.0)

            results = quotes.warm_cache(tickers)

        # Should return dict with all tickers
        self.assertEqual(set(results.keys()), set(tickers))
        # Should have called fetch_ticker_price once per ticker
        self.assertEqual(mock_fetch.call_count, len(tickers))

    def test_extract_price_priority(self):
        """
        _extract_price should try fields in order: regularMarketPrice, regularMarketPreviousClose, etc.
        """
        # Test regularMarketPrice priority
        payload = {"regularMarketPrice": 150.0, "regularMarketPreviousClose": 140.0}
        price, err = quotes._extract_price(payload)
        self.assertEqual(price, 150.0)

        # Test fallback to regularMarketPreviousClose
        payload = {"regularMarketPreviousClose": 140.0}
        price, err = quotes._extract_price(payload)
        self.assertEqual(price, 140.0)

        # Test no valid price
        payload = {"someOtherField": 999.0}
        price, err = quotes._extract_price(payload)
        self.assertIsNone(price)
        self.assertIsNotNone(err)

    def test_cache_stats(self):
        """
        cache_stats should return dict with cache info.
        """
        quotes._set_cache("AAPL", 150.0)
        quotes._set_cache("MSFT", 250.0)

        stats = quotes.cache_stats()
        self.assertEqual(stats["cached_tickers"], 2)
        self.assertEqual(stats["stale_tickers"], 2)
        self.assertEqual(stats["cache_ttl_seconds"], quotes.CACHE_TTL_SECONDS)

    def test_non_ok_quote_no_retry(self):
        """
        When _fetch_live returns non-ok (but doesn't raise), should not retry.
        """
        call_count = [0]

        def side_effect(ticker):
            call_count[0] += 1
            return quotes.PriceQuote(
                price=None,
                error_message="Empty price history"
            )

        with patch("core.quotes._fetch_live", side_effect=side_effect):
            with patch("time.sleep"):
                result = quotes.fetch_ticker_price("AAPL")

        # Should be called exactly once, not retried
        self.assertEqual(call_count[0], 1)
        self.assertFalse(result.ok)


class TestPriceQuote(unittest.TestCase):
    """Test PriceQuote dataclass."""

    def test_price_quote_ok_property(self):
        """PriceQuote.ok should be True only for positive prices."""
        self.assertTrue(quotes.PriceQuote(150.0).ok)
        self.assertFalse(quotes.PriceQuote(None).ok)
        self.assertFalse(quotes.PriceQuote(0.0).ok)
        self.assertFalse(quotes.PriceQuote(-10.0).ok)

    def test_price_quote_with_error_message(self):
        """PriceQuote should store error messages."""
        pq = quotes.PriceQuote(150.0, error_message="Stale price")
        self.assertEqual(pq.price, 150.0)
        self.assertEqual(pq.error_message, "Stale price")


if __name__ == "__main__":
    unittest.main()
