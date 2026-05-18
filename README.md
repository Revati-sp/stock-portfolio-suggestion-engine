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

### Investment Methodology and Strategy Rationale

#### Overview

This engine implements a **rules-based, passive allocation model** inspired by widely documented investment frameworks in academic finance and professional portfolio management. Users select one or two broad investment strategies; the engine then maps each strategy to a curated set of publicly traded stocks or ETFs and sizes positions using a **market-capitalisation weighting** approach.

The underlying principle is that market capitalisation — the total market value of a company's outstanding shares — is a widely accepted proxy for a company's relative weight in the investable universe. Larger, more established companies receive proportionally larger allocations, which mirrors the construction methodology of major benchmark indices such as the S&P 500 and MSCI World.

This approach has two key properties that make it appropriate for a portfolio suggestion engine:

1. **Self-adjusting exposure**: Positions naturally grow when holdings appreciate and shrink when they decline, without requiring manual rebalancing.
2. **Reduced concentration risk**: Capital is spread across holdings in proportion to their economic footprint rather than arbitrarily.

> **Disclaimer:** This project is for educational purposes only and is not financial advice. All data is sourced from publicly available market feeds. Past performance does not imply future results. Do not make real investment decisions based on this tool.

---

#### Allocation Mechanism

When a user selects **one strategy**, all invested capital is allocated across that strategy's tickers weighted by their individual market capitalisations.

When a user selects **two strategies**, the total investment is divided equally between the two strategies (50% each), and within each strategy's share, allocation is again market-cap-weighted among that strategy's tickers.

**Example** — $10,000 split across Growth Investing and Value Investing:

| Strategy | Strategy Budget | Tickers | Weight basis |
|---|---|---|---|
| Growth Investing | $5,000 | NVDA, AMZN, TSLA | Market cap within group |
| Value Investing | $5,000 | BRK-B, JPM, XOM | Market cap within group |

If live market-cap data is unavailable for a ticker (e.g., Yahoo Finance rate-limits the request), the engine falls back to an equal-weight split within that strategy, ensuring the portfolio is always generated without errors.

From each strategy's allocation, the number of fractional shares purchased per ticker is computed as:

```
shares = dollar_allocation / current_live_price
```

Live prices are fetched in real time from Yahoo Finance via the `yfinance` library. A 15-minute cache and retry layer prevents rate-limit failures from blocking the UI.

---

#### Strategy Definitions and Ticker Rationale

---

##### 1. Ethical Investing
**Tickers: AAPL, ADBE, MSFT**

**Strategy definition:** Ethical investing (also called ESG investing — Environmental, Social, and Governance) selects companies based on non-financial criteria alongside financial performance. The goal is to align capital with companies that demonstrate responsible business practices, including climate commitments, strong corporate governance, and positive social impact. Academic research (e.g., Friede, Busch & Bassen, 2015, *Journal of Sustainable Finance & Investment*) finds that high-ESG portfolios exhibit risk-adjusted returns comparable to or better than conventional benchmarks.

**Why these tickers:**

| Ticker | Company | Ethical Rationale |
|---|---|---|
| AAPL | Apple Inc. | Apple has committed to carbon neutrality across its entire supply chain and products by 2030. It is a member of the RE100 initiative (100% renewable electricity) and publishes annual environmental progress reports audited to ISO 14064. Its supply chain transparency and conflict-mineral disclosure policies place it among the highest-scored technology companies on MSCI ESG ratings. |
| ADBE | Adobe Inc. | Adobe consistently earns an MSCI ESG rating of "AAA" — the highest tier. As a software-only company, it has a structurally low carbon footprint. Adobe has committed to 100% renewable energy, publishes a detailed corporate responsibility report, and has formalised diversity and pay-equity targets with external audit trails. |
| MSFT | Microsoft Corporation | Microsoft has committed to becoming **carbon negative** by 2030 and to removing all historical carbon emissions by 2050. It has invested over $1 billion in a Climate Innovation Fund, purchases renewable energy matching 100% of its consumption, and consistently achieves top-tier scores on the Dow Jones Sustainability Index. Its governance structure and executive accountability standards are industry benchmarks. |

---

##### 2. Growth Investing
**Tickers: NVDA, AMZN, TSLA**

**Strategy definition:** Growth investing targets companies whose revenues, earnings, or addressable markets are expanding significantly faster than the broader economy. Pioneered as a discipline by investors such as Philip Fisher (*Common Stocks and Uncommon Profits*, 1958) and later quantified through metrics like the PEG ratio (Price/Earnings-to-Growth), growth investors accept higher current valuations in exchange for the expectation of compounding future returns. The strategy is inherently higher-risk: high-multiple stocks are more sensitive to interest rate changes and growth disappointments.

