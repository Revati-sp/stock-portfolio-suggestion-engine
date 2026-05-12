"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { LayoutDashboard, Newspaper } from "lucide-react";
import { rememberPortfolioReturn, resolvePortfolioHref } from "@/lib/portfolioUrl";

const navItems = [
  {
    key: "portfolio",
    label: "Portfolio",
    icon: LayoutDashboard,
    external: true,
  },
  {
    key: "news",
    label: "News",
    icon: Newspaper,
    external: false,
  },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const portfolioHref = resolvePortfolioHref({
    portfolio: searchParams.get("portfolio"),
    user: searchParams.get("user"),
    resume: searchParams.get("resume"),
  });
  const newsHref = useMemo(() => {
    const query = searchParams.toString();
    return query ? `/news?${query}` : "/news";
  }, [searchParams]);

  useEffect(() => {
    rememberPortfolioReturn({
      portfolio: searchParams.get("portfolio"),
      user: searchParams.get("user"),
      resume: searchParams.get("resume"),
    });
  }, [searchParams]);

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-white px-4 py-6">
      <div className="mb-8 px-2">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Portfolio Engine
        </p>
        <h1 className="mt-2 text-lg font-bold text-slate-900">Market Desk</h1>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const href = item.key === "portfolio" ? portfolioHref : newsHref;
          const active = !item.external && pathname === "/news";
          const className = [
            "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
            active
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
          ].join(" ");

          if (item.external) {
            return (
              <a key={item.key} href={href} className={className}>
                <item.icon className="h-4 w-4" />
                {item.label}
              </a>
            );
          }

          return (
            <Link key={item.key} href={href} className={className}>
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
