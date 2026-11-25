import type { Metadata } from "next";
import type { ReactNode } from "react";
import { IBM_Plex_Mono, Inter_Tight } from "next/font/google";
import { SiteNav } from "@/components/site-nav";
import { THEME_SCRIPT } from "@/lib/theme";
import "./globals.css";

const interTight = Inter_Tight({
  variable: "--font-inter-tight",
  subsets: ["latin"],
  weight: ["400", "500"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: { default: "NEXUS", template: "%s · NEXUS" },
  description: "GraphRAG over a fictional Indonesian business corpus: compare vector RAG, hybrid and graph retrieval with cited, multi-hop answers.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${interTight.variable} ${plexMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="relative min-h-dvh">
        <a
          href="#main"
          className="sr-only z-50 rounded-pill bg-inverse-bg px-4 py-2 text-ui text-inverse-fg focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        <SiteNav />
        <main id="main" tabIndex={-1} className="outline-none">
          {children}
        </main>
        <footer className="mx-auto flex max-w-content flex-wrap justify-between gap-2 px-6 py-10 text-ui text-muted-fg">
          <span>NEXUS · local-first GraphRAG</span>
          <span>All companies and people are fictional.</span>
        </footer>
      </body>
    </html>
  );
}
