import { NextResponse } from "next/server";
import type { NewsApiResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const ticker = (searchParams.get("q") ?? searchParams.get("ticker") ?? "").trim().toUpperCase();

  if (!ticker) {
    return NextResponse.json({
      articles: [],
      error: "A ticker symbol is required.",
    });
  }

  const apiKey = process.env.NEWS_API_KEY;
  if (!apiKey) {
    return NextResponse.json({
      articles: [],
      error: "News API key is not configured.",
    });
  }

  const endpoint = new URL("https://newsapi.org/v2/everything");
  endpoint.searchParams.set("q", ticker);
  endpoint.searchParams.set("sortBy", "publishedAt");
  endpoint.searchParams.set("pageSize", "10");
  endpoint.searchParams.set("language", "en");
  endpoint.searchParams.set("apiKey", apiKey);

  try {
    const response = await fetch(endpoint.toString(), { cache: "no-store" });
    const data = (await response.json()) as NewsApiResponse;

    if (!response.ok || data.status === "error") {
      return NextResponse.json({
        articles: [],
        error: data.message ?? "News service returned an error.",
      });
    }

    return NextResponse.json({
      articles: data.articles ?? [],
    });
  } catch {
    return NextResponse.json({
      articles: [],
      error: "Unable to reach the news service.",
    });
  }
}
