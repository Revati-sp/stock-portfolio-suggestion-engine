"""Portfolio history cards and rerun actions."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st

from database.repositories import load_recent_records
from ui.formatting import fmt_signed_dollar, fmt_signed_pct
from ui.navigation import go_to_portfolio_view


def _format_history_datetime(raw: str) -> str:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(raw), fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d":
            return dt.strftime("%b %d, %Y")
        time_label = dt.strftime("%I:%M %p").lstrip("0")
        return f"{dt.strftime('%b %d, %Y')} – {time_label}"
    return str(raw)


def _parse_history_strategies(raw: str) -> list[str]:
    return [part.strip() for part in str(raw).split("+") if part.strip()]


def _queue_history_rerun(slug: str, record: dict[str, Any]) -> None:
    st.session_state[f"strategy_selection_{slug}"] = _parse_history_strategies(record["strategies"])
    st.session_state[f"investment_amount_{slug}"] = float(record["investment_amount"])
    st.session_state[f"history_rerun_pending_{slug}"] = True
    go_to_portfolio_view()


def render_portfolio_history(slug: str) -> None:
    records = load_recent_records(slug, 8)
    detail_key = f"history_detail_{slug}"
    detail_idx = st.session_state.get(detail_key)

    st.markdown(
        '<div class="portfolio-history-section"><h3 class="portfolio-history-title">Portfolio History</h3>',
        unsafe_allow_html=True,
    )

    if not records:
        st.markdown(
            '<p class="portfolio-history-empty">No portfolio runs yet. Generate a portfolio to build your history.</p></div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="portfolio-history-list">', unsafe_allow_html=True)
    for i, record in enumerate(reversed(records)):
        stamp = html.escape(_format_history_datetime(str(record.get("date", ""))))
        strategies = html.escape(str(record.get("strategies", "")))
        investment = float(record.get("investment_amount") or 0.0)
        portfolio_value = float(record.get("total_portfolio_value") or 0.0)
        st.markdown(
            "<div class='portfolio-history-card'>"
            f"<div class='portfolio-history-card-head'>{stamp}</div>"
            f"<div class='portfolio-history-card-line'><strong>Strategies:</strong> {strategies}</div>"
            f"<div class='portfolio-history-card-line'><strong>Investment:</strong> ${investment:,.0f}</div>"
            f"<div class='portfolio-history-card-line'><strong>Portfolio Value:</strong> ${portfolio_value:,.0f}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        rerun_col, details_col = st.columns(2, gap="small")
        with rerun_col:
            if st.button(
                "Re-run Portfolio",
                key=f"history_rerun_{slug}_{i}",
                type="secondary",
                use_container_width=True,
            ):
                _queue_history_rerun(slug, record)
                st.session_state.pop(detail_key, None)
                st.rerun()
        with details_col:
            if st.button(
                "View Details",
                key=f"history_details_{slug}_{i}",
                type="tertiary",
                use_container_width=True,
            ):
                st.session_state[detail_key] = i
                st.rerun()
        if detail_idx == i:
            return_pct = 0.0
            if investment > 0:
                return_pct = ((portfolio_value - investment) / investment) * 100.0
            return_delta = fmt_signed_dollar(portfolio_value - investment)
            return_pct_label = fmt_signed_pct(return_pct)
            st.markdown(
                "<div class='portfolio-history-detail'>"
                f"<strong>Run snapshot</strong><br>"
                f"Date: {stamp}<br>"
                f"Strategies: {strategies}<br>"
                f"Investment: ${investment:,.2f}<br>"
                f"Portfolio value: ${portfolio_value:,.2f}<br>"
                f"Return vs. investment: {html.escape(return_delta)} "
                f"({html.escape(return_pct_label)})"
                "</div>",
                unsafe_allow_html=True,
            )
    st.markdown("</div></div>", unsafe_allow_html=True)
