import type { MouseEvent } from "react";

export const SECTIONS = [
  { id: "ask", label: "Ask", keys: ["q", "modes"] },
  { id: "explore", label: "Explore", keys: ["e", "from", "to"] },
  { id: "themes", label: "Themes", keys: ["c"] },
  { id: "eval", label: "Eval", keys: [] },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];

// Each section owns its keys; everything else in the URL (other sections' keys, hash) survives.
export function writeParams(updates: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(updates)) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  window.history.replaceState(null, "", url);
}

const SETTLE_FALLBACK_MS = 1500;
let cancelSettle = () => {};

// Lets a caller that scrolls somewhere finer than the section top keep the settle from snapping back.
export const cancelSectionSettle = () => cancelSettle();

export function scrollToSection(id: SectionId) {
  const target = document.getElementById(id);
  if (!target) return false;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  cancelSettle();
  if (!reduced) {
    // Sections passed on the way mount lazily and can move the target; settle on it when this scroll ends.
    const settle = () => {
      cancelSettle();
      target.scrollIntoView({ block: "start" });
    };
    // Fallback for browsers without scrollend (Safari).
    const timer = window.setTimeout(settle, SETTLE_FALLBACK_MS);
    window.addEventListener("scrollend", settle, { once: true });
    cancelSettle = () => {
      window.clearTimeout(timer);
      window.removeEventListener("scrollend", settle);
      cancelSettle = () => {};
    };
  }
  target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  target.focus({ preventScroll: true });
  const url = new URL(window.location.href);
  url.hash = id;
  window.history.replaceState(null, "", url);
  return true;
}

// In-page jump that keeps the query string; modified clicks and other routes fall through to the href.
export function onSectionLink(event: MouseEvent<HTMLAnchorElement>, id: SectionId) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  if (window.location.pathname !== "/") return;
  if (scrollToSection(id)) event.preventDefault();
}

// The old per-section routes; the hash must follow the query (`/?q=..#ask`). Relative Location keeps the proxy host.
export const sectionRedirect = (id: SectionId) => (request: Request) => {
  const { search } = new URL(request.url);
  return new Response(null, { status: 307, headers: { Location: `/${search}#${id}` } });
};
