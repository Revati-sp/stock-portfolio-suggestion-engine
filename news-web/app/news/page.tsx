"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import NewsGrid from "@/components/NewsGrid";
import TickerFilter from "@/components/TickerFilter";
import { fetchNewsForSelection, parseTickersParam } from "@/lib/news";
import type { NewsArticle } from "@/lib/types";

export default function NewsPage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto p-6 text-sm text-slate-500">Loading market news…</div>
      }
    >
      <NewsPageContent />
    </Suspense>
  );
}

function NewsPageContent() {
  const searchParams = useSearchParams();
  const tickers = useMemo(
    () => parseTickersParam(searchParams.get("tickers")),
    [searchParams],
  );
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadNews() {
      setLoading(true);
      setError(null);
      const result = await fetchNewsForSelection(tickers, selectedTicker);
      if (cancelled) {
        return;
      }
      setArticles(result.articles);
      setError(result.error ?? null);
      setLoading(false);
    }

    void loadNews();
    return () => {
      cancelled = true;
    };
  }, [tickers, selectedTicker]);

  const emptyMessage = selectedTicker
    ? `No news found for selected ticker ${selectedTicker}.`
    : "No news found for selected ticker.";

  return (
    <div className="container mx-auto flex flex-col gap-6 p-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Market News</h1>
        <p className="text-sm text-slate-500">Latest news for your portfolio</p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="mb-3 text-sm font-medium text-slate-600">Selected Tickers</p>
        <TickerFilter
          tickers={tickers}
          selectedTicker={selectedTicker}
          onSelect={setSelectedTicker}
        />
      </section>

      {error ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      ) : null}

      <NewsGrid articles={articles} loading={loading} emptyMessage={emptyMessage} />
    </div>
  );
}
