"""
tests/test_project_functions.py
================================
Ten test cases covering distinct functions across the project.

Each test is self-contained and uses only in-process logic or in-memory
SQLite — no live network calls, no secrets.toml required.

Setup (one-time):
    cd Revati/stock-portfolio-suggestion-engine
    pip install -r requirements.txt

Run all ten tests:
    python -m pytest tests/test_project_functions.py -v

Run a single test by name:
    python -m pytest tests/test_project_functions.py::TestUsernameValidation::test_valid_username -v
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pandas as pd

# ---------------------------------------------------------------------------
# Make sure project root is on sys.path so imports work when run from any dir.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ===========================================================================
# TEST CASE 1 — Username sanitization (auth/users.py :: sanitize_username)
# ===========================================================================
class TestUsernameValidation(unittest.TestCase):
    """
    Function tested: auth.users.sanitize_username

    sanitize_username() enforces username rules before any DB write:
    - Must start with a letter or digit
    - May contain letters, digits, hyphens, underscores
    - Max 48 characters
    - Input is lowercased and stripped
    - Returns None for anything invalid
    """

    def setUp(self):
        from auth.users import sanitize_username
        self.sanitize = sanitize_username

    def test_valid_username_lowercased(self):
        """A normal alphanumeric username is accepted and returned in lowercase."""
        result = self.sanitize("Alice123")
        self.assertEqual(result, "alice123")

    def test_leading_special_char_rejected(self):
        """A username starting with a special character must be rejected (returns None)."""
        result = self.sanitize("_admin")
        self.assertIsNone(result)

    def test_spaces_stripped_but_internal_spaces_rejected(self):
        """Leading/trailing whitespace is stripped; internal spaces make it invalid."""
        self.assertIsNone(self.sanitize("alice bob"))

    def test_empty_string_rejected(self):
        """An empty string is not a valid username."""
        self.assertIsNone(self.sanitize(""))

    def test_hyphen_and_underscore_allowed(self):
        """Hyphens and underscores within the name are permitted."""
        result = self.sanitize("john-doe_99")
        self.assertEqual(result, "john-doe_99")


# ===========================================================================
# TEST CASE 2 — Password policy enforcement (auth/users.py :: password_policy_error)
# ===========================================================================
class TestPasswordPolicy(unittest.TestCase):
    """
    Function tested: auth.users.password_policy_error

    password_policy_error() returns an error string when the password is too
    short (< 8 chars) and None when the password meets the policy.
    """

    def setUp(self):
        from auth.users import password_policy_error
        self.policy = password_policy_error

    def test_short_password_returns_error(self):
        """A 5-character password must trigger an error message."""
        error = self.policy("abc12")
        self.assertIsNotNone(error)
        self.assertIn("8", error)  # message must mention the required length

    def test_exactly_8_chars_passes(self):
        """A password of exactly 8 characters must pass the policy."""
        error = self.policy("abcd1234")
        self.assertIsNone(error)

    def test_long_password_passes(self):
        """A long, strong password must pass the policy."""
        error = self.policy("S3cur3P@ssword!")
        self.assertIsNone(error)

    def test_empty_password_fails(self):
        """An empty password must fail."""
        error = self.policy("")
        self.assertIsNotNone(error)


# ===========================================================================
# TEST CASE 3 — bcrypt password hashing & verification (auth/hashing.py)
# ===========================================================================
class TestPasswordHashing(unittest.TestCase):
    """
    Functions tested: auth.hashing.hash_password, auth.hashing.verify_hash

    hash_password() produces a bcrypt hash that is NOT equal to the plain text.
    verify_hash() confirms the correct plain text and rejects wrong ones.
    """

    def setUp(self):
        from auth.hashing import hash_password, verify_hash
        self.hash_password = hash_password
        self.verify_hash = verify_hash

    def test_hash_is_not_plaintext(self):
        """The stored hash must differ from the original password."""
        plain = "MyPassword1!"
        hashed = self.hash_password(plain)
        self.assertNotEqual(plain, hashed)

    def test_correct_password_verifies(self):
        """verify_hash must return True for the original password."""
        plain = "CorrectHorse99"
        hashed = self.hash_password(plain)
        self.assertTrue(self.verify_hash(plain, hashed))

    def test_wrong_password_fails(self):
        """verify_hash must return False for any other string."""
        hashed = self.hash_password("RealPassword1")
        self.assertFalse(self.verify_hash("WrongPassword", hashed))

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt salts each hash; the same password must produce different digests."""
        plain = "SamePassword1"
        h1 = self.hash_password(plain)
        h2 = self.hash_password(plain)
        self.assertNotEqual(h1, h2)


