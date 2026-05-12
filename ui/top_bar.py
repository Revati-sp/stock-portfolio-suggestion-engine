"""Top application bar with aligned navigation links."""

from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from ui.navigation import portfolio_view_href


def render_portfolio_top_bar(
    *,
    active_view: str,
    news_url: str,
    user_slug: str,
) -> None:
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    market_label = "Market Closed" if is_weekend else "Live Market"
    market_dot = "#94a3b8" if is_weekend else "#16a34a"
    market_time = now.strftime("%b %d %Y  %H:%M")

    portfolio_href = html.escape(portfolio_view_href(user_slug), quote=True)
    history_href = html.escape(portfolio_view_href(user_slug, "history"), quote=True)

    if active_view == "history":
        brand_html = (
            f'<a class="portfolio-top-nav__title portfolio-top-nav__title--link" href="{portfolio_href}">'
            "Portfolio Engine"
            "</a>"
        )
    else:
        brand_html = '<h1 class="portfolio-top-nav__title">Portfolio Engine</h1>'

    history_classes = ["portfolio-top-nav__pill"]
    if active_view == "history":
        history_classes.append("portfolio-top-nav__pill--active")

    st.markdown(
        f"""
<div class="portfolio-top-nav-wrap">
  <nav class="portfolio-top-nav" aria-label="Portfolio navigation">
    <div class="portfolio-top-nav__zone portfolio-top-nav__zone--left">
      <div class="portfolio-top-nav__brand">
        <span class="portfolio-top-nav__logo" aria-hidden="true">📈</span>
        {brand_html}
      </div>
    </div>
    <div class="portfolio-top-nav__zone portfolio-top-nav__zone--right">
      <div class="app-market-meta app-market-meta--toolbar app-market-meta--inline portfolio-top-nav__market">
        <span class="app-market-label">
          <span class="app-market-dot" style="background:{market_dot};"></span>
          <b>{html.escape(market_label)}</b>
        </span>
        <span class="app-market-separator" aria-hidden="true">·</span>
        <span class="app-market-time">{html.escape(market_time)}</span>
      </div>
      <a class="{' '.join(history_classes)}" href="{history_href}">Portfolio History</a>
      <a
        class="portfolio-top-nav__pill"
        href="{html.escape(news_url, quote=True)}"
        target="_blank"
        rel="noopener noreferrer"
      >Market News</a>
      <a class="portfolio-top-nav__pill" href="?logout=1">Log out</a>
    </div>
  </nav>
</div>
""",
        unsafe_allow_html=True,
    )
