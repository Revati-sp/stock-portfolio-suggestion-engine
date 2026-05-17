"""NewsAPI client and article helpers for Market News."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DEFAULT_TICKERS = ["VTI", "AAPL", "TSLA", "AMZN"]

_POSITIVE_TERMS = ("surge", "growth", "rally", "gain", "beat", "record", "soar")
_NEGATIVE_TERMS = ("drop", "loss", "fall", "decline", "miss", "slump", "plunge")

_FALLBACK_IMAGE = (
    "https://images.unsplash.com/photo-1611974765270-7a19a6e6542f"
    "?auto=format&fit=crop&w=1200&q=80"
)


@dataclass(frozen=True)
class NewsArticle:
    title: str
    url: str
    published_at: str
    description: str
    source_name: str
    image_url: str
    sentiment: Optional[str] = None


@dataclass(frozen=True)
class NewsFetchResult:
    articles: list[NewsArticle]
    error: Optional[str] = None


def parse_tickers_param(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_TICKERS)
    tickers = [part.strip().upper() for part in raw.split(",") if part.strip()]
    return list(dict.fromkeys(tickers)) if tickers else list(DEFAULT_TICKERS)


def _read_key_from_env_local() -> Optional[str]:
    path = Path(__file__).resolve().parents[1] / "news-web" / ".env.local"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("NEWS_API_KEY="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get_news_api_key() -> Optional[str]:
    key = os.environ.get("NEWS_API_KEY", "").strip()
    if key:
        return key
    return _read_key_from_env_local()


def get_sentiment(title: str) -> Optional[str]:
    normalized = title.lower()
    if any(term in normalized for term in _POSITIVE_TERMS):
        return "Positive"
    if any(term in normalized for term in _NEGATIVE_TERMS):
        return "Negative"
    return None


def format_published_date(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p").lstrip("0")
    except ValueError:
        return "Recently"


def _article_from_payload(item: dict[str, Any]) -> NewsArticle:
    title = str(item.get("title") or "Untitled")
    source = item.get("source") or {}
    source_name = str(source.get("name") or "Market Source")
    return NewsArticle(
        title=title,
        url=str(item.get("url") or "#"),
        published_at=str(item.get("publishedAt") or ""),
        description=str(item.get("description") or "No description available for this article."),
        source_name=source_name,
        image_url=str(item.get("urlToImage") or _FALLBACK_IMAGE),
        sentiment=get_sentiment(title),
    )


def _dedupe_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    unique: list[NewsArticle] = []
    for article in articles:
        key = article.url or f"{article.title}-{article.published_at}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def fetch_news_for_ticker(ticker: str, api_key: str) -> NewsFetchResult:
    symbol = ticker.strip().upper()
    if not symbol:
        return NewsFetchResult([], error="A ticker symbol is required.")

    params = urllib.parse.urlencode(
        {
            "q": symbol,
            "sortBy": "publishedAt",
            "pageSize": "10",
            "language": "en",
            "apiKey": api_key,
        }
    )
    endpoint = f"https://newsapi.org/v2/everything?{params}"
    request = urllib.request.Request(endpoint, headers={"User-Agent": "PortfolioEngine/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = body.get("message") or str(exc)
        except Exception:
            message = str(exc)
        return NewsFetchResult([], error=message)
    except Exception:
        return NewsFetchResult([], error="Unable to reach the news service.")

    if payload.get("status") == "error":
        return NewsFetchResult([], error=str(payload.get("message") or "News service returned an error."))

    raw_articles = payload.get("articles") or []
    articles = [_article_from_payload(item) for item in raw_articles if isinstance(item, dict)]
    return NewsFetchResult(articles)


def fetch_news_for_selection(
    tickers: list[str],
    selected_ticker: str | None,
    api_key: str,
) -> NewsFetchResult:
    targets = [selected_ticker] if selected_ticker else tickers
    merged: list[NewsArticle] = []
    errors: list[str] = []

    for symbol in targets:
        result = fetch_news_for_ticker(symbol, api_key)
        if result.error:
            errors.append(result.error)
        merged.extend(result.articles)

    sorted_articles = sorted(merged, key=lambda a: a.published_at, reverse=True)
    return NewsFetchResult(
        articles=_dedupe_articles(sorted_articles)[:15],
        error=errors[0] if errors else None,
    )