# ===========================================================================
# TEST CASE 4 — JWT token creation and decoding (auth/tokens.py)
# ===========================================================================
class TestJWTTokens(unittest.TestCase):
    """
    Functions tested: auth.tokens.create_access_token, auth.tokens.decode_token

    create_access_token() encodes a username into a signed JWT.
    decode_token() extracts the username back out.
    An expired token must raise ValueError.
    """

    def setUp(self):
        # Use a fixed test key so the test is deterministic
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-ok"
        from auth.tokens import create_access_token, decode_token
        self.create = create_access_token
        self.decode = decode_token

    def tearDown(self):
        os.environ.pop("JWT_SECRET_KEY", None)

    def test_roundtrip_username(self):
        """A token created for 'testuser' must decode back to 'testuser'."""
        token = self.create("testuser")
        username = self.decode(token)
        self.assertEqual(username, "testuser")

    def test_expired_token_raises_value_error(self):
        """A token with a past expiry must raise ValueError on decode."""
        token = self.create("testuser", expires_delta=timedelta(seconds=-1))
        with self.assertRaises(ValueError) as ctx:
            self.decode(token)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_tampered_token_raises_value_error(self):
        """A token with its signature corrupted must raise ValueError."""
        token = self.create("testuser")
        bad_token = token[:-4] + "XXXX"
        with self.assertRaises(ValueError):
            self.decode(bad_token)


# ===========================================================================
# TEST CASE 5 — Portfolio risk scoring (core/risk.py :: calculate_risk_level)
# ===========================================================================
class TestRiskScoring(unittest.TestCase):
    """
    Function tested: core.risk.calculate_risk_level

    The function computes a value-weighted average of per-ticker risk scores
    (defined in TICKER_RISK), then maps the result to Low / Moderate / High.

      score < 2    → Low
      2 ≤ score < 3.5 → Moderate
      score ≥ 3.5  → High
      total_value = 0 → N/A

    Risk scores from the code:
      BND=1, JNJ=1, VTI=2, AAPL=2, JPM=3, NVDA=4, TSLA=5
    """

    def setUp(self):
        from core.risk import calculate_risk_level
        self.calc = calculate_risk_level

    def test_low_risk_bond_only(self):
        """BND has risk 1 (< 2 threshold) → result must be 'Low'."""
        holdings = [{"ticker": "BND", "currentValue": 10000}]
        result = self.calc(holdings)
        self.assertEqual(result.level, "Low")
        self.assertAlmostEqual(result.score, 1.0)

    def test_high_risk_tsla_only(self):
        """TSLA has risk 5 (≥ 3.5 threshold) → result must be 'High'."""
        holdings = [{"ticker": "TSLA", "currentValue": 5000}]
        result = self.calc(holdings)
        self.assertEqual(result.level, "High")
        self.assertAlmostEqual(result.score, 5.0)

    def test_moderate_risk_mixed(self):
        """
        Equal-value mix of JNJ (risk=1) and NVDA (risk=4):
        weighted score = (1×5000 + 4×5000) / 10000 = 2.5  → 'Moderate'
        """
        holdings = [
            {"ticker": "JNJ", "currentValue": 5000},
            {"ticker": "NVDA", "currentValue": 5000},
        ]
        result = self.calc(holdings)
        self.assertEqual(result.level, "Moderate")
        self.assertAlmostEqual(result.score, 2.5)

    def test_empty_holdings_returns_na(self):
        """No holdings → total_value is 0, result must be 'N/A'."""
        result = self.calc([])
        self.assertEqual(result.level, "N/A")
        self.assertAlmostEqual(result.score, 0.0)

    def test_unknown_ticker_defaults_to_risk_3(self):
        """
        A ticker not in TICKER_RISK (e.g. 'XYZ') defaults to risk=3.
        score = 3.0 → 'Moderate' (2 ≤ 3 < 3.5).
        """
        holdings = [{"ticker": "XYZ", "currentValue": 1000}]
        result = self.calc(holdings)
        self.assertEqual(result.level, "Moderate")
        self.assertAlmostEqual(result.score, 3.0)


