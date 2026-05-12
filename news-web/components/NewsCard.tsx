import type { NewsArticle } from "@/lib/types";
import { formatPublishedDate, getSentiment } from "@/lib/news";

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1611974765270-7a19a6e6542f?auto=format&fit=crop&w=1200&q=80";

type NewsCardProps = {
  article: NewsArticle;
};

export default function NewsCard({ article }: NewsCardProps) {
  const sentiment = getSentiment(article.title);
  const imageSrc = article.urlToImage || FALLBACK_IMAGE;

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative h-40 overflow-hidden bg-slate-100">
        <img
          src={imageSrc}
          alt={article.title}
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
          loading="lazy"
        />
        {sentiment ? (
          <span
            className={[
              "absolute right-3 top-3 rounded-full px-2 py-1 text-xs font-semibold",
              sentiment === "Positive"
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700",
            ].join(" ")}
          >
            {sentiment}
          </span>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {article.source?.name ?? "Market Source"}
        </p>
        <h3 className="mt-2 line-clamp-2 text-base font-bold leading-snug text-slate-900">
          {article.title}
        </h3>
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
          {article.description ?? "No description available for this article."}
        </p>
        <p className="mt-3 text-xs text-slate-400">
          {formatPublishedDate(article.publishedAt)}
        </p>
        <div className="mt-auto flex items-center justify-between pt-4">
          <a
            href={article.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-semibold text-blue-600 transition hover:text-blue-700"
          >
            Read More →
          </a>
        </div>
      </div>
    </article>
  );
}
