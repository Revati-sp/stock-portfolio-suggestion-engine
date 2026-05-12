"""Shared currency and percentage formatting for UI surfaces."""

from __future__ import annotations


def fmt_signed_dollar(value: float) -> str:
    if value > 0:
        return f"+${value:,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return "$0.00"


def fmt_signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"+{value:.2f}%"
    if value < 0:
        return f"{value:.2f}%"
    return "0.00%"
