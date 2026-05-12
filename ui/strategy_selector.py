from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

_strategy_selector = components.declare_component(
    "strategy_selector",
    path=str(_FRONTEND_DIST),
)


def strategy_selector_widget(*, default: list[str] | None = None, key: str | None = None) -> list[str]:
    selected = default if default is not None else ["Index Investing"]
    theme = st.context.theme.type or "light"
    value = _strategy_selector(default=selected, theme=theme, key=key)
    if value is None:
        return list(selected)
    return list(value)