**Why these tickers:**

| Ticker | Company | Growth Rationale |
|---|---|---|
| NVDA | NVIDIA Corporation | NVIDIA's data-centre revenue grew over 200% year-over-year in fiscal year 2024, driven by demand for its H100/H200 GPU accelerators used in training large AI models. It holds an estimated 70–90% market share in AI training hardware, a near-monopoly position in a market forecast to reach hundreds of billions of dollars. Its CUDA software platform creates substantial switching costs. |
| AMZN | Amazon.com Inc. | Amazon Web Services (AWS) is the global leader in cloud infrastructure, generating high-margin revenue that funds continued growth in e-commerce, advertising, and AI services. Amazon's compounding reinvestment strategy — deliberately suppressing short-term profits to fund long-run market expansion — is a textbook case study in growth-oriented capital allocation. |
| TSLA | Tesla Inc. | Tesla pioneered the mass-market electric vehicle category and retains significant brand recognition and direct-to-consumer scale advantages. Beyond vehicles, Tesla is expanding into energy storage (Megapack), autonomy software (Full Self-Driving), and AI infrastructure (Dojo supercomputer). Its revenue CAGR from 2019–2023 exceeded 40%, placing it among the fastest-scaling industrial companies in history. |

---

##### 3. Index Investing
**Tickers: VTI, IXUS, BND**

**Strategy definition:** Index investing (passive investing) is grounded in the Efficient Market Hypothesis (Fama, 1970), which holds that active stock-picking cannot consistently outperform the market after fees. Rather than selecting individual securities, index investors buy diversified funds that track entire markets. John Bogle, founder of Vanguard, popularised this approach with the world's first public index fund in 1976. Academic research, including SPIVA scorecards, consistently shows that 80–90% of actively managed funds underperform their benchmark index over 10-year horizons.

**Why these tickers:**

| Ticker | Fund | Index Rationale |
|---|---|---|
| VTI | Vanguard Total Stock Market ETF | VTI tracks the CRSP US Total Market Index, covering approximately 3,900 US companies across all market capitalisations — large, mid, and small cap. Its expense ratio is 0.03%, among the lowest in the industry. Holding VTI is equivalent to owning a proportional slice of the entire US equity market. |
| IXUS | iShares Core MSCI Total International Stock ETF | IXUS provides exposure to approximately 4,300 non-US companies across developed and emerging markets (Europe, Asia-Pacific, Latin America, Middle East). International diversification reduces dependence on the US business cycle. Its expense ratio is 0.07%, making it an efficient global complement to VTI. |
| BND | Vanguard Total Bond Market ETF | BND tracks the Bloomberg US Aggregate Bond Index, holding over 10,000 US investment-grade bonds — government, corporate, and mortgage-backed. Bonds provide income, reduce portfolio volatility, and tend to rise in value during equity market downturns, acting as a portfolio stabiliser. |

Combined, VTI + IXUS + BND provide a globally diversified, low-cost portfolio spanning equities and fixed income — a three-fund portfolio structure recommended by many academic financial planners.

---

##### 4. Quality Investing
**Tickers: COST, JNJ, PG**

**Strategy definition:** Quality investing selects companies with durable competitive advantages ("economic moats"), high returns on invested capital (ROIC), stable free cash flow generation, and low financial leverage. The approach is rooted in research by Novy-Marx (2013) and AQR Capital, which demonstrated that high-quality (profitable, stable) companies have historically delivered superior risk-adjusted returns. Quality companies are also more defensive: their stable cash flows give them resilience during economic downturns.

**Why these tickers:**

| Ticker | Company | Quality Rationale |
|---|---|---|
| COST | Costco Wholesale Corporation | Costco's membership model generates over $4 billion annually in high-margin, recurring fee revenue before a single product is sold. Its ROIC consistently exceeds 20%, and its inventory turnover ratio is among the highest in retail. The membership renewal rate exceeds 90%, indicating exceptional customer loyalty and pricing power. These are hallmarks of a quality compounder. |
| JNJ | Johnson & Johnson | Johnson & Johnson is a Dividend King — it has increased its dividend for over 60 consecutive years — evidence of consistent cash flow across full economic cycles. Operating across pharmaceuticals and medtech, it maintains high gross margins and steady ROIC. Its diversified product portfolio across essential healthcare categories insulates revenues from any single market disruption. |
| PG | Procter & Gamble Co. | Procter & Gamble owns 65+ brands including Tide, Gillette, Pampers, and Crest. These brands occupy category-defining positions where consumers exhibit persistent repeat-purchase behaviour regardless of economic conditions. P&G has increased its dividend for over 67 consecutive years (Dividend King status), backed by free cash flow margins that routinely exceed 15%. Its pricing power — demonstrated by successful price increases during inflationary periods — confirms deep consumer franchise value. |

