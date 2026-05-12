export type NewsArticle = {
  source?: { id?: string | null; name?: string | null };
  author?: string | null;
  title: string;
  description?: string | null;
  url: string;
  urlToImage?: string | null;
  publishedAt: string;
  content?: string | null;
};

export type NewsApiResponse = {
  status?: string;
  totalResults?: number;
  articles?: NewsArticle[];
  message?: string;
  code?: string;
};

export type Sentiment = "Positive" | "Negative" | null;

export type NewsFetchResult = {
  articles: NewsArticle[];
  error?: string;
};
