"""
app.py — Streamlit front-end for the Stock Portfolio Suggestion Engine.

Students use this page to simulate an equal-dollar split across equities chosen
implicitly via one or two investment strategies.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data import ALL_STRATEGY_NAMES, STRATEGY_TICKERS
from history import append_record, ensure_history_file, load_recent_records
from portfolio_engine import (
    fetch_ticker_price,
    portfolio_totals,
    unique_tickers_for_strategies,
    build_portfolio_table,
)


# ── Page bootstrap ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Stock Portfolio Suggestion Engine", layout="wide")

st.title("Stock Portfolio Suggestion Engine")
st.markdown(
    "Simulate diversified US-equity placements using textbook-style allocation rules "
    "and **live Yahoo Finance snapshots** fetched through `yfinance`."
)


# ── Sidebar: quick orientation ────────────────────────────────────────────────
with st.sidebar:
    st.header("About this app")
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

# ── Explanation block (presentation-friendly) ─────────────────────────────────
with st.expander("Investment methodology explained", expanded=True):
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

        5. **Historical strip** persists the newest five **Generate** executions so presenters can narrate how 
           repeated demos shifted total marks even if the syllabus portfolio stayed similar.
        """
    )


def validate_inputs(amount: float, strategies: list[str]) -> list[str]:
    """Return validation error strings instead of crashing the script."""
    issues: list[str] = []
    if amount < 5000:
        issues.append("Investment amount must be at least **$5,000**.")
    if len(strategies) < 1 or len(strategies) > 2:
        issues.append("Please pick **either one or exactly two** investment strategies.")
    return issues


def plot_recent_history(history_rows: list[dict]) -> None:
    """Render Plotly markup for ≤5 persisted portfolio snapshots sourced from CSV rows."""
    if not history_rows:
        st.info(
            "Nothing has been persisted to `portfolio_history.csv` yet — hit **Generate** once "
            "and this panel will illuminate with the freshest five executions."
        )
        return

    hist_df = pd.DataFrame(history_rows)

    fig = px.line(
        hist_df,
        x="date",
        y="total_portfolio_value",
        markers=True,
        title="Last five simulated portfolio valuations (CSV timestamps)",
        labels={
            "date": "Simulator timestamp",
            "total_portfolio_value": "Portfolio value (USD)",
        },
        hover_data=["strategies", "investment_amount"],
    )

    fig.update_traces(mode="markers+lines", line_shape="hv")
    fig.update_layout(height=460, hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw simulator history backing the chart"):
        st.dataframe(
            hist_df[["date", "strategies", "investment_amount", "total_portfolio_value"]],
            hide_index=True,
            use_container_width=True,
        )


ensure_history_file()


# ── Input widgets ─────────────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    investment_amount = st.number_input(
        "Investment budget (USD)",
        min_value=0.0,
        value=10_000.0,
        step=500.0,
        format="%.2f",
        help="Minimum $5,000 for this classroom scenario.",
    )
with col_b:
    selected_strategies = st.multiselect(
        "Investment strategies",
        ALL_STRATEGY_NAMES,
        default=["Index Investing"],
        help="Combine up to **two** strategies; pick more than three tickers implicitly.",
        max_selections=2,
    )

generate_clicked = st.button("Generate Portfolio", type="primary")

if generate_clicked:
    errors = validate_inputs(investment_amount, selected_strategies)
    if errors:
        for msg in errors:
            st.warning(msg)
    else:
        # Live pricing can take noticeable wall-clock seconds on classroom Wi‑Fi --- keep UX honest.
        with st.spinner("Pulling consolidated quotes from Yahoo Finance…"):
            table_df, price_warnings = build_portfolio_table(
                selected_strategies, investment_amount, quote_fn=fetch_ticker_price
            )

        if price_warnings:
            for alert in price_warnings:
                st.warning(alert)

        total_invested, current_value, total_gl = portfolio_totals(
            table_df, investment_amount
        )

        # Persist immediately so reloading the dashboard still exposes the KPI trail.
        try:
            append_record(selected_strategies, investment_amount, current_value)
        except OSError as exc:
            st.error(f"Could not append CSV history ({exc}).")

        st.subheader("Selected strategies & assets")
        st.write(", ".join(selected_strategies))

        uniq = ", ".join(unique_tickers_for_strategies(selected_strategies))
        st.write(f"**Tickers slated:** {uniq}")

        # Harmonize dataframe column headings with syllabus wording.
        present = table_df.rename(
            columns={
                "Ticker": "Ticker",
                "Strategy": "Strategy",
                "Allocation (USD)": "Allocation",
                "Current Price (USD)": "Current Price",
                "Shares": "Shares",
                "Current Value (USD)": "Current Value",
                "Gain/Loss (USD)": "Gain/Loss",
            }
        )

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

else:
    st.info(
        "Enter an amount (**at least $5,000**), pick strategies, then press **Generate Portfolio** "
        "to hydrate the KPI cards and persistence layer."
    )

# ── History + reference materials (shown on every rerun once CSV fills up) ───
st.divider()
st.subheader("Five most recent simulator runs (portfolio trend)")
plot_recent_history(load_recent_records(5))

st.subheader("Static strategy → ticker cheat sheet")
cheat_sheet = pd.DataFrame(
    [{"Strategy": name, "Tickers": ", ".join(syms)} for name, syms in STRATEGY_TICKERS.items()]
)
st.dataframe(cheat_sheet, hide_index=True, use_container_width=True)
