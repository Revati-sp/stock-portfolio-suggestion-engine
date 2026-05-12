"""
app.py — Stock Portfolio Suggestion Engine · Finance-grade Streamlit UI
"""
from __future__ import annotations

import html
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from ui.portfolio_history import render_portfolio_history
from ui.session_cache import clear_session_portfolio_cache
from ui.navigation import resolve_active_view
from ui.top_bar import render_portfolio_top_bar

from auth.users import (
    any_users_exist,
    register_user,
    sanitize_username,
    verify_password,
)
from auth.resume import portfolio_resume_token, verify_portfolio_resume
from database.connection import get_user_id
from database.repositories import (
    append_record,
    backfill_trend_from_holdings,
    ensure_daily_trend_file,
    ensure_history_file,
    load_current_holdings,
    load_daily_trend,
    save_current_holdings,
    upsert_daily_portfolio_value,
)
from core.portfolio import (
    build_portfolio_table,
    build_portfolio_table_from_saved,
    extract_priced_holdings,
    fetch_ticker_price,
    mark_to_market_holdings,
    portfolio_totals,
)
from core.risk import calculate_risk_level
from ui.strategy_selector import strategy_selector_widget


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ────────────────────────────────────────────────────────────
if "user_slug" not in st.session_state:
    st.session_state.user_slug = None
if "daily_auto_mtm_date" not in st.session_state:
    st.session_state.daily_auto_mtm_date = {}
if "allocation_df_by_user" not in st.session_state:
    st.session_state.allocation_df_by_user = {}


def _handle_top_nav_query_actions() -> None:
    if st.query_params.get("logout") != "1":
        return
    clear_session_portfolio_cache()
    st.session_state.user_slug = None
    st.session_state.pop("auth_panel", None)
    st.session_state.pop("app_view", None)
    if "logout" in st.query_params:
        del st.query_params["logout"]
    st.rerun()


_handle_top_nav_query_actions()


