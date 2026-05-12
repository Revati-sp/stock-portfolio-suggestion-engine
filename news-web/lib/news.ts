import type { NewsArticle, NewsFetchResult, Sentiment } from "@/lib/types";

const POSITIVE_TERMS = ["surge", "growth", "rally", "gain", "beat", "record", "soar"];
const NEGATIVE_TERMS = ["drop", "loss", "fall", "decline", "miss", "slump", "plunge"];

export const DEFAULT_TICKERS = ["AAPL", "TSLA", "VTI", "AMZN"];

export function parseTickersParam(raw: string | null | undefined): string[] {
  if (!raw) {
    return DEFAULT_TICKERS;
  }
  const tickers = raw
    .split(",")
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean);
  return tickers.length > 0 ? Array.from(new Set(tickers)) : DEFAULT_TICKERS;
}

export function getSentiment(title: string): Sentiment {
  const normalized = title.toLowerCase();
  if (POSITIVE_TERMS.some((term) => normalized.includes(term))) {
    return "Positive";
  }
  if (NEGATIVE_TERMS.some((term) => normalized.includes(term))) {
    return "Negative";
  }
  return null;
}

export function dedupeArticles(articles: NewsArticle[]): NewsArticle[] {
  const seen = new Set<string>();
  const unique: NewsArticle[] = [];
  for (const article of articles) {
    const key = article.url || `${article.title}-${article.publishedAt}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(article);
  }
  return unique;
}

export async function fetchNews(ticker: string): Promise<NewsFetchResult> {
  try {
    const response = await fetch(
      `/api/news?q=${encodeURIComponent(ticker)}`,
      { cache: "no-store" },
    );
    const data = (await response.json()) as NewsFetchResult;
    return {
      articles: data.articles ?? [],
      error: data.error,
    };
  } catch {
    return {
      articles: [],
      error: "Unable to load news right now.",
    };
  }
}

export async function fetchNewsForSelection(
  tickers: string[],
  selectedTicker: string | null,
): Promise<NewsFetchResult> {
  const targets = selectedTicker ? [selectedTicker] : tickers;
  const results = await Promise.all(targets.map((ticker) => fetchNews(ticker)));
  const merged = dedupeArticles(results.flatMap((result) => result.articles));
  const sorted = merged.sort(
    (left, right) =>
      new Date(right.publishedAt).getTime() - new Date(left.publishedAt).getTime(),
  );
  const errors = results.map((result) => result.error).filter(Boolean) as string[];
  return {
    articles: sorted.slice(0, 15),
    error: errors[0],
  };
}

export function formatPublishedDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Recently";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
