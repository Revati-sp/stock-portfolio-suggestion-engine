from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

_portfolio_builder = components.declare_component(
    "portfolio_builder",
    path=str(_FRONTEND_DIST),
)

_DEFAULT_STATE: dict[str, Any] = {
    "strategies": ["Index Investing"],
    "amount": 10_000.0,
    "action": None,
}


def portfolio_builder_widget(*, default: dict[str, Any] | None = None, key: str | None = None) -> dict[str, Any]:
    state = dict(default if default is not None else _DEFAULT_STATE)
    value = _portfolio_builder(default=state, key=key)
    if value is None:
        return state
    return dict(value)