# ── Finance-grade global CSS ─────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ─── Palette ───────────────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    --gain: #16a34a;
    --loss: #dc2626;
    --accent: light-dark(#2563eb, #60a5fa);
    --bg-card: light-dark(#f8fafc, #1e293b);
    --bg-elevated: light-dark(#ffffff, #243044);
    --bg-subtle: light-dark(#f8fafc, #172033);
    --bg-muted: light-dark(#f1f5f9, #0f172a);
    --border: light-dark(#e2e8f0, #334155);
    --border-subtle: light-dark(#f1f5f9, #1e293b);
    --txt-hi: light-dark(#0f172a, #f1f5f9);
    --txt-mid: light-dark(#334155, #cbd5e1);
    --txt-lo: light-dark(#64748b, #94a3b8);
    --banner-bg: light-dark(#eff6ff, rgba(30, 58, 138, 0.28));
    --banner-border: light-dark(#bfdbfe, #1e40af);
    --banner-txt: light-dark(#1e40af, #bfdbfe);
    --disclaimer-icon-border: light-dark(#93c5fd, #60a5fa);
    --shadow-card: light-dark(rgba(15, 23, 42, 0.06), rgba(0, 0, 0, 0.28));
    --btn-generate-start: light-dark(#1e3a5f, #2d4d74);
    --btn-generate-end: light-dark(#0f172a, #111827);
    --btn-generate-hover-start: light-dark(#244a75, #3b5f8c);
    --btn-generate-hover-end: light-dark(#162032, #0b1220);
    --btn-generate-border: light-dark(rgba(148, 163, 184, 0.28), rgba(148, 163, 184, 0.35));
    --btn-generate-hover-border: light-dark(rgba(191, 219, 254, 0.38), rgba(147, 197, 253, 0.45));
    --btn-secondary-bg: light-dark(#ffffff, #1e293b);
    --btn-secondary-txt: light-dark(#334155, #e2e8f0);
    --btn-secondary-border: light-dark(#dbe4ee, #475569);
    --btn-secondary-hover-txt: light-dark(#1e3a5f, #bfdbfe);
    --btn-secondary-hover-border: light-dark(#bfd0e3, #64748b);
}
.app-title {
    font-size: 2.75rem;
    font-weight: 800;
    color: var(--txt-hi);
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.app-title--header { font-size: 2.25rem; }
.app-subtitle {
    color: var(--txt-lo);
    font-size: 0.95rem;
    margin-top: 8px;
}
.app-market-meta {
    text-align: right;
    line-height: 1.55;
    color: var(--txt-lo);
}
.app-market-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--txt-hi);
}
.app-market-time {
    color: var(--txt-lo);
    font-size: 0.73rem;
    font-family: ui-monospace, monospace;
}
.app-header-nav-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.05rem;
    padding: 0.38rem 0.72rem;
    border-radius: 999px;
    border: 1px solid var(--banner-border);
    background: var(--banner-bg);
    color: var(--banner-txt);
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1;
    text-decoration: none !important;
    white-space: nowrap;
    box-shadow: 0 1px 2px var(--shadow-card);
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}
.app-header-nav-link:hover {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--bg-elevated);
    transform: translateY(-1px);
}
.app-header-nav-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
.app-header-nav-group {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: nowrap;
    gap: 0.4rem;
    min-width: 0;
}
.app-header-toolbar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.9rem;
    flex-wrap: nowrap;
    width: 100%;
}
.app-header-toolbar-actions {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    flex-wrap: nowrap;
    min-width: 0;
}
.app-market-meta--toolbar {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.2rem;
    text-align: center;
    line-height: 1.25;
}
.app-market-meta--inline {
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    text-align: left;
    white-space: nowrap;
}
.app-market-meta--inline .app-market-label {
    line-height: 1.2;
}
.app-market-meta--inline .app-market-separator {
    color: var(--txt-lo);
    font-size: 0.82rem;
    line-height: 1;
}
.app-market-meta--toolbar .app-market-label {
    line-height: 1.2;
}
.app-market-meta--toolbar .app-market-time {
    display: block;
    line-height: 1.2;
    letter-spacing: 0.01em;
}
.app-market-meta--inline .app-market-time {
    display: inline;
}
.app-market-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
}
.app-header-nav-link--active {
    background: var(--banner-bg);
    border-color: var(--banner-border);
    color: var(--banner-txt);
    box-shadow: 0 1px 2px var(--shadow-card);
}
.app-header-nav-link--ghost {
    background: transparent;
    border-color: var(--border);
    color: var(--txt-mid);
    box-shadow: none;
}
.app-header-nav-link--ghost:hover {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--bg-elevated);
    transform: translateY(-1px);
}
.app-header-nav-icon {
    font-size: 0.95rem;
    line-height: 1;
}

/* ─── Auth gate ─────────────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) {
    background:
        radial-gradient(circle at top left, light-dark(rgba(37, 99, 235, 0.12), rgba(37, 99, 235, 0.18)), transparent 34%),
        radial-gradient(circle at bottom right, light-dark(rgba(15, 23, 42, 0.05), rgba(15, 23, 42, 0.42)), transparent 38%),
        var(--bg-muted) !important;
}
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stHeader"],
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stSidebar"],
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stToolbar"] {
    display: none !important;
}
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stMain"] > [data-testid="block-container"] {
    max-width: 1120px !important;
    padding-top: 2.25rem !important;
    padding-bottom: 2.5rem !important;
}
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stMain"] [data-testid="stMarkdownContainer"]:has(.portfolio-top-nav-wrap),
[data-testid="stAppViewContainer"]:has(.auth-screen-marker) [data-testid="stMain"] [data-testid="stMarkdownContainer"]:has(.app-market-meta--toolbar) {
    display: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
    gap: 2rem !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    display: flex !important;
    align-items: stretch !important;
    min-width: 0 !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] > [data-testid="column"] > [data-testid="stVerticalBlock"] {
    justify-content: flex-start !important;
    align-items: stretch !important;
    gap: 1rem !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child > [data-testid="stVerticalBlock"] {
    padding-top: 0.35rem !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child > [data-testid="stVerticalBlock"] {
    padding-top: 0.35rem !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) .auth-card-column-marker {
    display: none !important;
}
[data-testid="stAppViewContainer"]:has(.auth-layout-marker) .auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] {
    margin-top: 0 !important;
}
@media (max-width: 900px) {
    [data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: 1.5rem !important;
    }
    [data-testid="stAppViewContainer"]:has(.auth-layout-marker) [data-testid="stMarkdownContainer"]:has(.auth-layout-marker) + [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 100% !important;
    }
}
.auth-screen-marker,
.auth-layout-marker {
    display: none !important;
}
.auth-hero {
    padding: 0.35rem 0.5rem 0.35rem 0;
}
.auth-hero .app-title {
    font-size: clamp(2.1rem, 4vw, 2.85rem);
    margin-top: 0.85rem;
}
.auth-hero .app-subtitle {
    margin-top: 0.75rem;
    margin-bottom: 1.35rem;
    max-width: 34rem;
    line-height: 1.55;
}
.auth-eyebrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.32rem 0.78rem;
    border-radius: 999px;
    border: 1px solid var(--banner-border);
    background: var(--banner-bg);
    color: var(--banner-txt);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.auth-callout {
    margin: 0 0 1rem;
    padding: 0.85rem 0.95rem;
    border-radius: 14px;
    border: 1px solid var(--banner-border);
    background: var(--banner-bg);
    color: var(--banner-txt);
    font-size: 0.84rem;
    line-height: 1.5;
}
.auth-feature-grid {
    display: grid;
    gap: 0.8rem;
    margin: 0;
}
.auth-feature-card {
    display: flex;
    align-items: flex-start;
    gap: 0.85rem;
    padding: 0.95rem 1rem;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-elevated) 88%, transparent);
    box-shadow: 0 10px 24px var(--shadow-card);
}
.auth-feature-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.35rem;
    height: 2.35rem;
    border-radius: 12px;
    background: var(--banner-bg);
    border: 1px solid var(--banner-border);
    font-size: 1.05rem;
    flex: 0 0 auto;
}
.auth-feature-copy strong {
    display: block;
    color: var(--txt-hi);
    font-size: 0.92rem;
    margin-bottom: 0.18rem;
}
.auth-feature-copy span {
    color: var(--txt-mid);
    font-size: 0.84rem;
    line-height: 1.45;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    border-radius: 22px !important;
    box-shadow: 0 24px 60px var(--shadow-card) !important;
    overflow: hidden !important;
    padding-top: 0.35rem !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stSegmentedControl"] {
    margin-bottom: 0.35rem !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stSegmentedControl"] button {
    min-height: 2.45rem !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stForm"] {
    margin-top: 0.15rem !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] p {
    margin-bottom: 0.35rem !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"] p {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: var(--txt-mid) !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] input {
    min-height: 2.65rem !important;
    border-radius: 12px !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stFormSubmitButton"] button {
    min-height: 2.75rem !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
}
.auth-card-anchor + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] p {
    color: var(--txt-lo) !important;
    font-size: 0.78rem !important;
    line-height: 1.45 !important;
}
.auth-footnote {
    margin-top: 1rem;
    color: var(--txt-lo);
    font-size: 0.76rem;
    line-height: 1.45;
    text-align: center;
}

/* ─── Section labels ────────────────────────────────────────────────────── */
.section-label {
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--txt-lo);
    margin: 1.4rem 0 0.5rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
}
.portfolio-section-label {
    margin-bottom: 1.5rem;
}

/* ─── KPI metric tiles ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.5rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricLabel"] > div {
    color: var(--txt-lo) !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] > div {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: var(--txt-hi) !important;
    letter-spacing: -0.025em !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricDelta"] svg { display: none !important; }
[data-testid="stMetricDelta"] > div {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    margin-top: 3px !important;
}

/* ─── Saved-portfolio info banner ───────────────────────────────────────── */
.saved-banner {
    background: var(--banner-bg);
    border: 1px solid var(--banner-border);
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-size: 0.82rem;
    color: var(--banner-txt);
    margin-bottom: 0.8rem;
}

/* ─── Holdings dashboard ────────────────────────────────────────────────── */
.holdings-dashboard {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 1.5rem;
    align-items: start;
    margin: 0.25rem 0 1.25rem 0;
}
.holdings-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 1rem;
    box-shadow: 0 1px 3px var(--shadow-card), 0 8px 24px var(--shadow-card);
    padding: 1.5rem;
    overflow: hidden;
}
.holdings-card--table { grid-column: span 9; }
.holdings-card--summary {
    grid-column: span 3;
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
    padding: 1.35rem 1.4rem 1.25rem;
    border-radius: 1rem;
    background:
        linear-gradient(180deg, color-mix(in srgb, var(--bg-elevated) 92%, var(--accent) 8%), var(--bg-elevated));
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
}
.holdings-card--summary .holdings-card-title {
    margin: 0;
}
.holdings-summary-head {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}
.holdings-summary-eyebrow {
    margin: 0;
    color: var(--txt-lo);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.holdings-summary-hero {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 1rem 1.05rem;
    border: 1px solid var(--border);
    border-radius: 0.9rem;
    background: color-mix(in srgb, var(--bg-subtle) 82%, var(--bg-elevated));
    box-shadow: inset 0 1px 0 color-mix(in srgb, #ffffff 55%, transparent);
}
.holdings-summary-hero-label {
    color: var(--txt-lo);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.holdings-summary-hero-value {
    color: var(--txt-hi);
    font-size: clamp(1.65rem, 2.4vw, 2rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.05;
}
.holdings-summary-hero-change {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem;
}
.holdings-summary-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.55rem;
    border-radius: 999px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.2;
}
.holdings-summary-chip.holdings-positive {
    background: light-dark(#ecfdf3, rgba(22, 163, 74, 0.16));
    border-color: light-dark(#bbf7d0, rgba(34, 197, 94, 0.35));
}
.holdings-summary-chip.holdings-negative {
    background: light-dark(#fef2f2, rgba(220, 38, 38, 0.16));
    border-color: light-dark(#fecaca, rgba(248, 113, 113, 0.35));
}
.holdings-summary-chip-caption {
    color: var(--txt-lo);
    font-size: 0.76rem;
    font-weight: 500;
}
.holdings-summary-metrics {
    display: grid;
    gap: 0.55rem;
    margin: 0;
}
.holdings-summary-metric {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.72rem 0.85rem;
    border: 1px solid var(--border-subtle);
    border-radius: 0.75rem;
    background: var(--bg-elevated);
}
.holdings-summary-metric dt {
    margin: 0;
    color: var(--txt-lo);
    font-size: 0.8rem;
    font-weight: 600;
}
.holdings-summary-metric dd {
    margin: 0;
    color: var(--txt-hi);
    font-size: 0.92rem;
    font-weight: 700;
    text-align: right;
    font-variant-numeric: tabular-nums;
}
.holdings-summary-metric dd.holdings-positive,
.holdings-summary-metric dd.holdings-negative {
    font-weight: 800;
}
.holdings-summary-risk-panel {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    padding: 0.95rem 1rem;
    border: 1px solid var(--border);
    border-radius: 0.85rem;
    background: var(--bg-subtle);
}
.holdings-summary-risk-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
}
.holdings-summary-risk-title {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--txt-mid);
    font-size: 0.8rem;
    font-weight: 700;
}
.holdings-summary-risk-meter {
    width: 100%;
    height: 0.45rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--border) 70%, transparent);
    overflow: hidden;
}
.holdings-summary-risk-meter > span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--gain), #f59e0b 58%, var(--loss));
}
.holdings-summary-risk-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    color: var(--txt-lo);
    font-size: 0.74rem;
    font-weight: 500;
}
.holdings-summary-risk-foot strong {
    color: var(--txt-mid);
    font-weight: 700;
}
@media (max-width: 900px) {
    .holdings-dashboard { grid-template-columns: 1fr; }
    .holdings-card--table,
    .holdings-card--summary { grid-column: span 1; }
}
.holdings-card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--txt-hi);
    margin: 0 0 1rem 0;
}
.holdings-table-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}
.holdings-table {
    width: 100%;
    min-width: 1020px;
    table-layout: fixed;
    border-collapse: collapse;
    font-size: 0.875rem;
}
.holdings-table th {
    text-align: left;
    background: var(--bg-subtle);
    color: var(--txt-lo);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.75rem 1rem;
    border: none;
    border-bottom: 1px solid var(--border);
}
.holdings-table th.holdings-th--right {
    text-align: right;
}
.holdings-table tbody tr {
    border-bottom: 1px solid var(--border-subtle);
}
.holdings-table tbody tr:hover {
    background: var(--bg-card);
}
.holdings-table td {
    padding: 1rem;
    border: none;
    vertical-align: middle;
    color: var(--txt-hi);
}
.holdings-table td.holdings-td--right {
    text-align: right;
}
.holdings-num {
    font-variant-numeric: tabular-nums;
}
.holdings-symbol-badge {
    width: 3rem;
    height: 3rem;
    border-radius: 0.5rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-weight: 700;
    font-size: 0.7rem;
    letter-spacing: -0.02em;
}
.holdings-name {
    font-weight: 500;
    color: var(--txt-mid);
    line-height: 1.35;
}
.holdings-alloc-pct {
    font-weight: 600;
    color: var(--txt-hi);
}
.holdings-alloc-bar {
    width: 7rem;
    height: 0.5rem;
    background: var(--border);
    border-radius: 999px;
    overflow: hidden;
    margin-top: 0.35rem;
}
.holdings-alloc-bar > span {
    display: block;
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
}
.holdings-money { font-weight: 700; color: var(--txt-hi); }
.holdings-price-sub,
.holdings-summary-change {
    font-size: 0.74rem;
    font-weight: 600;
    margin-top: 0.15rem;
}
.holdings-positive { color: var(--gain); }
.holdings-negative { color: var(--loss); }
.holdings-table-footer {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    background: var(--bg-subtle);
    border-radius: 0.75rem;
    padding: 1rem;
    margin-top: 1rem;
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--txt-hi);
}
.holdings-table-footer-item {
    font-variant-numeric: tabular-nums;
}
.holdings-summary-list {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--border);
}
.holdings-summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 0;
    font-size: 0.875rem;
    line-height: 1.35;
}
.holdings-summary-row + .holdings-summary-row {
    border-top: 1px solid var(--border);
}
.holdings-summary-label {
    flex: 1 1 auto;
    min-width: 0;
    color: var(--txt-lo);
    font-weight: 500;
}
.holdings-summary-value {
    flex: 0 0 auto;
    margin-left: auto;
    color: var(--txt-hi);
    font-weight: 600;
    text-align: right;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}
.holdings-summary-value.holdings-positive { color: var(--gain); }
.holdings-summary-value.holdings-negative { color: var(--loss); }
.holdings-summary-row--risk {
    border-top: 1px solid var(--border);
    margin-top: 0.15rem;
    padding-top: 0.85rem;
}
.holdings-summary-label--risk {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
}
.holdings-risk-info {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.1rem;
    height: 1.1rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--txt-lo);
    font-size: 0.68rem;
    font-weight: 700;
    line-height: 1;
    cursor: help;
}
.holdings-risk-info::after {
    content: attr(data-tip);
    position: absolute;
    left: 50%;
    bottom: calc(100% + 0.45rem);
    transform: translateX(-50%);
    width: max-content;
    max-width: 14rem;
    padding: 0.45rem 0.55rem;
    border-radius: 0.45rem;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--txt-mid);
    font-size: 0.68rem;
    font-weight: 500;
    line-height: 1.35;
    box-shadow: 0 4px 14px var(--shadow-card);
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: opacity 0.15s ease, visibility 0.15s ease;
    z-index: 2;
}
.holdings-risk-info:hover::after,
.holdings-risk-info:focus-visible::after {
    opacity: 1;
    visibility: visible;
}
.holdings-summary-value--risk {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.2rem;
    white-space: nowrap;
}
.holdings-risk-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.2rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.2;
}
.holdings-risk-badge--low {
    background: light-dark(#dcfce7, rgba(22, 101, 52, 0.28));
    color: light-dark(#15803d, #86efac);
}
.holdings-risk-badge--moderate {
    background: light-dark(#ffedd5, rgba(194, 65, 12, 0.28));
    color: light-dark(#c2410c, #fdba74);
}
.holdings-risk-badge--high {
    background: light-dark(#fee2e2, rgba(185, 28, 28, 0.28));
    color: light-dark(#dc2626, #fca5a5);
}
.holdings-risk-badge--na {
    background: light-dark(#f1f5f9, rgba(100, 116, 139, 0.22));
    color: light-dark(#475569, #cbd5e1);
}
.holdings-risk-score {
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--txt-lo);
    line-height: 1.2;
}

/* ─── Dashboard charts ──────────────────────────────────────────────────── */
.dashboard-anchor + [data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
    gap: 1.5rem !important;
}
.dashboard-anchor + [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 1rem;
    box-shadow: 0 1px 2px var(--shadow-card);
    padding: 1.5rem;
    min-height: 100%;
}
.dashboard-anchor + [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
    flex: 2.25 1 0 !important;
}
.dashboard-anchor + [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child {
    flex: 1 1 0 !important;
}
@media (max-width: 900px) {
    .dashboard-anchor + [data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
    }
    .dashboard-anchor + [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 auto !important;
        width: 100% !important;
        max-width: 100% !important;
    }
}
.dashboard-chart-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--txt-hi);
    margin: 0 0 0.75rem 0;
}
.dashboard-anchor + [data-testid="stHorizontalBlock"] [data-testid="stPlotlyChart"] {
    margin-top: 0 !important;
}
.dashboard-disclaimer {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    margin-top: 1.5rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--banner-border);
    border-radius: 0.5rem;
    background: var(--banner-bg);
    color: var(--banner-txt);
    font-size: 0.84rem;
    line-height: 1.45;
}
.dashboard-disclaimer-icon {
    flex: 0 0 auto;
    width: 1.1rem;
    height: 1.1rem;
    border-radius: 999px;
    border: 1px solid var(--disclaimer-icon-border);
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1.1rem;
    text-align: center;
}
.dashboard-chart-note {
    margin-top: 0.55rem;
    color: var(--txt-lo);
    font-size: 0.78rem;
    line-height: 1.45;
}
.portfolio-history-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 1.75rem;
    max-width: 1120px;
}
.portfolio-history-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--txt-hi);
    margin: 0;
}
.portfolio-history-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.portfolio-history-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 0.9rem;
    box-shadow: 0 1px 2px var(--shadow-card);
    padding: 1rem 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
}
.portfolio-history-card-head {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--txt-hi);
    line-height: 1.35;
}
.portfolio-history-card-line {
    color: var(--txt-mid);
    font-size: 0.86rem;
    line-height: 1.45;
}
.portfolio-history-card-line strong {
    color: var(--txt-hi);
    font-weight: 600;
}
.portfolio-history-detail {
    margin-top: 0.15rem;
    padding: 0.85rem 0.95rem;
    border-radius: 0.75rem;
    border: 1px solid var(--border-subtle);
    background: var(--bg-subtle);
    color: var(--txt-mid);
    font-size: 0.84rem;
    line-height: 1.5;
}
.portfolio-history-empty {
    color: var(--txt-lo);
    font-size: 0.86rem;
    line-height: 1.45;
    padding: 0.35rem 0;
}
.portfolio-history-card + [data-testid="stHorizontalBlock"] {
    margin-top: 0.15rem !important;
    gap: 0.65rem !important;
}
.portfolio-history-card + [data-testid="stHorizontalBlock"] [data-testid="stButton"] button {
    min-height: 2.15rem !important;
    padding: 0.35rem 0.85rem !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    border-radius: 0.65rem !important;
}

/* ─── Primary actions (generate, refresh) ───────────────────────────────── */
section[data-testid="stMain"] div[data-testid="stButton"] button {
    min-height: 2.75rem !important;
    box-sizing: border-box !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1.15 !important;
    font-size: 0.875rem !important;
}

/* ─── Build panel ───────────────────────────────────────────────────────── */
.build-panel {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.1rem 1.25rem 1.25rem;
    margin-bottom: 0.5rem;
}
.build-panel .tile-note { margin-top: 0.15rem; }
.build-panel [data-testid="stCaptionContainer"] p {
    color: var(--txt-lo) !important;
    font-size: 0.78rem !important;
    margin-bottom: 0.35rem !important;
}

/* ─── Create portfolio row ──────────────────────────────────────────────── */
div.portfolio-builder-anchor {
    display: none !important;
}
section[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-elevated) !important;
    border-color: var(--border) !important;
}
.portfolio-builder-anchor + [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.1rem 1.25rem 1.25rem;
    margin-bottom: 0.5rem;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
    justify-content: flex-start !important;
    gap: 0.75rem !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
    flex: 0 0 11rem !important;
    max-width: 11rem;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
    flex: 1 1 0 !important;
    min-width: 0;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > [data-testid="stVerticalBlock"] {
    align-items: stretch !important;
    gap: 0 !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
    justify-content: flex-start !important;
    width: 100% !important;
    gap: 0.75rem !important;
    margin-top: 0 !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
    flex: 1 1 0% !important;
    width: auto !important;
    min-width: 0 !important;
    max-width: none !important;
}
div.portfolio-builder-actions {
    display: none !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) {
    flex: 0 0 11rem !important;
    width: 11rem !important;
    max-width: 11rem !important;
    min-width: 11rem !important;
    margin-top: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding-top: 2.85rem !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) [data-testid="stVerticalBlock"] {
    gap: 0.85rem !important;
    transform: none !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stCustomComponentV1"] {
    width: 100% !important;
    max-width: 100% !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stCustomComponentV1"] iframe {
    width: 100% !important;
    max-width: 100% !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stNumberInput"] input[data-testid="stNumberInputField"] {
    max-width: 12.5rem;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    padding: 0.55rem 0.75rem !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"] p {
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    color: var(--txt-hi) !important;
    margin: 0 !important;
    line-height: 1.25rem !important;
    min-height: 1.25rem !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stNumberInput"] {
    margin-top: 1rem !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] .build-min-note {
    margin-top: 0.4rem;
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--accent);
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="primary"] {
    min-height: 3.25rem !important;
    border-radius: 12px !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.01em !important;
    color: #f8fafc !important;
    background-color: var(--btn-generate-end) !important;
    background-image: linear-gradient(165deg, var(--btn-generate-start) 0%, var(--btn-generate-end) 100%) !important;
    border: 1px solid var(--btn-generate-border) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.1), 0 6px 18px rgba(15, 23, 42, 0.14) !important;
    transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease, border-color 0.16s ease !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="primary"]:hover {
    color: #ffffff !important;
    background-color: var(--btn-generate-hover-end) !important;
    background-image: linear-gradient(165deg, var(--btn-generate-hover-start) 0%, var(--btn-generate-hover-end) 100%) !important;
    border-color: var(--btn-generate-hover-border) !important;
    box-shadow: 0 2px 4px rgba(15, 23, 42, 0.12), 0 10px 24px rgba(15, 23, 42, 0.16) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="primary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12), 0 4px 10px rgba(15, 23, 42, 0.12) !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="primary"] p,
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="primary"] span {
    color: inherit !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="secondary"] {
    margin-top: 0 !important;
    border-radius: 12px !important;
    color: var(--btn-secondary-txt) !important;
    background: var(--btn-secondary-bg) !important;
    border: 1px solid var(--btn-secondary-border) !important;
    box-shadow: 0 1px 2px var(--shadow-card) !important;
    transition: border-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"]:has(.portfolio-builder-actions) button[kind="secondary"]:hover {
    color: var(--btn-secondary-hover-txt) !important;
    border-color: var(--btn-secondary-hover-border) !important;
    box-shadow: 0 2px 6px var(--shadow-card) !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCustomComponentV1"] {
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCustomComponentV1"] iframe {
    width: auto !important;
    max-width: 100%;
    display: block;
}
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCustomComponentV1"] [data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCustomComponentV1"] label,
[data-testid="stMarkdownContainer"]:has(.portfolio-builder-anchor) + [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCustomComponentV1"] [data-testid="stMarkdownContainer"] {
    display: none !important;
}
/* ─── Top bar ───────────────────────────────────────────────────────────── */
.portfolio-top-nav-wrap {
    width: 100%;
    margin: 0 0 1rem;
    border-bottom: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-elevated) 92%, transparent);
    box-sizing: border-box;
}
section[data-testid="stMain"] [data-testid="stElementContainer"]:has(.portfolio-top-nav-wrap),
section[data-testid="stMain"] [data-testid="stMarkdownContainer"]:has(.portfolio-top-nav-wrap),
section[data-testid="stMain"] [data-testid="stElementContainer"]:has(.portfolio-section-label),
section[data-testid="stMain"] [data-testid="stMarkdownContainer"]:has(.portfolio-section-label) {
    padding-left: 0 !important;
    margin-left: 0 !important;
}
.portfolio-top-nav {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    column-gap: 1rem;
    width: 100%;
    min-height: 3.5rem;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}
