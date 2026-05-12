"""Ticker-weighted portfolio risk scoring for summary display."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

TICKER_RISK: dict[str, int] = {
    "BND": 1,
    "ILTB": 1,
    "JNJ": 1,
    "PG": 1,
    "VTI": 2,
    "IXUS": 2,
    "AAPL": 2,
    "MSFT": 2,
    "COST": 2,
    "BRK-B": 2,
    "ADBE": 3,
    "JPM": 3,
    "XOM": 3,
    "NVDA": 4,
    "AMZN": 4,
    "TSLA": 5,
}


@dataclass(frozen=True)
class RiskLevelResult:
    score: float
    level: str
    badge_class: str


def calculate_risk_level(holdings: Sequence[Mapping[str, object]]) -> RiskLevelResult:
    total_value = 0.0
    weighted_risk = 0.0

    for holding in holdings:
        ticker = str(holding.get("ticker") or holding.get("symbol") or "")
        raw_value = holding.get("currentValue")
        if raw_value is None:
            raw_value = holding.get("value", 0)
        try:
            value = float(raw_value or 0)
        except (TypeError, ValueError):
            value = 0.0
        risk = TICKER_RISK.get(ticker, 3)
        weighted_risk += risk * value
        total_value += value

    if total_value == 0:
        return RiskLevelResult(0.0, "N/A", "holdings-risk-badge--na")

    score = weighted_risk / total_value
    if score < 2:
        return RiskLevelResult(score, "Low", "holdings-risk-badge--low")
    if score < 3.5:
        return RiskLevelResult(score, "Moderate", "holdings-risk-badge--moderate")
    return RiskLevelResult(score, "High", "holdings-risk-badge--high")
