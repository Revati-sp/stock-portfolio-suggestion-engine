import type { NewsArticle } from "@/lib/types";
import NewsCard from "@/components/NewsCard";

type NewsGridProps = {
  articles: NewsArticle[];
  loading: boolean;
  emptyMessage: string;
};

function NewsSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="h-40 animate-pulse bg-slate-200" />
      <div className="space-y-3 p-4">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
        <div className="h-5 w-full animate-pulse rounded bg-slate-200" />
        <div className="h-5 w-5/6 animate-pulse rounded bg-slate-200" />
        <div className="h-12 w-full animate-pulse rounded bg-slate-100" />
        <div className="h-3 w-32 animate-pulse rounded bg-slate-100" />
      </div>
    </div>
  );
}

export default function NewsGrid({ articles, loading, emptyMessage }: NewsGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <NewsSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
        <p className="text-base font-medium text-slate-600">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {articles.map((article) => (
        <NewsCard key={`${article.url}-${article.publishedAt}`} article={article} />
      ))}
    </div>
  );
}
