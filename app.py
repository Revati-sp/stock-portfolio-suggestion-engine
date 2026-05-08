"""
app.py — Streamlit front-end for the Stock Portfolio Suggestion Engine.

Students use this page to simulate an equal-dollar split across equities chosen
implicitly via one or two investment strategies. Login isolates each user's CSV/JSON data.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import sanitize_username, users_from_secrets, verify_password
from data import ALL_STRATEGY_NAMES, STRATEGY_TICKERS
from history import (
    append_record,
    ensure_daily_trend_file,
    ensure_history_file,
    load_current_holdings,
    load_daily_trend,
    load_recent_records,
    save_current_holdings,
    upsert_daily_portfolio_value,
)
from portfolio_engine import (
    build_portfolio_table,
    build_portfolio_table_from_saved,
    extract_priced_holdings,
    fetch_ticker_price,
    mark_to_market_holdings,
    portfolio_totals,
    unique_tickers_for_strategies,
)


# ── Page bootstrap ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Stock Portfolio Suggestion Engine", layout="wide")

if "user_slug" not in st.session_state:
    st.session_state.user_slug = None
if "daily_auto_mtm_date" not in st.session_state:
    st.session_state.daily_auto_mtm_date = {}
if "allocation_df_by_user" not in st.session_state:
    st.session_state.allocation_df_by_user = {}
if "strategy_tile_state" not in st.session_state:
    st.session_state.strategy_tile_state = {}


def validate_inputs(amount: float, strategies: list[str]) -> list[str]:
    """Return validation error strings instead of crashing the script."""
    issues: list[str] = []
    if amount < 5000:
        issues.append("Investment amount must be at least **$5,000**.")
    if len(strategies) < 1 or len(strategies) > 2:
        issues.append("Please pick **either one or exactly two** investment strategies.")
    return issues


def plot_daily_trend(rows: list[dict], *, show_csv_expander: bool = True) -> None:
    """Line chart: one point per calendar day from `portfolio_daily_trend.csv`."""
    if not rows:
        st.info(
            "**Generate** a portfolio first. The engine saves your holdings, then records **one** "
            "mark-to-market total per day (re-priced via Yahoo) and charts the **last five days**."
        )
        return

    hist_df = pd.DataFrame(rows)
    hist_df["date"] = pd.to_datetime(hist_df["date"], errors="coerce")
    hist_df = hist_df.dropna(subset=["date"])
    hist_df["day_label"] = hist_df["date"].dt.strftime("%Y-%m-%d")

    if len(hist_df) == 1 and show_csv_expander:
        st.caption(
            "Only **one** day is stored so far — the line needs **up to five different calendar days** "
            "(open the app or use **Update today's trend** on later days). The chart below uses day labels "
            "so a single point stays readable."
        )

    fig = px.line(
        hist_df,
        x="day_label",
        y="total_portfolio_value",
        markers=True,
        title="Portfolio value trend (USD)",
        labels={
            "day_label": "Calendar day",
            "total_portfolio_value": "Total value (USD)",
        },
    )
    fig.update_traces(mode="markers+lines")
    fig.update_layout(height=420, hovermode="x unified")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=hist_df["day_label"].tolist())

    lo, hi = float(hist_df["total_portfolio_value"].min()), float(hist_df["total_portfolio_value"].max())
    if lo == hi:
        pad = max(abs(lo) * 0.02, 25.0)
        fig.update_yaxes(range=[lo - pad, hi + pad])

    st.plotly_chart(fig, use_container_width=True)

    if show_csv_expander:
        with st.expander("Daily totals (CSV)"):
            show_df = hist_df[["day_label", "total_portfolio_value"]].rename(
                columns={"day_label": "date"}
            )
            st.dataframe(show_df, hide_index=True, use_container_width=True)


_PRESENT_RENAME = {
    "Ticker": "Ticker",
    "Strategy": "Strategy",
    "Allocation (USD)": "Allocation",
    "Current Price (USD)": "Current Price",
    "Shares": "Shares",
    "Current Value (USD)": "Current Value",
    "Gain/Loss (USD)": "Gain/Loss",
}


def portfolio_snapshot_key(slug: str) -> str:
    return f"portfolio_snapshot_{slug}"


def clear_session_portfolio_cache() -> None:
    """Drop in-memory portfolio UI so the next login reloads from disk."""
    for k in list(st.session_state.keys()):
        if k.startswith("portfolio_snapshot_"):
            del st.session_state[k]
    st.session_state.allocation_df_by_user = {}


def hydrate_portfolio_from_disk(slug: str) -> None:
    """If JSON holdings exist and nothing is cached, rebuild table + pie data."""
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


def render_portfolio_snapshot(snapshot: dict) -> None:
    """Table + metrics for a generated or disk-restored portfolio."""
    if snapshot.get("from_disk"):
        st.info(
            "This is your **saved** portfolio for this account (from `current_holdings.json`, "
            "re-priced with the latest quotes). **Generate Portfolio** again to replace it."
        )
    for alert in snapshot.get("price_warnings") or []:
        st.warning(alert)

    present = snapshot["present"]
    strategies = snapshot["strategies"]
    total_invested, current_value, total_gl = snapshot["totals"]

    st.subheader("Selected strategies & assets")
    st.write(", ".join(strategies))

    uniq = ", ".join(unique_tickers_for_strategies(strategies))
    st.write(f"**Tickers slated:** {uniq}")

    if present["Ticker"].isin(["BRK-B"]).any():
        st.caption("Note: Berkshire Class B trades under **BRK-B** inside Yahoo.")

    st.dataframe(
        present.style.format(
            {"Allocation": "${:,.2f}", "Current Price": "${:,.4f}", "Shares": "{:,.6f}"},
            na_rep="---",
        ).format({"Current Value": "${:,.2f}", "Gain/Loss": "${:,.2f}"}, na_rep="---")
    )

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(label="Total Invested", value=f"${total_invested:,.2f}")
    with metric_cols[1]:
        st.metric(label="Current Portfolio Value", value=f"${current_value:,.2f}")
    with metric_cols[2]:
        st.metric(label="Total Gain/Loss", value=f"${total_gl:,.2f}")

    st.caption(
        "Totals reflect allocations actually priced rows when Yahoo cooperates --- "
        "compare this against your budget if any warnings appeared."
    )


def plot_allocation_pie(alloc_df: pd.DataFrame | None) -> None:
    """Pie chart: dollar allocation per ticker (saved portfolio)."""
    if alloc_df is None or alloc_df.empty:
        st.info("**Generate** a portfolio (or reload after login) to see dollar allocation by ticker.")
        return

    pie_df = alloc_df.copy()
    pie_df["Allocation"] = pd.to_numeric(pie_df["Allocation"], errors="coerce")
    pie_df = pie_df.dropna(subset=["Allocation"])
    pie_df = pie_df[pie_df["Allocation"] > 0]
    if pie_df.empty:
        st.info("No priced allocations to chart yet.")
        return

    fig = px.pie(
        pie_df,
        names="Ticker",
        values="Allocation",
        title="Budget allocation by ticker",
        color_discrete_sequence=px.colors.qualitative.Safe,
        hover_data={"Strategy": True},
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=420, legend_title_text="Ticker", showlegend=True)

    st.plotly_chart(fig, use_container_width=True)


# ── Login gate ─────────────────────────────────────────────────────────────────
if not st.session_state.user_slug:
    st.title("Account login")
    st.markdown(
        "Enter the username and password defined in your **`.streamlit/secrets.toml`** file (`[users]` section). "
        "Your portfolio files are stored under **`user_data/<username>/`** after you sign in."
    )
    configured = users_from_secrets()
    if not configured:
        st.error(
            "No `[users]` table found. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` "
            "and set at least one username/password."
        )
    else:
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("login"):
                username_in = st.text_input("Username", placeholder="e.g. demo")
                password_in = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
                if submitted:
                    slug = sanitize_username(username_in)
                    if slug and verify_password(username_in, password_in):
                        st.session_state.user_slug = slug
                        st.rerun()
                    st.error("Invalid username or password.")
    st.stop()

user_slug = st.session_state.user_slug

# ── Top bar: always visible (sidebar may be collapsed) ─────────────────────────
_head_l, _head_r = st.columns([1, 0.35], vertical_alignment="center")
with _head_l:
    st.markdown("## Portfolio Suggestion")
with _head_r:
    st.markdown(
        f"<div style='text-align:right; font-size: 0.9rem;'>"
        f"<span style='display:inline-flex; align-items:center; gap:8px;'>"
        f"<span style='width:10px; height:10px; border-radius:50%; background:#16a34a; display:inline-block;'></span>"
        f"<span><b>Live Market</b></span>"
        f"</span><br/>"
        f"<span style='color:#6b7280;'>{datetime.now().strftime('%b %d, %Y %I:%M:%S %p')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "Log out",
        key="logout_top",
        type="tertiary",
        width="content",
        help="Sign out and return to the login screen.",
    ):
        clear_session_portfolio_cache()
        st.session_state.user_slug = None
        st.rerun()

st.markdown(
    "Simulate diversified US-equity placements using textbook-style allocation rules "
    "and **live Yahoo Finance snapshots** fetched through `yfinance`."
)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("About this app")
    st.caption(f"Account: `{user_slug}` — use **Log out** at the top of the page to switch users.")
    st.markdown(
        """
        **What does it do?**  
        You choose **one or two** strategy themes plus a **cash budget** (minimum $5,000).  
        Every unique stock/ETF you inherit from those baskets receives the **same dollar slice**, 
        and we convert that slice into **fractional shares** using Yahoo's latest workable quote.

        **Why Streamlit + Plotly?**  
        The UI stays lightweight for class demos yet still feels like a credible analytics surface.

        **Data source**  
        Prices come from Yahoo Finance indirectly via [`yfinance`](https://pypi.org/project/yfinance/) 
        --- no keys, trades off reliability during market holidays.
        """
    )
    st.divider()
    st.caption("ISTA / CSC 285 term project scaffold — educational use only.")

with st.expander("Investment methodology explained", expanded=False):
    st.markdown(
        """
        1. **Strategy palettes** anchor the idea that different mandates favor different equities.  
           Example: passive investors lean on ETFs such as **VTI** while growth seekers might target 
           high-revenue innovators like **NVDA**.

        2. **Capital deployment** divides your budget **uniformly across every resulting ticker**.  
           Selecting **two** strategies merges the underlying lists (**duplicates drop automatically**).

        3. **Sizing** computes `Shares = Dollars allocated ÷ Quote`, keeping fractional precision so 
           $5,000+ inputs stay realistic without rounding to whole lots.

        4. **Mark-to-market** multiplies holdings by the freshest quote surfaced by Yahoo. Pricing 
           failures bubble up inline warnings --- your CSV history still captures `total portfolio value`.

        5. **Five-day trend** stores **one total portfolio value per calendar day** (mark-to-market:  
           Σ shares × live price) for the **same saved basket** after you **Generate**. Opening the app on a  
           later day re-prices that basket once per session and appends/updates that day’s row;  
           the chart keeps at most the **last five days**.
        """
    )


ensure_history_file(user_slug)
ensure_daily_trend_file(user_slug)

_today_iso = date.today().isoformat()
_last_mtm = st.session_state.daily_auto_mtm_date.get(user_slug)
_payload = load_current_holdings(user_slug)
if (
    _payload
    and _payload.get("holdings")
    and _last_mtm != _today_iso
):
    _holdings_pairs = [(str(h[0]), float(h[1])) for h in _payload["holdings"]]
    _mtm_total, _mtm_warns = mark_to_market_holdings(_holdings_pairs, quote_fn=fetch_ticker_price)
    upsert_daily_portfolio_value(user_slug, _mtm_total)
    st.session_state.daily_auto_mtm_date[user_slug] = _today_iso

hydrate_portfolio_from_disk(user_slug)

st.markdown(
    """
<style>
.tile-note { color:#6b7280; font-size: 0.85rem; margin-top: -8px; }
/* Baseline button sizing — tiles use identical label “Choose”; min-height aligns rows */
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
/* Log out: text-link style (`type="tertiary"` → kind="tertiary" on the button) */
section[data-testid="stMain"] button[kind="tertiary"] {
  min-height: unset !important;
  padding: 0 !important;
  margin: 0 !important;
  font-size: 0.85rem !important;
  font-weight: 500 !important;
  color: #2563eb !important;
  text-decoration: underline !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
section[data-testid="stMain"] button[kind="tertiary"]:hover {
  color: #1d4ed8 !important;
  background: transparent !important;
}
/* st.number_input +/- steppers: scoped to this widget’s element container only */
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
</style>
""",
    unsafe_allow_html=True,
)

left_col, mid_col, right_col = st.columns([0.33, 0.52, 0.15], vertical_alignment="top")
with left_col:
    investment_amount = st.number_input(
        "Investment budget (USD)",
        min_value=0.0,
        value=10_000.0,
        step=500.0,
        format="%.2f",
        help="Minimum $5,000 for this classroom scenario.",
    )
    st.markdown("<div class='tile-note'>Minimum is <b>$5,000</b> USD</div>", unsafe_allow_html=True)

STRATEGY_ICONS = {
    "Ethical Investing": "assets/image-f34c41ea-e283-4440-be13-27d1f30dad9e.png",
    "Growth Investing": "assets/image-d9eb2414-178d-4226-8ad6-8ffd7043e2af.png",
    "Index Investing": "assets/image-0408f3a9-72e9-4751-a232-7a10ea099a9c.png",
    "Quality Investing": "assets/image-81fdf36a-8a85-4832-82eb-a40abcc0cbbd.png",
    "Value Investing": "assets/image-c3b85530-c3c2-4945-8380-4a773d547ed4.png",
}

# Initialize per-user tile state once.
if user_slug not in st.session_state.strategy_tile_state:
    st.session_state.strategy_tile_state[user_slug] = {"Index Investing"}

with mid_col:
    st.caption("Select Investment Strategy (select one or two)")
    if st.session_state.pop(f"strat_max2_warn_{user_slug}", False):
        st.warning("You can select **at most two** strategies — deselect one to choose another.")
    tile_cols = st.columns(5)
    current_set = set(st.session_state.strategy_tile_state.get(user_slug, set()))

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
                    f"<div style='text-align:center;font-weight:600;font-size:0.88rem;"
                    f"margin:0.15rem 0 0.35rem 0;line-height:1.2;'>{short}"
                    f"{' <span style=\"color:#2563eb;\">●</span>' if selected else ''}</div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Choose",
                    key=f"strat_tile_{user_slug}_{idx}",
                    type="primary" if selected else "secondary",
                    use_container_width=True,
                    help=f"Toggle **{strat}** (max 2). Highlighted = selected.",
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
    st.write("")  # vertical spacing
    st.write("")
    generate_clicked = st.button("Generate Portfolio", type="primary", use_container_width=True)

selected_strategies = list(st.session_state.strategy_tile_state.get(user_slug, set()))

_actions_l, _actions_r = st.columns([0.7, 0.3])
with _actions_r:
    refresh_trend = st.button(
        "Update today's trend (re-price saved holdings)",
        use_container_width=True,
    )

if refresh_trend:
    hp = load_current_holdings(user_slug)
    if not hp or not hp.get("holdings"):
        st.warning("Generate a portfolio first so holdings can be saved for daily tracking.")
    else:
        with st.spinner("Re-pricing saved holdings via Yahoo Finance…"):
            pairs = [(str(x[0]), float(x[1])) for x in hp["holdings"]]
            mtm, mtm_warnings = mark_to_market_holdings(pairs, quote_fn=fetch_ticker_price)
        upsert_daily_portfolio_value(user_slug, mtm)
        st.session_state.daily_auto_mtm_date[user_slug] = _today_iso
        for alert in mtm_warnings:
            st.warning(alert)
        st.success(f"Recorded **{date.today().isoformat()}** total: **${mtm:,.2f}**.")

if generate_clicked:
    errors = validate_inputs(investment_amount, selected_strategies)
    if errors:
        for msg in errors:
            st.warning(msg)
    else:
        with st.spinner("Pulling consolidated quotes from Yahoo Finance…"):
            table_df, price_warnings = build_portfolio_table(
                selected_strategies, investment_amount, quote_fn=fetch_ticker_price
            )

        total_invested, current_value, total_gl = portfolio_totals(
            table_df, investment_amount
        )

        try:
            append_record(user_slug, selected_strategies, investment_amount, current_value)
        except OSError as exc:
            st.error(f"Could not append CSV history ({exc}).")

        priced_holdings = extract_priced_holdings(table_df)
        if priced_holdings:
            try:
                n_u = len(unique_tickers_for_strategies(selected_strategies))
                dollar_per = investment_amount / float(n_u) if n_u else 0.0
                save_current_holdings(
                    user_slug,
                    selected_strategies,
                    investment_amount,
                    priced_holdings,
                    dollar_per_ticker=dollar_per,
                )
                upsert_daily_portfolio_value(user_slug, current_value)
                st.session_state.daily_auto_mtm_date[user_slug] = date.today().isoformat()
            except OSError as exc:
                st.error(f"Could not save holdings / daily trend ({exc}).")

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
        st.info(
            "Enter an amount (**at least $5,000**), pick strategies, then press **Generate Portfolio** "
            "to hydrate the KPI cards and persistence layer."
        )

_snapshot = st.session_state.get(portfolio_snapshot_key(user_slug))
if _snapshot:
    render_portfolio_snapshot(_snapshot)

st.divider()
st.subheader("Graphical dashboard")

_trend_rows = load_daily_trend(user_slug, 5)
_chart_l, _chart_r = st.columns(2)
with _chart_l:
    st.caption("**Pie chart** — dollar allocation per ticker (saved portfolio).")
    plot_allocation_pie(st.session_state.allocation_df_by_user.get(user_slug))
with _chart_r:
    st.caption("**Line chart** — portfolio total value by day (up to five days on file).")
    if len(_trend_rows) == 1:
        st.caption(
            "One day stored so far; add more days by opening the app later or using **Update today's trend**."
        )
    plot_daily_trend(_trend_rows, show_csv_expander=False)

if _trend_rows:
    _hist_df = pd.DataFrame(_trend_rows)
    _hist_df["date"] = pd.to_datetime(_hist_df["date"], errors="coerce")
    _hist_df = _hist_df.dropna(subset=["date"])
    _hist_df["day_label"] = _hist_df["date"].dt.strftime("%Y-%m-%d")
    with st.expander("Daily totals (CSV)"):
        st.dataframe(
            _hist_df[["day_label", "total_portfolio_value"]].rename(columns={"day_label": "date"}),
            hide_index=True,
            use_container_width=True,
        )

with st.expander("Recent Generate runs (audit log)"):
    audit = load_recent_records(user_slug, 8)
    if not audit:
        st.caption("No audit rows for this user yet.")
    else:
        st.dataframe(pd.DataFrame(audit), hide_index=True, use_container_width=True)