.portfolio-top-nav__zone--left {
    justify-self: start;
}
.portfolio-top-nav__zone--right {
    justify-self: end;
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: nowrap;
}
.portfolio-top-nav__title {
    margin: 0;
    font-size: clamp(1.35rem, 2.1vw, 1.75rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.1;
    color: var(--txt-hi);
    white-space: nowrap;
}
.portfolio-top-nav__title--link {
    display: inline-block;
    text-decoration: none;
    color: inherit;
}
.portfolio-top-nav__title--link:hover {
    color: var(--accent);
}
.portfolio-top-nav__pill {
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.05rem;
    min-width: 0;
    padding: 0.38rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--txt-mid);
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
    text-decoration: none;
}
.portfolio-top-nav__pill:hover {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--bg-elevated);
}
.portfolio-top-nav__pill--active {
    border-color: var(--banner-border);
    background: var(--banner-bg);
    color: var(--banner-txt);
    box-shadow: 0 1px 2px var(--shadow-card);
}
.portfolio-top-nav__pill--active:hover {
    color: var(--banner-txt);
    border-color: var(--banner-border);
    background: var(--banner-bg);
}
@media (max-width: 900px) {
    .portfolio-top-nav {
        grid-template-columns: 1fr;
        row-gap: 0.75rem;
        padding: 0 16px;
    }
    .portfolio-top-nav__zone--left,
    .portfolio-top-nav__zone--right {
        justify-self: center;
    }
    .portfolio-top-nav__zone--right {
        flex-wrap: wrap;
        justify-content: center;
    }
    .app-market-meta--inline {
        white-space: normal;
        flex-wrap: wrap;
        justify-content: center;
    }
}

