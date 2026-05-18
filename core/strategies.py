"""
data.py — Investment strategy mappings and metadata.

Each strategy maps to at least three equities (stocks or ETFs) used when
building a diversified suggestion portfolio for the user's selected strategies.

Strategy rationale (see README § Investment Methodology for full citations):
  Ethical Investing   — ESG-screened large caps with carbon-neutrality commitments
                        AAPL (carbon neutral 2030, RE100), ADBE (MSCI ESG AAA),
                        MSFT (carbon negative 2030 pledge, Climate Innovation Fund)
  Growth Investing    — High-revenue-growth companies in expanding markets
                        NVDA (AI GPU monopoly, >200% YoY data-centre revenue),
                        AMZN (AWS cloud leader + advertising flywheel),
                        TSLA (EV pioneer, energy storage, autonomy platform)
  Index Investing     — Passive market exposure via low-cost diversified ETFs
                        VTI (total US market, 0.03% ER), IXUS (4,300 intl stocks),
                        BND (US investment-grade bonds, portfolio stabiliser)
  Quality Investing   — High ROIC, durable moat, consistent free cash flow
                        COST (90%+ membership renewal, 20%+ ROIC),
                        JNJ (60+ yr dividend growth, diversified healthcare),
                        PG (67+ yr Dividend King, brand pricing power)
  Value Investing     — Securities trading below estimated intrinsic value
                        BRK-B (sum-of-parts discount, Buffett capital discipline),
                        JPM (best-managed US bank, ROE >15%, P/B entry points),
                        XOM (single-digit P/E at commodity lows, dividend through cycles)
"""

# Display name -> list of Yahoo Finance ticker symbols
STRATEGY_TICKERS = {
    "Ethical Investing": ["AAPL", "ADBE", "MSFT"],
    "Growth Investing": ["NVDA", "AMZN", "TSLA"],
    "Index Investing": ["VTI", "IXUS", "BND"],
    "Quality Investing": ["COST", "JNJ", "PG"],
    "Value Investing": ["BRK-B", "JPM", "XOM"],
}

# All strategy names for UI dropdowns (stable order)
ALL_STRATEGY_NAMES = list(STRATEGY_TICKERS.keys())


def ticker_to_strategy(selected_strategies):
    """
    Build a lookup: ticker -> first strategy label that owns it among selected ones.

    If two strategies share a ticker (should not occur with given mappings),
    the first listed strategy wins.
    """
    mapping = {}
    for strat in selected_strategies:
        for ticker in STRATEGY_TICKERS.get(strat, []):
            if ticker not in mapping:
                mapping[ticker] = strat
    return mapping
