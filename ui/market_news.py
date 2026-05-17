"""In-app Market News view (Streamlit)."""

from __future__ import annotations

import html

import streamlit as st

from core.news import (
    DEFAULT_TICKERS,
    NewsArticle,
    fetch_news_for_selection,
    format_published_date,
    get_news_api_key,
)
from database.repositories import load_current_holdings


@st.cache_data(ttl=300, show_spinner=False)
def _load_news(tickers: tuple[str, ...], selected_ticker: str | None, api_key: str):
    return fetch_news_for_selection(list(tickers), selected_ticker, api_key)


def _news_api_key() -> str | None:
    try:
        key = st.secrets.get("NEWS_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return get_news_api_key()


def portfolio_tickers_for_user(slug: str) -> list[str]:
    snapshot_key = f"portfolio_snapshot_{slug}"
    snapshot = st.session_state.get(snapshot_key)
    if snapshot:
        present = snapshot.get("present")
        if present is not None and not present.empty and "Ticker" in present.columns:
            tickers = sorted({str(t) for t in present["Ticker"].tolist() if str(t)})
            if tickers:
                return tickers

    disk = load_current_holdings(slug)
    if disk and disk.get("holdings"):
        tickers = sorted({str(h[0]) for h in disk["holdings"] if h and len(h) >= 1})
        if tickers:
            return tickers

    return list(DEFAULT_TICKERS)


def _sentiment_class(sentiment: str | None) -> str:
    if sentiment == "Positive":
        return "market-news-sentiment--positive"
    if sentiment == "Negative":
        return "market-news-sentiment--negative"
    return ""


def _article_card_html(article: NewsArticle) -> str:
    sentiment_html = ""
    if article.sentiment:
        sentiment_html = (
            f"<span class='market-news-sentiment {_sentiment_class(article.sentiment)}'>"
            f"{html.escape(article.sentiment)}</span>"
        )
    return (
        "<article class='market-news-card'>"
        "<div class='market-news-card-media'>"
        f"<img src='{html.escape(article.image_url, quote=True)}' alt='' loading='lazy' />"
        f"{sentiment_html}"
        "</div>"
        "<div class='market-news-card-body'>"
        f"<p class='market-news-source'>{html.escape(article.source_name)}</p>"
        f"<h3 class='market-news-title'>{html.escape(article.title)}</h3>"
        f"<p class='market-news-desc'>{html.escape(article.description)}</p>"
        f"<p class='market-news-date'>{html.escape(format_published_date(article.published_at))}</p>"
        f"<a class='market-news-link' href='{html.escape(article.url, quote=True)}' "
        "target='_blank' rel='noopener noreferrer'>Read more →</a>"
        "</div>"
        "</article>"
    )


def render_market_news(slug: str) -> None:
    tickers = portfolio_tickers_for_user(slug)
    st.markdown(
        '<p class="section-label portfolio-section-label">Market News</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='market-news-header'>"
        "<h2 class='market-news-heading'>Latest headlines</h2>"
        "<p class='market-news-subtitle'>News for your portfolio tickers</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<p class='market-news-filter-label'>Filter by ticker</p>", unsafe_allow_html=True)
    filter_options = ["All"] + tickers
    choice = st.segmented_control(
        "Ticker filter",
        filter_options,
        key=f"news_segment_{slug}",
        label_visibility="collapsed",
    )
    selected_ticker = None if choice == "All" else choice

    api_key = _news_api_key()
    if not api_key:
        st.warning(
            "News API key is not configured. Add `NEWS_API_KEY` to `.streamlit/secrets.toml` "
            "(see `secrets.toml.example`)."
        )
        return

    with st.spinner("Loading headlines…"):
        result = _load_news(tuple(tickers), selected_ticker, api_key)

    if result.error:
        st.warning(result.error)

    if not result.articles:
        empty = (
            f"No news found for {html.escape(selected_ticker)}."
            if selected_ticker
            else "No news found for the selected tickers."
        )
        st.info(empty)
        return

    cards = "".join(_article_card_html(article) for article in result.articles)
    st.markdown(f"<div class='market-news-grid'>{cards}</div>", unsafe_allow_html=True)