# ===========================================================================
# TEST CASE 6 — Strategy ticker deduplication (core/portfolio.py)
# ===========================================================================
class TestUniqueTickers(unittest.TestCase):
    """
    Function tested: core.portfolio.unique_tickers_for_strategies

    When the user picks strategies, their tickers are merged in order.
    A ticker appearing in two strategies must appear only once in the result,
    preserving the order of first encounter.
    """

    def setUp(self):
        from core.portfolio import unique_tickers_for_strategies
        self.unique = unique_tickers_for_strategies

    def test_single_strategy_returns_all_tickers(self):
        """Selecting 'Ethical Investing' must return exactly its 3 tickers."""
        from core.strategies import STRATEGY_TICKERS
        result = self.unique(["Ethical Investing"])
        self.assertEqual(result, STRATEGY_TICKERS["Ethical Investing"])

    def test_two_strategies_no_overlap_returns_six(self):
        """
        'Ethical Investing' and 'Growth Investing' share no tickers,
        so the combined list must have 6 unique tickers.
        """
        result = self.unique(["Ethical Investing", "Growth Investing"])
        self.assertEqual(len(result), 6)

    def test_order_preserved_first_strategy_first(self):
        """
        Tickers from the first strategy must appear before tickers from the second.
        The first ticker in the result must come from 'Index Investing'.
        """
        from core.strategies import STRATEGY_TICKERS
        result = self.unique(["Index Investing", "Value Investing"])
        first_strategy_tickers = STRATEGY_TICKERS["Index Investing"]
        self.assertEqual(result[0], first_strategy_tickers[0])

    def test_duplicate_tickers_appear_once(self):
        """
        If the same strategy is listed twice (edge case), each ticker
        must still appear exactly once in the output.
        """
        result = self.unique(["Quality Investing", "Quality Investing"])
        self.assertEqual(len(result), len(set(result)))


# ===========================================================================
# TEST CASE 7 — Portfolio totals rollup (core/portfolio.py :: portfolio_totals)
# ===========================================================================
class TestPortfolioTotals(unittest.TestCase):
    """
    Function tested: core.portfolio.portfolio_totals

    Given a DataFrame with 'Current Value (USD)' and 'Allocation (USD)' columns,
    portfolio_totals() returns (basis, marked_value, gain_loss).

    - basis     = lump_sum_usd (always the original investment)
    - marked    = sum of rows that have a non-null current value
    - gain_loss = marked - allocation_of_priced_rows
    """

    def setUp(self):
        from core.portfolio import portfolio_totals
        self.totals = portfolio_totals

    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def test_all_priced_gain(self):
        """
        Invest $10,000; portfolio grows to $11,000.
        gain_loss must be $1,000.
        """
        df = self._make_df([
            {"Ticker": "AAPL", "Allocation (USD)": 5000.0, "Current Value (USD)": 5500.0},
            {"Ticker": "MSFT", "Allocation (USD)": 5000.0, "Current Value (USD)": 5500.0},
        ])
        basis, marked, gain_loss = self.totals(df, 10000.0)
        self.assertEqual(basis, 10000.0)
        self.assertAlmostEqual(marked, 11000.0)
        self.assertAlmostEqual(gain_loss, 1000.0)

    def test_partial_pricing_ignores_unpriced(self):
        """
        One ticker has no price (None).  Only the priced row contributes to
        marked value; gain_loss uses only the priced allocation.
        """
        df = self._make_df([
            {"Ticker": "AAPL", "Allocation (USD)": 5000.0, "Current Value (USD)": 4800.0},
            {"Ticker": "MSFT", "Allocation (USD)": 5000.0, "Current Value (USD)": None},
        ])
        basis, marked, gain_loss = self.totals(df, 10000.0)
        self.assertEqual(basis, 10000.0)
        self.assertAlmostEqual(marked, 4800.0)
        self.assertAlmostEqual(gain_loss, -200.0)  # 4800 - 5000

    def test_zero_investment_no_crash(self):
        """An empty DataFrame must return zeros without raising."""
        df = pd.DataFrame(columns=["Ticker", "Allocation (USD)", "Current Value (USD)"])
        basis, marked, gain_loss = self.totals(df, 0.0)
        self.assertEqual(basis, 0.0)
        self.assertAlmostEqual(marked, 0.0)