---

##### 5. Value Investing
**Tickers: BRK-B, JPM, XOM**

**Strategy definition:** Value investing, formalised by Benjamin Graham (*The Intelligent Investor*, 1949) and extended by Warren Buffett, seeks securities trading below their intrinsic value — the discounted present value of all future cash flows. Value investors use metrics such as Price-to-Earnings (P/E), Price-to-Book (P/B), Enterprise Value-to-EBITDA, and free cash flow yield to identify undervalued businesses. Academic evidence (Fama & French, 1992) shows that value stocks have historically earned a return premium over growth stocks over long horizons, though with periods of underperformance.

**Why these tickers:**

| Ticker | Company | Value Rationale |
|---|---|---|
| BRK-B | Berkshire Hathaway Inc. Class B | Berkshire Hathaway is Warren Buffett's conglomerate, directly embodying the value investing philosophy. It holds a portfolio of wholly owned businesses (GEICO, BNSF Railway, Berkshire Hathaway Energy) plus large equity stakes in companies like Apple and Bank of America. Berkshire typically trades at or near 1.2–1.5× book value, historically a significant discount to the intrinsic value of its subsidiaries when evaluated sum-of-parts. It holds hundreds of billions in cash, enabling opportunistic acquisitions at distressed prices. |
| JPM | JPMorgan Chase & Co. | JPMorgan is the largest US bank by assets and consistently earns a Return on Equity (ROE) of 15–17%, above the cost of equity — creating genuine shareholder value. It is frequently cited as the best-managed major bank globally. When banking sector sentiment is negative, JPM can trade at Price-to-Book ratios approaching 1.0–1.5×, offering value entry points in a business with durable competitive advantages (scale in deposits, investment banking relationships, consumer credit infrastructure). |
| XOM | Exxon Mobil Corporation | ExxonMobil is one of the world's largest integrated energy companies, with operations spanning upstream exploration, downstream refining, and chemicals. Its stock has historically traded at single-digit P/E multiples during periods of low oil prices, reflecting market pessimism rather than fundamental impairment of long-lived assets. Exxon has maintained and grown its dividend through multiple commodity cycles — evidence of balance sheet discipline that value investors prize. |

---

#### Summary Table

| Strategy | Tickers | Core Principle | Risk Level |
|---|---|---|---|
| Ethical Investing | AAPL, ADBE, MSFT | ESG-screened, carbon-committed large caps | Moderate |
| Growth Investing | NVDA, AMZN, TSLA | High revenue growth, expanding TAM | High |
| Index Investing | VTI, IXUS, BND | Passive market exposure, low cost, diversified | Low–Moderate |
| Quality Investing | COST, JNJ, PG | High ROIC, stable cash flow, dividend continuity | Low–Moderate |
| Value Investing | BRK-B, JPM, XOM | Trading below intrinsic value, margin of safety | Moderate |

The engine's **risk scoring system** (visible in the Portfolio Summary card) reflects these levels: each ticker carries a pre-assigned risk score from 1 (BND — government bonds) to 5 (TSLA — high-volatility growth), and the portfolio risk level is a value-weighted average of its holdings.

---

> **Academic note:** The strategy-to-ticker mapping in this project was designed for educational demonstration. In a production system, ticker selection would be driven by quantitative screening (e.g., ESG scores from MSCI, revenue growth CAGR from financial statements, ROIC from DCF models) refreshed on a recurring schedule. This project demonstrates the allocation and pricing engine architecture; the specific securities are illustrative.

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
python -m pytest tests/ -v
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

**Run all tests (recommended):**

```bash
# pytest is included in requirements.txt — no separate install needed
python -m pytest tests/ -v
```

**Run each test file separately:**

```bash
# Core project functions (auth, portfolio, risk, allocation)
python -m pytest tests/test_project_functions.py -v

# Quote-fetching reliability layer (cache, retries, rate limiting)
python -m pytest tests/test_quotes.py -v
```

---

### Notes

- Yahoo Finance intermittently rate-limits automated requests; retry after a brief pause if quotes fail.
- `portfolio.db` is local only and excluded from version control.
- `.streamlit/secrets.toml` is excluded — use `secrets.toml.example` as the template.

---

© Academic project — educational use only, not financial advice.
