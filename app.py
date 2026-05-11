"""
app.py — Stock Portfolio Suggestion Engine · Finance-grade Streamlit UI
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from auth.users import sanitize_username, users_from_secrets, verify_password
from core.strategies import ALL_STRATEGY_NAMES, STRATEGY_TICKERS
from database.repositories import (
    append_record,
    backfill_trend_from_holdings,
    ensure_daily_trend_file,
    ensure_history_file,
    load_current_holdings,
    load_daily_trend,
    load_recent_records,
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
    unique_tickers_for_strategies,
)


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
if "strategy_tile_state" not in st.session_state:
    st.session_state.strategy_tile_state = {}


# ── Finance-grade global CSS ─────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ─── Palette ───────────────────────────────────────────────────────────── */
:root {
    --gain:    #16a34a;
    --loss:    #dc2626;
    --accent:  #2563eb;
    --bg-card: #f8fafc;
    --border:  #e2e8f0;
    --txt-hi:  #0f172a;
    --txt-lo:  #64748b;
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
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-size: 0.82rem;
    color: #1e40af;
    margin-bottom: 0.8rem;
}

/* ─── Ticker badges ─────────────────────────────────────────────────────── */
.ticker-badge {
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.76rem;
    font-weight: 700;
    margin: 1px 2px;
    font-family: ui-monospace, monospace;
}

/* ─── Strategy tile button sizing ───────────────────────────────────────── */
section[data-testid="stMain"] button[kind="primary"],
section[data-testid="stMain"] button[kind="secondary"] {
    min-height: 2.875rem !important;
    box-sizing: border-box !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1.15 !important;
    font-size: 0.875rem !important;
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


# ── Helpers ──────────────────────────────────────────────────────────────────
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


def portfolio_snapshot_key(slug: str) -> str:
    return f"portfolio_snapshot_{slug}"


def clear_session_portfolio_cache() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith("portfolio_snapshot_"):
            del st.session_state[k]
    st.session_state.allocation_df_by_user = {}


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


def _color_money(val: object) -> str:
    """Green for positive, red for negative — operates on raw float cell values."""
    try:
        v = float(val)  # type: ignore[arg-type]
        if v > 0:
            return "color: #16a34a; font-weight: 600"
        if v < 0:
            return "color: #dc2626; font-weight: 600"
    except (TypeError, ValueError):
        pass
    return ""


def style_holdings_df(df: pd.DataFrame, display_cols: list[str]) -> "pd.io.formats.style.Styler":
    subset = df[display_cols].copy()
    fmt: dict[str, str] = {}
    if "Current Price" in display_cols:
        fmt["Current Price"] = "${:,.4f}"
    if "Shares" in display_cols:
        fmt["Shares"] = "{:,.6f}"
    if "Current Value" in display_cols:
        fmt["Current Value"] = "${:,.2f}"
    if "Day Gain/Loss" in display_cols:
        fmt["Day Gain/Loss"] = "${:,.2f}"
    if "Gain/Loss" in display_cols:
        fmt["Gain/Loss"] = "${:,.2f}"

    styler = subset.style.format(fmt, na_rep="—")
    for col in ("Day Gain/Loss", "Gain/Loss"):
        if col in display_cols:
            try:
                styler = styler.map(_color_money, subset=[col])
            except AttributeError:
                styler = styler.applymap(_color_money, subset=[col])  # pandas < 2.1
    return styler


# ── Portfolio snapshot renderer ──────────────────────────────────────────────
def render_portfolio_snapshot(snapshot: dict) -> None:
    if snapshot.get("from_disk"):
        st.markdown(
            "<div class='saved-banner'>📂 Showing <strong>saved portfolio</strong> "
            "re-priced with the latest quotes — press <strong>Generate Portfolio</strong> to rebuild.</div>",
            unsafe_allow_html=True,
        )
    for alert in snapshot.get("price_warnings") or []:
        st.warning(alert)

    present = snapshot["present"]
    strategies = snapshot["strategies"]
    total_invested, current_value, total_gl = snapshot["totals"]

    # Strategy + ticker summary row
    uniq_tickers = unique_tickers_for_strategies(strategies)
    badges = "".join(f"<span class='ticker-badge'>{t}</span>" for t in uniq_tickers)
    st.markdown(
        f"<div style='margin-bottom:0.8rem;'>"
        f"<span style='font-weight:700;color:#0f172a;font-size:0.95rem;'>{' + '.join(strategies)}</span>"
        f"<span style='color:#cbd5e1;margin:0 8px;'>|</span>"
        f"{badges}</div>",
        unsafe_allow_html=True,
    )

    if present["Ticker"].isin(["BRK-B"]).any():
        st.caption("Berkshire Class B trades under **BRK-B** on Yahoo Finance.")

    # Holdings table with red/green gain/loss coloring
    display_cols = [c for c in ["Ticker", "Strategy", "Shares", "Current Price",
                                "Current Value", "Day Gain/Loss", "Gain/Loss"]
                   if c in present.columns]
    st.dataframe(
        style_holdings_df(present, display_cols),
        use_container_width=True,
        hide_index=True,
    )

    # KPI cards
    st.markdown("<div style='margin-top:0.9rem;'></div>", unsafe_allow_html=True)
    pct_chg = (total_gl / total_invested * 100) if total_invested else 0.0
    gl_str = _fmt_signed_dollar(total_gl)
    pct_str = f"{pct_chg:+.2f}%"

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Total Invested", f"${total_invested:,.2f}")
    with metric_cols[1]:
        st.metric(
            "Portfolio Value",
            f"${current_value:,.2f}",
            delta=f"{gl_str} ({pct_str})",
        )
    with metric_cols[2]:
        st.metric(
            "Total Gain / Loss",
            gl_str,
            delta=f"{pct_str} all-time",
        )


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

    fig = px.pie(
        pie_df,
        names="Ticker",
        values="Allocation",
        hole=0.52,
        color_discrete_sequence=px.colors.qualitative.Safe,
        hover_data={"Strategy": True},
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}  (%{percent})<extra></extra>",
    )
    fig.update_layout(
        title=dict(text="Allocation by Ticker", font=dict(size=13, color="#0f172a"), x=0),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11)),
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Portfolio trend area chart ───────────────────────────────────────────────
def plot_daily_trend(rows: list[dict]) -> None:
    if not rows:
        st.info("Generate a portfolio — the engine backfills 14 days of real price history.")
        return

    hist_df = pd.DataFrame(rows)
    hist_df["date"] = pd.to_datetime(hist_df["date"], errors="coerce")
    hist_df = hist_df.dropna(subset=["date"])
    hist_df.sort_values("date", inplace=True)
    hist_df["day_label"] = hist_df["date"].dt.strftime("%b %d")

    lo = float(hist_df["total_portfolio_value"].min())
    hi = float(hist_df["total_portfolio_value"].max())
    pad = max(abs(hi - lo) * 0.18, 60.0)

    first_v = hist_df["total_portfolio_value"].iloc[0]
    last_v = hist_df["total_portfolio_value"].iloc[-1]
    trend_up = last_v >= first_v
    line_color = "#16a34a" if trend_up else "#dc2626"
    fill_color = "rgba(22,163,74,0.08)" if trend_up else "rgba(220,38,38,0.08)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df["day_label"],
        y=hist_df["total_portfolio_value"],
        mode="lines+markers",
        fill="tozeroy",
        fillcolor=fill_color,
        line=dict(color=line_color, width=2.5),
        marker=dict(color=line_color, size=5, line=dict(width=1.5, color="white")),
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="14-Day Portfolio Value", font=dict(size=13, color="#0f172a"), x=0),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color="#64748b"),
            linecolor="#e2e8f0",
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f1f5f9",
            tickprefix="$",
            tickformat=",.0f",
            tickfont=dict(size=11, color="#64748b"),
            range=[max(0.0, lo - pad), hi + pad],
        ),
        hovermode="x unified",
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
#  LOGIN GATE
# ──────────────────────────────────────────────────────────────────────────────
if not st.session_state.user_slug:
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        st.markdown(
            "<div style='text-align:center;margin-bottom:1.8rem;padding-top:2rem;'>"
            "<span style='font-size:2.1rem;font-weight:800;color:#0f172a;letter-spacing:-0.03em;'>"
            "📈 Portfolio Engine</span>"
            "<p style='color:#64748b;font-size:0.86rem;margin-top:6px;'>"
            "Market-cap weighted equity simulator · SJSU CSC 285</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        configured = users_from_secrets()
        if not configured:
            st.error("No users configured. Run `python migrate.py` to seed accounts.")
        else:
            with st.container(border=True):
                with st.form("login"):
                    st.markdown("**Sign in to your account**")
                    username_in = st.text_input("Username", placeholder="e.g. demo")
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
    st.stop()

user_slug = st.session_state.user_slug


# ──────────────────────────────────────────────────────────────────────────────
#  TOP BAR
# ──────────────────────────────────────────────────────────────────────────────
_head_l, _head_r = st.columns([1, 0.38], vertical_alignment="center")
with _head_l:
    st.markdown(
        "<span style='font-size:1.45rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;'>"
        "📈 Portfolio Engine</span>",
        unsafe_allow_html=True,
    )
with _head_r:
    _now = datetime.now()
    _is_weekend = _now.weekday() >= 5
    _mkt_label = "Market Closed" if _is_weekend else "Live Market"
    _mkt_dot = "#94a3b8" if _is_weekend else "#16a34a"
    st.markdown(
        f"<div style='text-align:right;line-height:1.55;'>"
        f"<span style='display:inline-flex;align-items:center;gap:6px;font-size:0.8rem;'>"
        f"<span style='width:7px;height:7px;border-radius:50%;background:{_mkt_dot};"
        f"display:inline-block;'></span><b>{_mkt_label}</b></span>"
        f"<br><span style='color:#94a3b8;font-size:0.73rem;font-family:ui-monospace,monospace;'>"
        f"{_now.strftime('%b %d %Y  %H:%M')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("Log out", key="logout_top", type="tertiary", width="content"):
        clear_session_portfolio_cache()
        st.session_state.user_slug = None
        st.rerun()


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
#  SECTION: BUILD YOUR PORTFOLIO
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-label">Build Your Portfolio</p>', unsafe_allow_html=True)

STRATEGY_ICONS = {
    "Ethical Investing": "assets/image-f34c41ea-e283-4440-be13-27d1f30dad9e.png",
    "Growth Investing": "assets/image-d9eb2414-178d-4226-8ad6-8ffd7043e2af.png",
    "Index Investing": "assets/image-0408f3a9-72e9-4751-a232-7a10ea099a9c.png",
    "Quality Investing": "assets/image-81fdf36a-8a85-4832-82eb-a40abcc0cbbd.png",
    "Value Investing": "assets/image-c3b85530-c3c2-4945-8380-4a773d547ed4.png",
}

if user_slug not in st.session_state.strategy_tile_state:
    st.session_state.strategy_tile_state[user_slug] = {"Index Investing"}

if st.session_state.pop(f"strat_max2_warn_{user_slug}", False):
    st.warning("You can select **at most two** strategies — deselect one before picking another.")

with st.container(border=True):
    left_col, mid_col, right_col = st.columns([0.28, 0.57, 0.15], vertical_alignment="top")

    with left_col:
        investment_amount = st.number_input(
            "Investment Budget (USD)",
            min_value=0.0,
            value=10_000.0,
            step=500.0,
            format="%.2f",
            help="Minimum $5,000.",
        )
        st.markdown("<div class='tile-note'>Minimum <b>$5,000</b></div>", unsafe_allow_html=True)

    current_set = set(st.session_state.strategy_tile_state.get(user_slug, set()))
    with mid_col:
        st.caption("Select strategy (choose 1 or 2)")
        tile_cols = st.columns(5)
        for idx, strat in enumerate(ALL_STRATEGY_NAMES):
            with tile_cols[idx]:
                short = strat.replace(" Investing", "")
                selected = strat in current_set
                with st.container(border=True):
                    icon_path = STRATEGY_ICONS.get(strat)
                    if icon_path:
                        _ic_l, _ic_m, _ic_r = st.columns([1, 2, 1])
                        with _ic_m:
                            st.image(icon_path, width=44)
                    st.markdown(
                        f"<div style='text-align:center;font-weight:600;font-size:0.84rem;"
                        f"margin:0.1rem 0 0.3rem 0;line-height:1.2;'>{short}"
                        f"{'<span style=\"color:#2563eb;\"> ●</span>' if selected else ''}</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "✓ Selected" if selected else "Select",
                        key=f"strat_tile_{user_slug}_{idx}",
                        type="primary" if selected else "secondary",
                        use_container_width=True,
                        help=f"Toggle **{strat}** (max 2 strategies).",
                    ):
                        s = set(st.session_state.strategy_tile_state.get(user_slug, set()))
                        if strat in s:
                            s.discard(strat)
                            st.session_state.strategy_tile_state[user_slug] = s
                            st.rerun()
                        elif len(s) < 2:
                            s.add(strat)
                            st.session_state.strategy_tile_state[user_slug] = s
                            st.rerun()
                        else:
                            st.session_state[f"strat_max2_warn_{user_slug}"] = True
                            st.rerun()

    with right_col:
        st.write("")
        st.write("")
        generate_clicked = st.button(
            "Generate Portfolio", type="primary", use_container_width=True
        )

selected_strategies = list(st.session_state.strategy_tile_state.get(user_slug, set()))


# ──────────────────────────────────────────────────────────────────────────────
#  REFRESH TREND BUTTON
# ──────────────────────────────────────────────────────────────────────────────
_act_l, _act_r = st.columns([0.7, 0.3])
with _act_r:
    refresh_trend = st.button(
        "↻ Update today's trend",
        use_container_width=True,
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
if generate_clicked:
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
    st.markdown('<p class="section-label">Holdings</p>', unsafe_allow_html=True)
    render_portfolio_snapshot(_snapshot)


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION: DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-label">Dashboard</p>', unsafe_allow_html=True)

_trend_rows = load_daily_trend(user_slug, 30)
_chart_l, _chart_r = st.columns(2)
with _chart_l:
    plot_allocation_donut(st.session_state.allocation_df_by_user.get(user_slug))
with _chart_r:
    plot_daily_trend(_trend_rows)

if _trend_rows:
    _hist_df = pd.DataFrame(_trend_rows)
    _hist_df["date"] = pd.to_datetime(_hist_df["date"], errors="coerce")
    _hist_df = _hist_df.dropna(subset=["date"])
    _hist_df["day_label"] = _hist_df["date"].dt.strftime("%Y-%m-%d")
    with st.expander("Daily totals"):
        st.dataframe(
            _hist_df[["day_label", "total_portfolio_value"]].rename(columns={"day_label": "date"}),
            hide_index=True,
            use_container_width=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
#  AUDIT LOG
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("Recent runs (audit log)"):
    audit = load_recent_records(user_slug, 8)
    if not audit:
        st.caption("No audit rows yet.")
    else:
        st.dataframe(pd.DataFrame(audit), hide_index=True, use_container_width=True)
