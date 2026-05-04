"""
data.py — Investment strategy mappings and metadata.

Each strategy maps to at least three equities (stocks or ETFs) used when
building a diversified suggestion portfolio for the user's selected strategies.
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
