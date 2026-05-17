## Stock Portfolio Suggestion Engine

A full-stack portfolio management application built with Streamlit (Python backend) and a Next.js news web app. Users can build and track investment portfolios across five strategy styles, with live market data, risk scoring, JWT-based authentication, and persistent SQLite storage.

---

### Architecture

```
app.py                  # Streamlit entry point
├── api/                # FastAPI REST layer (routes, schemas, dependencies)
├── auth/               # JWT tokens, bcrypt hashing, user management
├── core/               # Business logic: portfolio, risk, quotes, market cap, news
├── database/           # SQLite connection and repositories
├── ui/                 # Streamlit UI components and CSS
├── scripts/            # One-off migration and backfill utilities
├── news-web/           # Next.js standalone news web app
└── frontend/           # Vite/TypeScript frontend (built assets in dist/)
```

---

### Investment strategies

| Strategy | Thesis |
| --- | --- |
| Ethical Investing | Large, transparent cash generators with durable brands |
| Growth Investing | High-revenue-growth innovators |
| Index Investing | Low-cost ETFs covering US equities, international, and bonds |
| Quality Investing | Household staples anchored by high ROIC operators |
| Value Investing | Franchise balance sheets favored when spreads widen |

Selecting two strategies merges their ticker lists (deduplicating overlaps), then allocates budget proportionally by market cap — falling back to equal-weight per strategy when cap data is unavailable.

---

### Local setup

**Prerequisites:** Python 3.9+, Node.js 18+ (for news-web)

```bash
cd stock-portfolio-suggestion-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Run the Streamlit app:**

```bash
streamlit run app.py
```

**Secrets (optional — for live news features):**

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# fill in your API keys
```

**Run the news web app:**

```bash
cd news-web
cp .env.local.example .env.local   # fill in API keys
npm install && npm run dev
```

---

### Features

- **Authentication** — register/login with bcrypt-hashed passwords and JWT session tokens
- **Portfolio builder** — pick 1–2 strategies, set a budget, get market-cap-weighted allocations
- **Live quotes** — real-time prices via `yfinance` (Yahoo Finance, no API key required)
- **Risk scoring** — value-weighted risk level (Low / Moderate / High) per holding
- **Portfolio history** — persistent trend chart across sessions (SQLite-backed)
- **Market news** — integrated news feed via `core/news.py` and the standalone `news-web` app
- **REST API** — FastAPI server in `api/` for programmatic access

---

### Testing

Tests live in `tests/` and require no network access or secrets — they use mocks and in-memory SQLite only.

**Run all tests:**

```bash
python -m pytest tests/test_project_functions.py -v
```

**Run a single test class:**

```bash
python -m pytest tests/test_project_functions.py::TestRiskScoring -v
```

#### Test cases

| # | Class | Function(s) tested | What it checks |
|---|---|---|---|
| 1 | `TestUsernameValidation` | `auth.users.sanitize_username` | Lowercasing, special-char rejection, length limits |
| 2 | `TestPasswordPolicy` | `auth.users.password_policy_error` | Min-length enforcement (8 chars) |
| 3 | `TestPasswordHashing` | `auth.hashing.hash_password`, `verify_hash` | bcrypt salting, correct/wrong password verification |
| 4 | `TestJWTTokens` | `auth.tokens.create_access_token`, `decode_token` | Round-trip encoding, expired token, tampered token |
| 5 | `TestRiskScoring` | `core.risk.calculate_risk_level` | Low/Moderate/High thresholds, unknown ticker default, empty holdings |
| 6 | `TestUniqueTickers` | `core.portfolio.unique_tickers_for_strategies` | Deduplication, order preservation, single/dual strategy |
| 7 | `TestPortfolioTotals` | `core.portfolio.portfolio_totals` | Gain/loss math, partial pricing, zero investment |
| 8 | `TestMarkToMarket` | `core.portfolio.mark_to_market_holdings` | Price × shares rollup, missing-price warnings |
| 9 | `TestStrategyAllocation` | `core.market_cap._allocate_by_strategy` | Equal split per strategy/ticker, total equals investment |
| 10 | `TestComputeAllocations` | `core.market_cap.compute_allocations` | Market-cap weighting (3:1 ratio), fallback on missing caps, total invariant |

**Running test suite:**

```bash
# pytest is included in requirements.txt — no separate install needed
python -m pytest tests/test_project_functions.py -v
```

---

### Notes

- Yahoo Finance intermittently rate-limits automated requests; retry after a brief pause if quotes fail.
- `portfolio.db` is local only and excluded from version control.
- `.streamlit/secrets.toml` is excluded — use `secrets.toml.example` as the template.

---

© Academic project — educational use only, not financial advice.
