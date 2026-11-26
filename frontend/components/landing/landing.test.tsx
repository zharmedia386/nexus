import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Film } from "@/components/landing/film";
import { Hero } from "@/components/landing/hero";
import { Modes } from "@/components/landing/modes";
import { Proof } from "@/components/landing/proof";
import { RunIt } from "@/components/landing/run-it";
import { Walkthrough } from "@/components/landing/walkthrough";
import { REPO_URL } from "@/lib/routes";
import { REPORT, WALKTHROUGH } from "@/lib/showcase";

const originalMatchMedia = window.matchMedia;

beforeEach(() => {
  // Reduced motion: every GSAP build only sets end states, so assertions see the final DOM.
  window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as typeof window.matchMedia;
});

afterEach(() => {
  vi.restoreAllMocks();
  window.matchMedia = originalMatchMedia;
});

describe("Hero", () => {
  it("shows the report headline numbers and both CTAs", () => {
    render(<Hero />);
    for (const value of ["0.70", "0.52", "375", "1,142", "136"]) expect(screen.getByText(value)).toBeInTheDocument();
    expect(screen.getByText(/extracted graph/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Watch the film" })).toHaveAttribute("href", "#film");
    expect(screen.getByRole("link", { name: "Open app" })).toHaveAttribute("href", "/ask");
  });
});

describe("Film", () => {
  const props = { src: "/film/nexus-demo.mp4", poster: "/film/nexus-demo-poster.png", captions: "/film/nexus-demo.en.vtt" };

  it("renders a click-to-play player with captions", () => {
    const { container } = render(<Film {...props} />);
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("preload", "metadata");
    expect(video).toHaveAttribute("poster", "/film/nexus-demo-poster.png");
    expect(video).not.toHaveAttribute("autoplay");
    expect(video).toHaveAccessibleName("NEXUS demo film");
    const track = container.querySelector("track");
    expect(track).toHaveAttribute("kind", "captions");
    expect(track).toHaveAttribute("srclang", "en");
    expect(track).toHaveAttribute("src", "/film/nexus-demo.en.vtt");
    expect(track).toHaveAttribute("default");
  });

  it("falls back to the README when the video fails to load", () => {
    const { container } = render(<Film {...props} />);
    fireEvent.error(container.querySelector("video") as HTMLVideoElement);
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByRole("link", { name: /README/ })).toHaveAttribute("href", `${REPO_URL}#readme`);
  });
});

describe("Walkthrough", () => {
  it("replays the saved answer from the fixture without fetching", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { container } = render(<Walkthrough />);
    expect(screen.getByText(WALKTHROUGH.question)).toBeInTheDocument();
    expect(container.querySelectorAll("[data-walkthrough-step]")).toHaveLength(3);

    const text = container.textContent ?? "";
    const order = ["Zaenab Thamrin", "Raden Prasasta", "PT Karya Semesta"].map((name) => text.indexOf(name));
    expect(order.every((position) => position >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(screen.getByText("The documents do not contain this information.")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /^Evidence 2, doc_025:0000/ })[0]);
    const quote = screen.getByRole("dialog", { name: /doc_025:0000/ });
    expect(within(quote).getByText(/Raden Prasasta adalah pasangan suami\/istri dari Zaenab Thamrin\./)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("Walkthrough replay", () => {
  const motion = (reduced: boolean) => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as typeof window.matchMedia;
  };

  it("offers a keyboard-reachable Replay when motion is allowed, and replaying never fetches", () => {
    motion(false);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { container } = render(<Walkthrough />);
    // Motion allowed: typing starts from an empty question instead of flashing the full one.
    expect(container.querySelector("[data-typed]")?.textContent).toBe("");
    const replay = screen.getByRole("button", { name: "Replay the walkthrough" });
    replay.focus();
    expect(replay).toHaveFocus();
    fireEvent.click(replay);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("clears the typed question the moment Replay is pressed", () => {
    motion(false);
    const { container } = render(<Walkthrough />);
    const typed = container.querySelector("[data-typed]") as HTMLElement;
    // End state of a finished first play.
    typed.textContent = WALKTHROUGH.question;
    fireEvent.click(screen.getByRole("button", { name: "Replay the walkthrough" }));
    expect(typed.textContent).toBe("");
  });

  it("has no Replay under reduced motion and keeps the full question", () => {
    const { container } = render(<Walkthrough />);
    expect(screen.queryByRole("button", { name: /Replay/ })).toBeNull();
    expect(container.querySelector("[data-typed]")?.textContent).toBe(WALKTHROUGH.question);
  });
});

describe("Hero count-up", () => {
  it("starts figures at zero when motion is allowed and keeps final values when reduced", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as typeof window.matchMedia;
    const { container, unmount } = render(<Hero />);
    expect([...container.querySelectorAll("[data-count]")].map((element) => element.textContent)).toEqual(["0.00", "0.00", "0", "0", "0"]);
    unmount();
  });
});

describe("Proof", () => {
  it("shows the paired diff and the thematic loss", () => {
    render(<Proof />);
    expect(screen.getAllByText("+0.18").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\[\+0\.09, \+0\.28\]/).length).toBeGreaterThan(0);
    const thematic = screen.getByRole("row", { name: /Thematic/ });
    const cells = within(thematic).getAllByRole("cell");
    // Columns: RAG, Hybrid, Graph local.
    const score = (cell: HTMLElement) => Number(cell.textContent?.match(/\d\.\d\d/)?.[0]);
    expect(score(cells[2])).toBeLessThan(score(cells[1]));
  });
});

describe("Modes", () => {
  it("only calls RAG the fastest when its p50 is below both other modes", () => {
    render(<Modes />);
    const p50 = (mode: string) => REPORT.summary.find((row) => row.mode === mode && row.category === "all")?.p50_ms ?? Infinity;
    const fastest = p50("rag") < p50("hybrid") && p50("rag") < p50("graph_local");
    expect(screen.queryByText(/Fastest of the three/) !== null).toBe(fastest);
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual(["Mode", "What it sees", "Where it wins", "Answer match"]);
  });
});

describe("RunIt", () => {
  it("shows the three README quickstart commands and a docs link", () => {
    const { container } = render(<RunIt />);
    expect(container.querySelectorAll("pre code")).toHaveLength(3);
    expect(screen.getByText(/uv sync/)).toBeInTheDocument();
    expect(screen.getByText(/uv run nexus graph build/)).toBeInTheDocument();
    expect(screen.getByText(/npm i && npm run dev/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Docs/ })).toHaveAttribute("href", "/docs");
  });
});
