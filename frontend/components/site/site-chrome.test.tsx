import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppNav } from "@/components/site/app-nav";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteNav } from "@/components/site/site-nav";
import { APP_PAGES, CONTENT_PAGES, REPO_URL } from "@/lib/routes";

const pathname = vi.hoisted(() => ({ value: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));

afterEach(() => {
  cleanup();
  pathname.value = "/";
});

describe("SiteNav", () => {
  it("links content pages, GitHub and Open app", () => {
    render(<SiteNav />);
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const hrefs = [...nav.querySelectorAll("a")].map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/", ...CONTENT_PAGES.map((page) => page.href), REPO_URL, "/ask"]);
    const github = screen.getByRole("link", { name: /^GitHub ?\(opens in a new tab\)$/ });
    expect(github).toHaveAttribute("rel", "noreferrer");
    expect(github).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: "Open app" })).toHaveAttribute("href", "/ask");
  });

  it("toggles the mobile menu and closes on Escape, returning focus", () => {
    render(<SiteNav />);
    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("only points aria-controls at the sheet while it exists, and marks the current page in it", () => {
    pathname.value = "/docs";
    render(<SiteNav />);
    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).not.toHaveAttribute("aria-controls");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-controls", "site-menu");
    const sheet = document.getElementById("site-menu") as HTMLElement;
    expect(sheet.querySelector('a[href="/docs"]')).toHaveAttribute("aria-current", "page");
    expect(sheet.querySelector('a[href="/benchmarks"]')).not.toHaveAttribute("aria-current");
  });

  it("closes the sheet when the route changes", () => {
    const { rerender } = render(<SiteNav />);
    const button = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(button);
    expect(document.getElementById("site-menu")).not.toBeNull();
    pathname.value = "/docs";
    rerender(<SiteNav />);
    expect(document.getElementById("site-menu")).toBeNull();
    expect(button).toHaveAttribute("aria-expanded", "false");
  });
});

describe("AppNav", () => {
  it("marks the current app page", () => {
    pathname.value = "/ask";
    render(<AppNav />);
    expect(screen.getByRole("link", { name: "Ask" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Explore" })).not.toHaveAttribute("aria-current");
  });
});

describe("SiteFooter", () => {
  it("lists every page, repo, disclaimer and run id", () => {
    render(<SiteFooter runId="abc123" />);
    const footer = screen.getByRole("contentinfo");
    const hrefs = [...footer.querySelectorAll("a")].map((link) => link.getAttribute("href"));
    for (const href of [...APP_PAGES, ...CONTENT_PAGES].map((page) => page.href)) expect(hrefs).toContain(href);
    expect(hrefs).toContain(REPO_URL);
    expect(footer).toHaveTextContent("All companies and people are fictional.");
    expect(footer).toHaveTextContent("abc123");
    const github = within(footer).getByRole("link", { name: /^GitHub ?\(opens in a new tab\)$/ });
    expect(github).toHaveAttribute("target", "_blank");
    expect(github).toHaveAttribute("rel", "noreferrer");
  });
});
