import type { Metadata } from "next";
import { Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Portfolio Suggestion Engine",
  description: "Market news for your portfolio holdings",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <div className="flex min-h-screen">
          <Suspense fallback={<aside className="w-64 shrink-0 border-r border-slate-200 bg-white" />}>
            <Sidebar />
          </Suspense>
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
