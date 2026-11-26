export const APP_PAGES = [
  { href: "/ask", label: "Ask", keys: ["q", "modes"] },
  { href: "/explore", label: "Explore", keys: ["e", "from", "to"] },
  { href: "/themes", label: "Themes", keys: ["c"] },
  { href: "/eval", label: "Eval", keys: [] },
] as const;

// Each page owns its keys; everything else in the URL survives.
export function writeParams(updates: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(updates)) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  window.history.replaceState(null, "", url);
}

// Old single-page bookmarks (`/?q=x#ask`) become routes (`/ask?q=x`).
export function legacyHashTarget(hash: string, search: string): string | null {
  const page = APP_PAGES.find((candidate) => candidate.href === `/${hash.slice(1)}`);
  return page ? `${page.href}${search}` : null;
}

export const CONTENT_PAGES = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/benchmarks", label: "Benchmarks" },
  { href: "/docs", label: "Docs" },
] as const;

export const REPO_URL = "https://github.com/zharmedia386/nexus";
