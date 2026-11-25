import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LazySection } from "@/components/lazy-section";
import { SiteNav } from "@/components/site-nav";
import { SECTIONS, sectionRedirect } from "@/lib/sections";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(search.value),
}));

let trigger: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {};
const observed: Element[] = [];

beforeEach(() => {
  observed.length = 0;
  vi.stubGlobal("IntersectionObserver", vi.fn(function (callback: typeof trigger) {
    trigger = callback;
    return { observe: (element: Element) => observed.push(element), disconnect: () => {} };
  }));
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  search.value = "";
  document.body.innerHTML = "";
  window.history.replaceState(null, "", "/");
});

function renderPage() {
  const sections = SECTIONS.map(({ id }) => {
    const element = document.createElement("section");
    element.id = id;
    element.tabIndex = -1;
    element.scrollIntoView = vi.fn();
    document.body.append(element);
    return element;
  });
  render(<SiteNav />);
  return sections;
}

describe("SiteNav", () => {
  it("links each section as an in-page anchor on /", () => {
    renderPage();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect([...nav.querySelectorAll("ul a")].map((link) => link.getAttribute("href"))).toEqual(["/#ask", "/#explore", "/#themes", "/#eval"]);
  });

  it("marks the section crossing the spy band with aria-current", () => {
    const sections = renderPage();
    expect(observed).toEqual(sections);
    act(() => trigger([{ target: sections[1], isIntersecting: true }]));
    expect(screen.getByRole("link", { name: "Explore" })).toHaveAttribute("aria-current", "location");
    expect(screen.getByRole("link", { name: "Ask" })).not.toHaveAttribute("aria-current");
    act(() => trigger([{ target: sections[1], isIntersecting: false }]));
    expect(screen.getByRole("link", { name: "Explore" })).not.toHaveAttribute("aria-current");
  });

  it("marks the last section at the page bottom", () => {
    renderPage();
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: window.innerHeight + 500 });
    vi.stubGlobal("scrollY", 500);
    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });
    expect(screen.getByRole("link", { name: "Eval" })).toHaveAttribute("aria-current", "location");
    Reflect.deleteProperty(document.documentElement, "scrollHeight");
  });

  it("scrolls in place and keeps the query string", () => {
    window.history.replaceState(null, "", "/?q=Who&e=c0");
    const sections = renderPage();
    fireEvent.click(screen.getByRole("link", { name: "Themes" }));
    expect(sections[2]?.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(document.activeElement).toBe(sections[2]);
    expect(`${window.location.search}${window.location.hash}`).toBe("?q=Who&e=c0#themes");
  });
});

describe("sectionRedirect", () => {
  it("maps the old route to /?query#section", () => {
    const response = sectionRedirect("explore")(new Request("http://localhost:3000/explore?e=c0&from=a&to=b"));
    expect(response.status).toBe(307);
    expect(response.headers.get("Location")).toBe("/?e=c0&from=a&to=b#explore");
    expect(sectionRedirect("eval")(new Request("http://localhost:3000/eval")).headers.get("Location")).toBe("/#eval");
  });
});

describe("LazySection", () => {
  it("waits until the section is near the viewport", () => {
    render(<LazySection id="explore" placeholderClassName="h-10"><p>Explore body</p></LazySection>);
    expect(screen.queryByText("Explore body")).toBeNull();
    act(() => trigger([{ isIntersecting: true }]));
    expect(screen.getByText("Explore body")).toBeInTheDocument();
  });

  it("mounts at once and scrolls there when its params are in the URL", () => {
    const target = document.createElement("section");
    target.id = "explore";
    target.scrollIntoView = vi.fn();
    document.body.append(target);
    search.value = "e=c0";
    render(<LazySection id="explore" placeholderClassName="h-10"><p>Explore body</p></LazySection>);
    expect(screen.getByText("Explore body")).toBeInTheDocument();
    expect(target.scrollIntoView).toHaveBeenCalled();
  });
});
