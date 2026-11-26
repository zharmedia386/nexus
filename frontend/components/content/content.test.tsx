import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import BenchmarksPage from "@/app/(site)/benchmarks/page";
import DocsPage from "@/app/(site)/docs/page";
import HowItWorksPage from "@/app/(site)/how-it-works/page";

const ENDPOINTS = ["/query", "/documents/{doc_id}", "/chunks/{chunk_id}", "/graph/entity/{entity_id}", "/graph/path", "/graph/search", "/graph/stats", "/eval/report", "/communities", "/health"];

describe("How it works", () => {
  it("renders its heading and names all five modes", () => {
    render(<HowItWorksPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    for (const mode of ["rag", "hybrid", "graph_local", "graph_global", "auto"]) {
      expect(screen.getAllByText(mode, { selector: "code" }).length).toBeGreaterThan(0);
    }
  });
});

describe("Benchmarks", () => {
  it("shows the headline difference, its interval and every caveat", () => {
    render(<BenchmarksPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByText("+0.18")).toBeInTheDocument();
    expect(screen.getByText(/\[\+0\.09, \+0\.28\]/)).toBeInTheDocument();
    const caveatList = within(screen.getByRole("heading", { name: "Read before quoting" }).closest("section") as HTMLElement);
    for (const text of [/planted world \(seed 42\)/, /One run \(96950f8a\)/, /mention check/, /13 entity-resolution collision merges/, /0 of 136 questions have been human-reviewed/, /Claim splitter v2 drops non-claim lines/]) {
      expect(caveatList.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByText("0.9506")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /full report/i })).toHaveAttribute("href", "https://github.com/zharmedia386/nexus/blob/main/docs/report/eval-report.md");
  });
});

describe("Docs", () => {
  it("renders its heading and lists every API endpoint", () => {
    render(<DocsPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    const table = within(screen.getByRole("region", { name: "API endpoints" }));
    for (const path of ENDPOINTS) expect(table.getByText(path, { selector: "code" })).toBeInTheDocument();
  });
});