# ===========================================================================
# TEST CASE 8 — Mark-to-market with mocked quotes (core/portfolio.py)
# ===========================================================================
class TestMarkToMarket(unittest.TestCase):
    """
    Function tested: core.portfolio.mark_to_market_holdings

    mark_to_market_holdings() takes [(ticker, shares), ...] and a quote function,
    multiplies shares × price for each priced ticker, skips unpriced ones,
    and returns (total_usd, warnings).
    """

    def setUp(self):
        from core.portfolio import mark_to_market_holdings
        from core.quotes import PriceQuote
        self.mtm = mark_to_market_holdings
        self.PriceQuote = PriceQuote

    def _quote_fn(self, prices: dict):
        """Return a quote function backed by a dict; missing tickers get error."""
        def fn(ticker):
            if ticker in prices:
                return self.PriceQuote(price=prices[ticker])
            return self.PriceQuote(price=None, error_message="no price")
        return fn

    def test_all_priced_sums_correctly(self):
        """
        2 shares of AAPL @ $150 + 1 share of MSFT @ $300 = $600 total.
        No warnings expected.
        """
        holdings = [("AAPL", 2.0), ("MSFT", 1.0)]
        prices = {"AAPL": 150.0, "MSFT": 300.0}
        total, warnings = self.mtm(holdings, quote_fn=self._quote_fn(prices))
        self.assertAlmostEqual(total, 600.0)
        self.assertEqual(warnings, [])

    def test_missing_price_skipped_with_warning(self):
        """
        AAPL priced at $200, NVDA has no price.
        Total must reflect only AAPL; NVDA must appear in warnings.
        """
        holdings = [("AAPL", 1.0), ("NVDA", 2.0)]
        prices = {"AAPL": 200.0}
        total, warnings = self.mtm(holdings, quote_fn=self._quote_fn(prices))
        self.assertAlmostEqual(total, 200.0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("NVDA", warnings[0])

    def test_all_unpriced_returns_zero(self):
        """If no ticker can be priced the total must be 0.0."""
        holdings = [("ZZZZ", 10.0)]
        total, warnings = self.mtm(holdings, quote_fn=self._quote_fn({}))
        self.assertAlmostEqual(total, 0.0)
        self.assertTrue(len(warnings) > 0)


# ===========================================================================
# TEST CASE 9 — Strategy-level budget allocation (core/market_cap.py)
# ===========================================================================
class TestStrategyAllocation(unittest.TestCase):
    """
    Function tested: core.market_cap._allocate_by_strategy

    When market-cap data is unavailable, the fallback divides the total
    investment equally across strategies, then equally among each strategy's tickers.

    Example with $10,000 and two strategies of 3 tickers each:
      budget per strategy = $5,000
      budget per ticker   = $5,000 / 3 ≈ $1,666.67
    """

    def setUp(self):
        from core.market_cap import _allocate_by_strategy
        self.allocate = _allocate_by_strategy

    def test_single_strategy_splits_evenly(self):
        """
        $9,000 across 'Ethical Investing' (3 tickers: AAPL, ADBE, MSFT).
        Each ticker must receive exactly $3,000.
        """
        tickers = ["AAPL", "ADBE", "MSFT"]
        allocs = self.allocate(tickers, ["Ethical Investing"], 9000.0)
        for ticker in tickers:
            self.assertAlmostEqual(allocs[ticker], 3000.0, places=2)

    def test_two_strategies_equal_budget_split(self):
        """
        $10,000 across 'Ethical Investing' + 'Growth Investing'.
        Each strategy gets $5,000; each of its 3 tickers gets ~$1,666.67.
        """
        eth_tickers = ["AAPL", "ADBE", "MSFT"]
        gro_tickers = ["NVDA", "AMZN", "TSLA"]
        all_tickers = eth_tickers + gro_tickers
        allocs = self.allocate(
            all_tickers,
            ["Ethical Investing", "Growth Investing"],
            10000.0,
        )
        expected = 10000.0 / 2 / 3
        for ticker in all_tickers:
            self.assertAlmostEqual(allocs[ticker], expected, places=1)

    def test_total_allocation_equals_investment(self):
        """Sum of all allocations must equal the original investment amount."""
        tickers = ["AAPL", "ADBE", "MSFT"]
        allocs = self.allocate(tickers, ["Ethical Investing"], 7500.0)
        self.assertAlmostEqual(sum(allocs.values()), 7500.0, places=2)


# ===========================================================================
# TEST CASE 10 — Market-cap weighted allocation with mocked caps
#                (core/market_cap.py :: compute_allocations)
# ===========================================================================
class TestComputeAllocations(unittest.TestCase):
    """
    Function tested: core.market_cap.compute_allocations

    compute_allocations() fetches market caps via get_market_cap(), then
    allocates proportionally by cap weight.  We mock get_market_cap so the
    test never touches the network.

    With two tickers whose caps are in a 3:1 ratio and $10,000 to invest:
      AAPL cap = 3 T → gets 75% → $7,500
      MSFT cap = 1 T → gets 25% → $2,500
    """

    def setUp(self):
        import core.market_cap as mc_module
        self.mc = mc_module

    def test_proportional_market_cap_weighting(self):
        """
        AAPL:MSFT market cap ratio of 3:1 must produce a 75%:25% dollar split.
        """
        mock_caps = {"AAPL": 3_000_000_000_000, "MSFT": 1_000_000_000_000}

        with patch.object(self.mc, "get_market_cap", side_effect=lambda t: mock_caps.get(t)):
            allocs, warnings = self.mc.compute_allocations(
                ["AAPL", "MSFT"], 10_000.0
            )

        self.assertAlmostEqual(allocs["AAPL"], 7500.0, places=1)
        self.assertAlmostEqual(allocs["MSFT"], 2500.0, places=1)
        self.assertEqual(warnings, [])

    def test_missing_caps_fallback_to_strategy_level(self):
        """
        When get_market_cap returns None for all tickers, the function must
        fall back to equal-weight allocation and include a warning.
        """
        with patch.object(self.mc, "get_market_cap", return_value=None):
            allocs, warnings = self.mc.compute_allocations(
                ["AAPL", "MSFT"], 10_000.0,
                strategies=["Ethical Investing"],
            )

        # Must have emitted at least one fallback warning
        self.assertTrue(len(warnings) > 0)
        # All tickers must still receive some allocation
        for ticker in ["AAPL", "MSFT"]:
            self.assertIn(ticker, allocs)

    def test_total_allocation_always_equals_investment(self):
        """
        Regardless of whether caps are known or missing, the sum of allocations
        must equal the investment amount exactly (to within floating-point noise).
        """
        mock_caps = {"AAPL": 2e12, "MSFT": 0}  # MSFT cap zero → fallback path

        with patch.object(self.mc, "get_market_cap", side_effect=lambda t: mock_caps.get(t) or None):
            allocs, _ = self.mc.compute_allocations(
                ["AAPL", "MSFT"], 12_000.0,
                strategies=["Ethical Investing"],
            )

        self.assertAlmostEqual(sum(allocs.values()), 12_000.0, places=1)


if __name__ == "__main__":
    unittest.main()