/* ─── Log-out text link ─────────────────────────────────────────────────── */
section[data-testid="stMain"] button[kind="tertiary"] {
    min-height: unset !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: var(--txt-lo) !important;
    text-decoration: underline !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
section[data-testid="stMain"] button[kind="tertiary"]:hover {
    color: var(--accent) !important;
    background: transparent !important;
}

/* ─── Number-input steppers ─────────────────────────────────────────────── */
[data-testid="stElementContainer"]:has(input[data-testid="stNumberInputField"]) button {
    min-height: unset !important;
    height: 100% !important;
    max-height: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 0 !important;
    padding: 0 !important;
    font-size: inherit !important;
    box-sizing: border-box !important;
}
[data-testid="stElementContainer"]:has(input[data-testid="stNumberInputField"]) button svg {
    display: block !important;
    margin: auto !important;
    flex-shrink: 0 !important;
}

.tile-note { color: var(--txt-lo); font-size: 0.81rem; margin-top: -5px; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"<style>{(Path(__file__).resolve().parent / 'ui' / 'portfolio_theme.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _is_dark_theme() -> bool:
    return st.context.theme.type == "dark"


def _chart_palette() -> dict[str, str]:
    dark = _is_dark_theme()
    return {
        "text_muted": "#94a3b8" if dark else "#64748b",
        "text_high": "#f1f5f9" if dark else "#0f172a",
        "text_mid": "#cbd5e1" if dark else "#334155",
        "grid": "#334155" if dark else "#f1f5f9",
        "axis": "#475569" if dark else "#e2e8f0",
        "marker_ring": "#1e293b" if dark else "#ffffff",
        "line": "#60a5fa" if dark else "#2563eb",
        "fill": "rgba(96, 165, 250, 0.18)" if dark else "rgba(37, 99, 235, 0.14)",
        "gain": "#4ade80" if dark else "#16a34a",
    }


def validate_inputs(amount: float, strategies: list[str]) -> list[str]:
    issues: list[str] = []
    if amount < 5000:
        issues.append("Investment amount must be at least **$5,000**.")
    if len(strategies) < 1 or len(strategies) > 2:
        issues.append("Please pick **either one or exactly two** investment strategies.")
    return issues


_PRESENT_RENAME = {
    "Ticker": "Ticker",
    "Strategy": "Strategy",
    "Allocation (USD)": "Allocation",
    "Purchase Price (USD)": "Purchase Price",
    "Current Price (USD)": "Current Price",
    "Shares": "Shares",
    "Current Value (USD)": "Current Value",
    "Day Gain/Loss (USD)": "Day Gain/Loss",
    "Total Gain/Loss (USD)": "Gain/Loss",
}

_TICKER_DISPLAY_NAMES: dict[str, str] = {
    "VTI": "Vanguard Total Stock Market ETF",
    "IXUS": "iShares Core MSCI Total Intl Stk ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com Inc.",
    "TSLA": "Tesla Inc.",
    "AAPL": "Apple Inc.",
    "ADBE": "Adobe Inc.",
    "MSFT": "Microsoft Corporation",
    "COST": "Costco Wholesale Corporation",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble Co.",
    "BRK-B": "Berkshire Hathaway Inc. Class B",
    "JPM": "JPMorgan Chase & Co.",
    "XOM": "Exxon Mobil Corporation",
}

_TICKER_BADGE_COLORS: dict[str, str] = {
    "VTI": "#9f1239",
    "IXUS": "#1d4ed8",
    "BND": "#15803d",
    "NVDA": "#7c3aed",
    "AMZN": "#ea580c",
    "TSLA": "#dc2626",
    "AAPL": "#0f172a",
    "ADBE": "#c026d3",
    "MSFT": "#0369a1",
    "COST": "#0d9488",
    "JNJ": "#be123c",
    "PG": "#4f46e5",
    "BRK-B": "#57534e",
    "JPM": "#1e3a8a",
    "XOM": "#b45309",
}

_BADGE_FALLBACK_COLORS = (
    "#334155",
    "#0f766e",
    "#7c2d12",
    "#4338ca",
    "#be185d",
    "#047857",
)


def portfolio_snapshot_key(slug: str) -> str:
    return f"portfolio_snapshot_{slug}"


def _news_app_base_url() -> str:
    return os.environ.get("NEWS_APP_URL", "http://127.0.0.1:3000").rstrip("/")


def _portfolio_app_url() -> str:
    configured = os.environ.get("PORTFOLIO_APP_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    try:
        headers = st.context.headers
        host = headers.get("Host") or headers.get("host")
        if host:
            forwarded_proto = headers.get("X-Forwarded-Proto") or headers.get("x-forwarded-proto")
            scheme = "https" if (forwarded_proto or "").lower() == "https" else "http"
            return f"{scheme}://{host}".rstrip("/")
    except Exception:
        pass
    try:
        import streamlit.config as stconfig

        port = int(stconfig.get_option("server.port"))
        address = (stconfig.get_option("browser.serverAddress") or "127.0.0.1").strip() or "127.0.0.1"
        return f"http://{address}:{port}"
    except Exception:
        pass
    return "http://127.0.0.1:8501"


def _portfolio_return_query(slug: str) -> dict[str, str]:
    return {
        "portfolio": _portfolio_app_url(),
        "user": slug,
        "resume": portfolio_resume_token(slug),
    }


def try_restore_session_from_return_link() -> None:
    if st.session_state.user_slug:
        return

    raw_user = st.query_params.get("user")
    resume = st.query_params.get("resume")
    if not raw_user or not resume:
        return

    slug = sanitize_username(raw_user)
    if not slug or not verify_portfolio_resume(slug, resume):
        return
    if get_user_id(slug) is None:
        return

    st.session_state.user_slug = slug
    for key in ("user", "resume"):
        if key in st.query_params:
            del st.query_params[key]
    st.rerun()


def _news_url_for_user(slug: str) -> str:
    tickers: list[str] = []
    snapshot = st.session_state.get(portfolio_snapshot_key(slug))
    if snapshot:
        present = snapshot.get("present")
        if present is not None and not present.empty and "Ticker" in present.columns:
            tickers = sorted({str(ticker) for ticker in present["Ticker"].tolist() if str(ticker)})
    if not tickers:
        disk = load_current_holdings(slug)
        if disk and disk.get("holdings"):
            tickers = sorted({str(holding[0]) for holding in disk["holdings"] if holding and len(holding) >= 1})
    if not tickers:
        tickers = ["VTI", "AAPL", "TSLA", "AMZN"]
    return f"{_news_app_base_url()}/news?{urlencode({'tickers': ','.join(tickers), **_portfolio_return_query(slug)})}"



def hydrate_portfolio_from_disk(slug: str) -> None:
    sk = portfolio_snapshot_key(slug)
    if sk in st.session_state:
        return
    disk = load_current_holdings(slug)
    if not disk or not disk.get("holdings"):
        return
    with st.spinner("Loading your saved portfolio…"):
        table_df, price_warnings = build_portfolio_table_from_saved(disk, quote_fn=fetch_ticker_price)
    inv = float(disk["investment_amount"])
    strats = list(disk["strategies"])
    total_invested, current_value, total_gl = portfolio_totals(table_df, inv)
    present = table_df.rename(columns=_PRESENT_RENAME)
    st.session_state[sk] = {
        "present": present,
        "strategies": strats,
        "investment_amount": inv,
        "totals": (total_invested, current_value, total_gl),
        "price_warnings": price_warnings,
        "from_disk": True,
    }
    st.session_state.allocation_df_by_user[slug] = present[["Ticker", "Strategy", "Allocation"]].copy()


def _fmt_signed_dollar(v: float) -> str:
    """Format a dollar value with explicit +/- sign and $ prefix."""
    if v >= 0:
        return f"+${v:,.2f}"
    return f"-${abs(v):,.2f}"


def _ticker_badge_color(sym: str) -> str:
    if sym in _TICKER_BADGE_COLORS:
        return _TICKER_BADGE_COLORS[sym]
    return _BADGE_FALLBACK_COLORS[sum(ord(c) for c in sym) % len(_BADGE_FALLBACK_COLORS)]


def _ticker_display_name(sym: str) -> str:
    return _TICKER_DISPLAY_NAMES.get(sym, sym)


def _signed_class(value: float | None) -> str:
    if value is None:
        return ""
    if value > 0:
        return "holdings-positive"
    if value < 0:
        return "holdings-negative"
    return ""


def _fmt_signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def _fmt_money(value: object, *, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    if signed:
        return _fmt_signed_dollar(amount)
    return f"${amount:,.2f}"


def _row_daily_pct(
    price: float | None,
    shares: float | None,
    day_gl: float | None,
    current_value: float | None,
) -> float | None:
    if day_gl is None or (isinstance(day_gl, float) and pd.isna(day_gl)):
        return None
    if shares is not None and not pd.isna(shares) and shares > 0 and price is not None and not pd.isna(price):
        prev_close = price - (day_gl / shares)
        if prev_close > 0:
            return (price - prev_close) / prev_close * 100
    if current_value is not None and not pd.isna(current_value):
        prev_value = current_value - day_gl
        if prev_value > 0:
            return day_gl / prev_value * 100
    return None


def _row_gain_loss(row: pd.Series) -> float | None:
    if "Gain/Loss" in row.index:
        gain_loss = row["Gain/Loss"]
        if gain_loss is not None and not pd.isna(gain_loss):
            return float(gain_loss)
    alloc = row.get("Allocation")
    value = row.get("Current Value")
    if alloc is None or value is None or pd.isna(alloc) or pd.isna(value):
        return None
    return float(value) - float(alloc)


def _build_holdings_dashboard_html(
    present: pd.DataFrame,
    *,
    total_invested: float,
    current_value: float,
    total_gl: float,
    investment_amount: float,
    strategies: list[str],
) -> str:
    alloc_series = pd.to_numeric(present["Allocation"], errors="coerce").fillna(0.0)
    total_allocated = float(alloc_series.sum())
    allocation_denominator = total_allocated if total_allocated > 0 else float(investment_amount or total_invested)

    day_series = (
        pd.to_numeric(present["Day Gain/Loss"], errors="coerce")
        if "Day Gain/Loss" in present.columns
        else pd.Series(dtype=float)
    )
    todays_change = float(day_series.fillna(0.0).sum()) if not day_series.empty else 0.0
    todays_change_pct = (todays_change / current_value * 100) if current_value else 0.0
    total_return_pct = (total_gl / total_invested * 100) if total_invested else 0.0
    cash_balance = max(0.0, float(investment_amount) - total_allocated)
    risk_holdings: list[dict[str, object]] = []
    for _, row in present.iterrows():
        value = row.get("Current Value")
        if value is None or pd.isna(value):
            continue
        try:
            current_value = float(value)
        except (TypeError, ValueError):
            continue
        if current_value <= 0:
            continue
        risk_holdings.append({"ticker": str(row["Ticker"]), "currentValue": current_value})
    risk = calculate_risk_level(risk_holdings)

    table_rows: list[str] = []
    for _, row in present.iterrows():
        sym = str(row["Ticker"])
        alloc = float(row["Allocation"]) if row.get("Allocation") is not None and not pd.isna(row["Allocation"]) else 0.0
        alloc_pct = (alloc / allocation_denominator * 100) if allocation_denominator else 0.0
        price = row.get("Current Price")
        shares = row.get("Shares")
        value = row.get("Current Value")
        day_gl = row.get("Day Gain/Loss") if "Day Gain/Loss" in row.index else None
        row_gl = _row_gain_loss(row)
        daily_pct = _row_daily_pct(
            float(price) if price is not None and not pd.isna(price) else None,
            float(shares) if shares is not None and not pd.isna(shares) else None,
            float(day_gl) if day_gl is not None and not pd.isna(day_gl) else None,
            float(value) if value is not None and not pd.isna(value) else None,
        )
        price_cell = (
            f"<span class='holdings-money holdings-num'>{html.escape(_fmt_money(price))}</span>"
        )
        if daily_pct is not None:
            price_cell += (
                f"<div class='holdings-price-sub holdings-num {_signed_class(daily_pct)}'>"
                f"{html.escape(_fmt_signed_pct(daily_pct))}</div>"
            )
        shares_cell = (
            f"<span class='holdings-num'>{html.escape(f'{float(shares):,.2f}')}</span>"
            if shares is not None and not pd.isna(shares)
            else "—"
        )
        value_class = _signed_class(row_gl)
        table_rows.append(
            "<tr>"
            f"<td class='holdings-td--symbol'><span class='holdings-symbol-badge' style='background:{_ticker_badge_color(sym)};'>"
            f"{html.escape(sym)}</span></td>"
            f"<td class='holdings-td--name'><div class='holdings-name'>{html.escape(_ticker_display_name(sym))}</div></td>"
            f"<td class='holdings-td--alloc'><div class='holdings-alloc-pct holdings-num'>{alloc_pct:.2f}%</div>"
            f"<div class='holdings-alloc-bar'><span style='width:{min(alloc_pct, 100):.2f}%;'></span></div></td>"
            f"<td class='holdings-td--right'><span class='holdings-money holdings-num'>{html.escape(_fmt_money(alloc))}</span></td>"
            f"<td class='holdings-td--right'>{price_cell}</td>"
            f"<td class='holdings-td--right'>{shares_cell}</td>"
            f"<td class='holdings-td--right'><span class='holdings-money holdings-num {value_class}'>"
            f"{html.escape(_fmt_money(value))}</span></td>"
            "</tr>"
        )

    total_alloc_pct = (total_allocated / allocation_denominator * 100) if allocation_denominator else 0.0
    portfolio_value_class = _signed_class(total_gl)

    todays_class = _signed_class(todays_change)
    total_return_class = _signed_class(total_gl)
    risk_score_pct = (
        min(max((risk.score / 5.0) * 100.0, 0.0), 100.0) if risk.level != "N/A" else 0.0
    )
    risk_score_text = f"{risk.score:.2f} / 5" if risk.level != "N/A" else "—"
    risk_tip = (
        "Risk is calculated using the weighted average risk of selected stocks/ETFs "
        "based on portfolio value."
    )
    summary_html = (
        "<div class='holdings-summary-hero'>"
        "<div class='holdings-summary-hero-label'>Current value</div>"
        f"<div class='holdings-summary-hero-value holdings-num'>{html.escape(_fmt_money(current_value))}</div>"
        "<div class='holdings-summary-hero-change'>"
        f"<span class='holdings-summary-chip holdings-num {html.escape(todays_class)}'>"
        f"{html.escape(_fmt_signed_dollar(todays_change))} "
        f"({html.escape(_fmt_signed_pct(todays_change_pct))})</span>"
        "<span class='holdings-summary-chip-caption'>today</span>"
        "</div>"
        "</div>"
        "<dl class='holdings-summary-metrics'>"
        "<div class='holdings-summary-metric'>"
        "<dt>Total invested</dt>"
        f"<dd class='holdings-num'>{html.escape(_fmt_money(total_invested))}</dd>"
        "</div>"
        "<div class='holdings-summary-metric'>"
        "<dt>Total return</dt>"
        f"<dd class='holdings-num {html.escape(total_return_class)}'>"
        f"{html.escape(_fmt_signed_dollar(total_gl))} "
        f"({html.escape(_fmt_signed_pct(total_return_pct))})</dd>"
        "</div>"
        "<div class='holdings-summary-metric'>"
        "<dt>Cash balance</dt>"
        f"<dd class='holdings-num'>{html.escape(_fmt_money(cash_balance))}</dd>"
        "</div>"
        "</dl>"
        "<div class='holdings-summary-risk-panel'>"
        "<div class='holdings-summary-risk-head'>"
        "<span class='holdings-summary-risk-title'>Risk level"
        f"<span class='holdings-risk-info' role='img' aria-label='{html.escape(risk_tip)}' "
        f"data-tip='{html.escape(risk_tip)}' tabindex='0'>i</span>"
        "</span>"
        f"<span class='holdings-risk-badge {html.escape(risk.badge_class)}'>"
        f"{html.escape(risk.level)}</span>"
        "</div>"
        "<div class='holdings-summary-risk-meter' aria-hidden='true'>"
        f"<span style='width:{risk_score_pct:.2f}%;'></span>"
        "</div>"
        "<div class='holdings-summary-risk-foot'>"
        "<span>Portfolio risk score</span>"
        f"<strong class='holdings-num'>{html.escape(risk_score_text)}</strong>"
        "</div>"
        "</div>"
    )

    return (
        "<div class='holdings-dashboard'>"
        "<div class='holdings-card holdings-card--table'>"
        "<h3 class='holdings-card-title'>Suggested Portfolio</h3>"
        "<div class='holdings-table-scroll'>"
        "<table class='holdings-table'>"
        "<colgroup>"
        "<col style='width:80px'>"
        "<col style='width:260px'>"
        "<col style='width:150px'>"
        "<col style='width:150px'>"
        "<col style='width:140px'>"
        "<col style='width:100px'>"
        "<col style='width:140px'>"
        "</colgroup>"
        "<thead><tr>"
        "<th class='holdings-th'>Symbol</th>"
        "<th class='holdings-th'>Name</th>"
        "<th class='holdings-th'>Allocation</th>"
        "<th class='holdings-th holdings-th--right'>Amount (USD)</th>"
        "<th class='holdings-th holdings-th--right'>Current Price</th>"
        "<th class='holdings-th holdings-th--right'>Shares</th>"
        "<th class='holdings-th holdings-th--right'>Value (USD)</th>"
        "</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
        "</div>"
        "<div class='holdings-table-footer'>"
        f"<div class='holdings-table-footer-item holdings-num'>Total Allocation: {total_alloc_pct:.2f}%</div>"
        f"<div class='holdings-table-footer-item holdings-num'>Total Invested: {html.escape(_fmt_money(total_invested))}</div>"
        f"<div class='holdings-table-footer-item holdings-num {portfolio_value_class}'>"
        f"Current Portfolio Value: {html.escape(_fmt_money(current_value))}</div>"
        "</div>"
        "</div>"
        "<div class='holdings-card holdings-card--summary'>"
        "<div class='holdings-summary-head'>"
        "<h3 class='holdings-card-title'>Portfolio Summary</h3>"
        "<p class='holdings-summary-eyebrow'>Live mark-to-market</p>"
        "</div>"
        f"{summary_html}"
        "</div>"
        "</div>"
    )



# ── Portfolio snapshot renderer ──────────────────────────────────────────────
def render_portfolio_snapshot(snapshot: dict) -> None:
    for alert in snapshot.get("price_warnings") or []:
        st.warning(alert)

    present = snapshot["present"]
    strategies = snapshot["strategies"]
    total_invested, current_value, total_gl = snapshot["totals"]
    investment_amount = float(snapshot.get("investment_amount") or total_invested)

    if present["Ticker"].isin(["BRK-B"]).any():
        st.caption("Berkshire Class B trades under **BRK-B** on Yahoo Finance.")

    st.markdown(
        _build_holdings_dashboard_html(
            present,
            total_invested=total_invested,
            current_value=current_value,
            total_gl=total_gl,
            investment_amount=investment_amount,
            strategies=list(strategies),
        ),
        unsafe_allow_html=True,
    )


_PLOTLY_CHART_CONFIG = {"displayModeBar": False, "displaylogo": False}


# ── Allocation donut chart ───────────────────────────────────────────────────
def plot_allocation_donut(alloc_df: pd.DataFrame | None) -> None:
    if alloc_df is None or alloc_df.empty:
        st.info("Generate a portfolio to see the allocation breakdown.")
        return
    pie_df = alloc_df.copy()
    pie_df["Allocation"] = pd.to_numeric(pie_df["Allocation"], errors="coerce")
    pie_df = pie_df.dropna(subset=["Allocation"])
    pie_df = pie_df[pie_df["Allocation"] > 0]
    if pie_df.empty:
        st.info("No priced allocations to chart.")
        return

    total_alloc = float(pie_df["Allocation"].sum())
    pie_df["legend_label"] = pie_df.apply(
        lambda row: f"{row['Ticker']} {row['Allocation'] / total_alloc * 100:.2f}%",
        axis=1,
    )
    color_map = {
        str(ticker): _ticker_badge_color(str(ticker))
        for ticker in pie_df["Ticker"].astype(str).unique()
    }

    fig = px.pie(
        pie_df,
        names="legend_label",
        values="Allocation",
        hole=0.58,
        color="Ticker",
        color_discrete_map=color_map,
        hover_data=["Strategy"],
    )
    fig.update_traces(
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f} (%{percent})<extra></extra>",
    )
    palette = _chart_palette()
    fig.update_layout(
        height=250,
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="v",
            x=1.02,
            y=0.5,
            xanchor="left",
            yanchor="middle",
            font=dict(size=11, color=palette["text_mid"]),
        ),
        margin=dict(t=10, b=10, l=10, r=120),
    )
    st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CHART_CONFIG)


# ── Portfolio trend area chart ───────────────────────────────────────────────
def plot_daily_trend(rows: list[dict]) -> None:
    if not rows:
        st.info("Generate a portfolio — the engine backfills 14 days of real price history.")
        return

    hist_df = pd.DataFrame(rows)
    hist_df["date"] = pd.to_datetime(hist_df["date"], errors="coerce").dt.normalize()
    hist_df = hist_df.dropna(subset=["date"]).sort_values("date")
    if hist_df.empty:
        st.info("No priced trend data to chart.")
        return
    hist_df = hist_df.groupby("date", as_index=False).last()
    hist_df["total_portfolio_value"] = pd.to_numeric(
        hist_df["total_portfolio_value"], errors="coerce"
    )
    hist_df = hist_df.dropna(subset=["total_portfolio_value"])
    if hist_df.empty:
        st.info("No priced trend data to chart.")
        return

    hist_df = hist_df.tail(5)
    if len(hist_df) < 2:
        st.info("At least two daily portfolio readings are needed to show a trend.")
        return

    hist_df["day_label"] = hist_df["date"].dt.strftime("%b %d")

    lo = float(hist_df["total_portfolio_value"].min())
    hi = float(hist_df["total_portfolio_value"].max())
    span = hi - lo
    pad = max(span * 0.18, abs(hi) * 0.002, 1.0) if span > 0 else max(abs(hi) * 0.01, 50.0)

    palette = _chart_palette()
    line_color = palette["line"]
    fill_color = palette["fill"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df["day_label"],
        y=hist_df["total_portfolio_value"],
        mode="lines+markers",
        fill="tozeroy",
        fillcolor=fill_color,
        line=dict(color=line_color, width=2.5),
        marker=dict(color=line_color, size=7, line=dict(width=1.5, color=palette["marker_ring"])),
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    for idx, (_, row) in enumerate(hist_df.iterrows()):
        if idx not in (0, len(hist_df) - 1):
            continue
        value = float(row["total_portfolio_value"])
        label_color = palette["gain"] if idx == len(hist_df) - 1 else palette["text_high"]
        fig.add_annotation(
            x=row["day_label"],
            y=value,
            text=f"${value:,.2f}",
            showarrow=False,
            yanchor="bottom",
            yshift=10,
            font=dict(size=11, color=label_color, family="Arial, sans-serif"),
        )
    day_labels = hist_df["day_label"].tolist()
    fig.update_layout(
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=day_labels,
            tickmode="array",
            tickvals=day_labels,
            ticktext=day_labels,
            showgrid=False,
            tickfont=dict(size=11, color=palette["text_muted"]),
            linecolor=palette["axis"],
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=palette["grid"],
            zeroline=False,
            tickprefix="$",
            tickformat=",.0f",
            tickfont=dict(size=11, color=palette["text_muted"]),
            range=[max(0.0, lo - pad), hi + pad],
        ),
        hovermode="x unified",
        margin=dict(t=28, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CHART_CONFIG)


def render_auth_gate() -> None:
    if "auth_panel" not in st.session_state:
        st.session_state.auth_panel = "Create account" if not any_users_exist() else "Sign in"

    st.markdown(
        '<div class="auth-screen-marker"></div><div class="auth-layout-marker"></div>',
        unsafe_allow_html=True,
    )
    hero_col, card_col = st.columns([1.08, 0.92], gap="large", vertical_alignment="top")

    with hero_col:
        st.markdown(
            """
            <div class="auth-hero">
                <span class="auth-eyebrow">CSC 285 · Portfolio Simulator</span>
                <div>
                    <span class="app-title">📈 Portfolio Engine</span>
                    <p class="app-subtitle">
                        Build a market-cap weighted portfolio, track daily value, and review news for your holdings.
                    </p>
                </div>
                <div class="auth-feature-grid">
                    <div class="auth-feature-card">
                        <span class="auth-feature-icon" aria-hidden="true">🎯</span>
                        <div class="auth-feature-copy">
                            <strong>Strategy-led allocation</strong>
                            <span>Choose one or two themes and let the engine size positions by market cap.</span>
                        </div>
                    </div>
                    <div class="auth-feature-card">
                        <span class="auth-feature-icon" aria-hidden="true">📈</span>
                        <div class="auth-feature-copy">
                            <strong>Daily portfolio tracking</strong>
                            <span>Save holdings, refresh live prices, and review recent value trends.</span>
                        </div>
                    </div>
                    <div class="auth-feature-card">
                        <span class="auth-feature-icon" aria-hidden="true">📰</span>
                        <div class="auth-feature-copy">
                            <strong>Market news desk</strong>
                            <span>Jump to headlines filtered for the tickers in your saved portfolio.</span>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with card_col:
        st.markdown('<div class="auth-card-column-marker"></div>', unsafe_allow_html=True)
        if not any_users_exist():
            st.markdown(
                '<p class="auth-callout">No accounts exist yet. Create the first account to start building portfolios.</p>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="auth-card-anchor"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            auth_mode = st.segmented_control(
                "Account access",
                options=["Sign in", "Create account"],
                key="auth_panel",
                label_visibility="collapsed",
            )

            if auth_mode == "Sign in":
                st.markdown("**Welcome back**")
                st.caption("Sign in to open your saved portfolio, dashboard, and market news.")
                with st.form("login"):
                    username_in = st.text_input(
                        "Username",
                        placeholder="e.g. demo",
                        help="Use the username you created or one seeded from migrate.py.",
                    )
                    password_in = st.text_input("Password", type="password")
                    submitted = st.form_submit_button(
                        "Sign in", type="primary", use_container_width=True
                    )
                    if submitted:
                        slug = sanitize_username(username_in)
                        if slug and verify_password(username_in, password_in):
                            st.session_state.user_slug = slug
                            st.rerun()
                        st.error("Invalid username or password.")
            else:
                st.markdown("**Create your account**")
                st.caption("Each account keeps its own portfolio history and saved holdings.")
                with st.form("signup"):
                    new_username = st.text_input(
                        "Username",
                        placeholder="letters, numbers, hyphens, underscores",
                        key="signup_username",
                        help="Usernames are stored in lowercase.",
                    )
                    new_password = st.text_input(
                        "Password",
                        type="password",
                        key="signup_password",
                        help="Use at least 8 characters.",
                    )
                    confirm_password = st.text_input(
                        "Confirm password",
                        type="password",
                        key="signup_confirm_password",
                    )
                    create_account = st.form_submit_button(
                        "Create account", type="primary", use_container_width=True
                    )
                    if create_account:
                        if new_password != confirm_password:
                            st.error("Passwords do not match.")
                        else:
                            ok, message = register_user(new_username, new_password)
                            if ok:
                                slug = sanitize_username(new_username)
                                if slug:
                                    st.session_state.user_slug = slug
                                    st.rerun()
                            else:
                                st.error(message)

        st.markdown(
            "<p class='auth-footnote'>Educational simulator only. Not financial advice.</p>",
            unsafe_allow_html=True,
        )


#  LOGIN GATE
# ──────────────────────────────────────────────────────────────────────────────
app_header = st.empty()
try_restore_session_from_return_link()

if not st.session_state.user_slug:
    app_header.empty()
    render_auth_gate()
    st.stop()

user_slug = st.session_state.user_slug


# ──────────────────────────────────────────────────────────────────────────────
#  TOP BAR
# ──────────────────────────────────────────────────────────────────────────────
active_view = resolve_active_view()

with app_header.container():
    render_portfolio_top_bar(
        active_view=active_view,
        news_url=_news_url_for_user(user_slug),
        user_slug=user_slug,
    )

if active_view == "history":
    render_portfolio_history(user_slug)
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"**Account:** `{user_slug}`")
    st.divider()
    st.markdown(
        """
**How it works**
Pick **1–2** strategy themes and a cash budget (min **$5,000**).
Each ticker is allocated proportionally by **market capitalisation**.
Fractional shares are sized from live Yahoo Finance quotes.

**Charts**
- Donut — dollar weight per ticker
- Area — 14-day portfolio value (real close prices)

**Data**
Prices via [`yfinance`](https://pypi.org/project/yfinance/).
Past performance does not imply future results.
"""
    )
    st.divider()
    st.caption("SJSU CSC 285 · Educational use only")


# ──────────────────────────────────────────────────────────────────────────────
#  AUTO MARK-TO-MARKET (once per calendar day)
# ──────────────────────────────────────────────────────────────────────────────
ensure_history_file(user_slug)
ensure_daily_trend_file(user_slug)

_today_iso = date.today().isoformat()
_last_mtm = st.session_state.daily_auto_mtm_date.get(user_slug)
_payload = load_current_holdings(user_slug)
if _payload and _payload.get("holdings") and _last_mtm != _today_iso:
    _holdings_pairs = [(str(h[0]), float(h[1])) for h in _payload["holdings"] if len(h) >= 2]
    _mtm_total, _mtm_warns = mark_to_market_holdings(_holdings_pairs, quote_fn=fetch_ticker_price)
    upsert_daily_portfolio_value(user_slug, _mtm_total)
    st.session_state.daily_auto_mtm_date[user_slug] = _today_iso

hydrate_portfolio_from_disk(user_slug)


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION: CREATE YOUR PORTFOLIO
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<p class="section-label portfolio-section-label">Create Your Portfolio</p>',
    unsafe_allow_html=True,
)

st.markdown('<div class="portfolio-builder-anchor"></div>', unsafe_allow_html=True)
with st.container(border=True):
    amount_col, content_col = st.columns([2.25, 7.75], vertical_alignment="top")

    with amount_col:
        investment_amount = st.number_input(
            "Investment Amount (USD)",
            min_value=0.0,
            value=10_000.0,
            step=500.0,
            format="%.0f",
            help="Minimum $5,000.",
            key=f"investment_amount_{user_slug}",
        )
        st.markdown(
            "<p class='build-min-note'>Minimum is $5,000 USD</p>",
            unsafe_allow_html=True,
        )

    with content_col:
        strategy_col, action_col = st.columns([7.35, 2.65], gap="small", vertical_alignment="top")

        with strategy_col:
            _strategy_widget_key = f"strategy_picker_{user_slug}"
            _strategy_state_key = f"strategy_selection_{user_slug}"
            _strategy_default = st.session_state.get(_strategy_state_key, ["Index Investing"])
            selected_strategies = strategy_selector_widget(
                default=_strategy_default,
                key=_strategy_widget_key,
            )
            if selected_strategies is None:
                selected_strategies = _strategy_default
            else:
                st.session_state[_strategy_state_key] = list(selected_strategies)

        with action_col:
            st.markdown('<div class="portfolio-builder-actions"></div>', unsafe_allow_html=True)
            generate_clicked = st.button(
                "Generate Portfolio",
                type="primary",
                use_container_width=True,
                key=f"generate_portfolio_{user_slug}",
            )
            refresh_trend = st.button(
                "Update today's trend",
                type="secondary",
                use_container_width=True,
                key=f"refresh_trend_{user_slug}",
                help="Re-price saved holdings and record today's portfolio total.",
            )

if refresh_trend:
    hp = load_current_holdings(user_slug)
    if not hp or not hp.get("holdings"):
        st.warning("Generate a portfolio first so holdings can be tracked.")
    else:
        with st.spinner("Re-pricing via Yahoo Finance…"):
            pairs = [(str(x[0]), float(x[1])) for x in hp["holdings"] if len(x) >= 2]
            mtm, mtm_warnings = mark_to_market_holdings(pairs, quote_fn=fetch_ticker_price)
        upsert_daily_portfolio_value(user_slug, mtm)
        st.session_state.daily_auto_mtm_date[user_slug] = _today_iso
        for alert in mtm_warnings:
            st.warning(alert)
        st.success(f"Recorded {date.today().isoformat()} — **${mtm:,.2f}**")


# ──────────────────────────────────────────────────────────────────────────────
#  GENERATE PORTFOLIO
# ──────────────────────────────────────────────────────────────────────────────
history_rerun = st.session_state.pop(f"history_rerun_pending_{user_slug}", False)
if generate_clicked or history_rerun:
    errors = validate_inputs(investment_amount, selected_strategies)
    if errors:
        for msg in errors:
            st.warning(msg)
    else:
        with st.spinner("Pulling quotes from Yahoo Finance…"):
            table_df, price_warnings = build_portfolio_table(
                selected_strategies, investment_amount, quote_fn=fetch_ticker_price
            )

        total_invested, current_value, total_gl = portfolio_totals(table_df, investment_amount)

        try:
            append_record(user_slug, selected_strategies, investment_amount, current_value)
        except Exception as exc:
            st.error(f"Could not append portfolio history: {exc}")

        priced_holdings = extract_priced_holdings(table_df)
        if priced_holdings:
            try:
                dollar_per = dict(zip(table_df["Ticker"], table_df["Allocation (USD)"]))
                save_current_holdings(
                    user_slug,
                    selected_strategies,
                    investment_amount,
                    priced_holdings,
                    dollar_per_ticker=dollar_per,
                )
                upsert_daily_portfolio_value(user_slug, current_value)
                st.session_state.daily_auto_mtm_date[user_slug] = date.today().isoformat()
            except Exception as exc:
                st.error(f"Could not save holdings / daily trend: {exc}")

            with st.spinner("Backfilling 14-day historical prices…"):
                try:
                    inserted = backfill_trend_from_holdings(user_slug, priced_holdings, days=14)
                    if inserted:
                        st.caption(f"Trend chart populated with {inserted} days of historical data.")
                except Exception as exc:
                    st.caption(f"Historical backfill skipped: {exc}")

        present = table_df.rename(columns=_PRESENT_RENAME)
        st.session_state[portfolio_snapshot_key(user_slug)] = {
            "present": present,
            "strategies": list(selected_strategies),
            "investment_amount": float(investment_amount),
            "totals": (total_invested, current_value, total_gl),
            "price_warnings": price_warnings,
            "from_disk": False,
        }
        st.session_state.allocation_df_by_user[user_slug] = present[
            ["Ticker", "Strategy", "Allocation"]
        ].copy()

else:
    if portfolio_snapshot_key(user_slug) not in st.session_state:
        st.info("Choose a strategy and amount, then press **Generate Portfolio**.")


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION: HOLDINGS
# ──────────────────────────────────────────────────────────────────────────────
_snapshot = st.session_state.get(portfolio_snapshot_key(user_slug))
if _snapshot:
    render_portfolio_snapshot(_snapshot)


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION: DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<p class="section-label portfolio-section-label">Dashboard</p>',
    unsafe_allow_html=True,
)

_trend_rows = load_daily_trend(user_slug, 30)
st.markdown('<div class="dashboard-anchor"></div>', unsafe_allow_html=True)
_trend_col, _alloc_col = st.columns([2.25, 1], gap="medium")
with _trend_col:
    st.markdown(
        '<h3 class="dashboard-chart-title">5-Day Portfolio Value Trend</h3>',
        unsafe_allow_html=True,
    )
    plot_daily_trend(_trend_rows)
    st.markdown('<p class="dashboard-chart-note">Data updated daily.</p>', unsafe_allow_html=True)
    if _trend_rows:
        _hist_df = pd.DataFrame(_trend_rows)
        _hist_df["date"] = pd.to_datetime(_hist_df["date"], errors="coerce")
        _hist_df = _hist_df.dropna(subset=["date"])
        _hist_df["day_label"] = _hist_df["date"].dt.strftime("%Y-%m-%d")
        with st.expander("View raw data"):
            st.dataframe(
                _hist_df[["day_label", "total_portfolio_value"]].rename(columns={"day_label": "date"}),
                hide_index=True,
                use_container_width=True,
            )
with _alloc_col:
    st.markdown(
        '<h3 class="dashboard-chart-title">Allocation Breakdown</h3>',
        unsafe_allow_html=True,
    )
    plot_allocation_donut(st.session_state.allocation_df_by_user.get(user_slug))
st.markdown(
    "<div class='dashboard-disclaimer'>"
    "<span class='dashboard-disclaimer-icon' aria-hidden='true'>i</span>"
    "<span>Disclaimer: This is for informational purposes only and not financial advice. "
    "Please do your own research before investing.</span>"
    "</div>",
    unsafe_allow_html=True,
)

