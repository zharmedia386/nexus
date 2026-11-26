import { afterEach, describe, expect, it } from "vitest";
import { APP_PAGES, legacyHashTarget, writeParams } from "@/lib/routes";

afterEach(() => window.history.replaceState(null, "", "/"));

describe("routes", () => {
  it("lists the four app pages in order", () => {
    expect(APP_PAGES.map((page) => page.href)).toEqual(["/ask", "/explore", "/themes", "/eval"]);
  });

  it("maps legacy hash bookmarks to routes, keeping the query", () => {
    expect(legacyHashTarget("#ask", "?q=x&modes=rag")).toBe("/ask?q=x&modes=rag");
    expect(legacyHashTarget("#explore", "?e=c0&from=a")).toBe("/explore?e=c0&from=a");
    expect(legacyHashTarget("#themes", "")).toBe("/themes");
    expect(legacyHashTarget("#nope", "?q=x")).toBeNull();
    expect(legacyHashTarget("", "")).toBeNull();
  });

  it("writeParams keeps the pathname and other keys", () => {
    window.history.replaceState(null, "", "/ask?keep=1&q=old#foo");
    writeParams({ q: "x", gone: null });
    const url = new URL(window.location.href);
    expect(url.pathname).toBe("/ask");
    expect(url.searchParams.get("q")).toBe("x");
    expect(url.searchParams.get("keep")).toBe("1");
  });
});
