import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bound, fixed, headline, signed, signedBound } from "@/components/eval/derive";
import { EvalSection } from "@/components/eval/eval-section";
import type { EvalReport } from "@/lib/types";
import raw from "./eval-report.fixture.json";

// JSON imports widen string unions; the fixture is a trimmed copy of a real /eval/report body.
const fixture = () => structuredClone(raw) as EvalReport;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let body: () => Response;

beforeEach(() => {
  body = () => json(fixture());
  vi.stubGlobal("fetch", vi.fn(async () => body()));
  // Reduced motion renders Reveal statically, so jsdom needs no IntersectionObserver.
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce"), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
});

afterEach(() => vi.unstubAllGlobals());

const table = async (name: RegExp) => within(await screen.findByRole("table", { name }));

describe("EvalSection", () => {
  it("renders answer_match values with CI from the report", async () => {
    render(<EvalSection />);
    const answers = await table(/^answer_match with 95% confidence interval/);
    const row = answers.getByRole("row", { name: /2-hop/ });
    expect(row.textContent).toContain("0.57");
    expect(row.textContent).toContain("0.29–0.79");
    expect(within(row).getByText("(best in row)")).toBeTruthy();
    // Ties share the mark: graph_local and auto share the 3-hop top score.
    expect(within(answers.getByRole("row", { name: /3-hop/ })).getAllByText("(best in row)")).toHaveLength(2);
  });

  it("marks nothing best when every mode ties", async () => {
    const report = fixture();
    report.summary = report.summary.map((row) => (row.category === "temporal" ? { ...row, answer_match: 0.4286 } : row));
    body = () => json(report);
    render(<EvalSection />);
    const answers = await table(/^answer_match with 95% confidence interval/);
    expect(within(answers.getByRole("row", { name: /Temporal/ })).queryByText("(best in row)")).toBeNull();
  });

  it("highlights the graph_local column", async () => {
    render(<EvalSection />);
    const answers = await table(/^answer_match with 95% confidence interval/);
    const spotlight = answers.getAllByRole("columnheader").filter((cell) => cell.hasAttribute("data-spotlight"));
    expect(spotlight.map((cell) => cell.textContent)).toEqual(["Graph local"]);
  });

  it("marks significant differences with their sign", async () => {
    render(<EvalSection />);
    const diffs = await table(/difference against hybrid/);
    const thematic = diffs.getByRole("row", { name: /Thematic/ });
    expect(within(thematic).getAllByText("worse")).toHaveLength(3);
    const twoHop = diffs.getByRole("row", { name: /2-hop/ });
    expect(within(twoHop).getAllByText("better")).toHaveLength(2);
    expect(twoHop.textContent).toContain("+0.50");
    expect(diffs.queryByRole("columnheader", { name: "Hybrid" })).toBeNull();
  });

  it("shows not run when judges are missing", async () => {
    const report = fixture();
    delete report.judges;
    body = () => json(report);
    render(<EvalSection />);
    expect(await screen.findByText(/no pairwise judge results/)).toBeTruthy();
    expect(screen.getAllByText("not run").length).toBeGreaterThan(0);
  });

  it("always lists caveats derived from the report", async () => {
    render(<EvalSection />);
    const caveats = within(await screen.findByRole("region", { name: "Read before quoting" }));
    expect(caveats.getByText(/planted world \(seed 42\)/)).toBeTruthy();
    expect(caveats.getByText(/^13 entity-resolution collision merges/)).toBeTruthy();
    expect(caveats.getByText(/single-hop 0.48 vs hybrid 0.83/)).toBeTruthy();
  });

  it("prefers caveats shipped in the report", async () => {
    body = () => json({ ...fixture(), caveats: ["Shipped caveat."] });
    render(<EvalSection />);
    expect(await screen.findByText("Shipped caveat.")).toBeTruthy();
    expect(screen.queryByText(/planted world \(seed/)).toBeNull();
  });

  it("shows not run when the API has no report", async () => {
    body = () => json({ detail: "eval report not found" }, 404);
    render(<EvalSection />);
    expect(await screen.findByText(/no evaluation report has been generated/)).toBeTruthy();
  });
});

// Headline keeps CIs on one line with word joiners / no-break spaces.
const plain = (lines: string[]) => lines.map((line) => line.replace(/\u2060/g, "").replace(/\u00a0/g, " "));

describe("headline", () => {
  it("states the overall comparison and sign-aware category significance", () => {
    const [first, second] = plain(headline(fixture()));
    expect(first).toContain("Graph local scores 0.66 [0.58–0.75]");
    expect(first).toContain("+0.14 [+0.05, +0.24], significant at 95%");
    expect(second).toBe("By question type it is significantly better on 2-hop, 3-hop; significantly worse on thematic; no significant difference on single-hop, temporal.");
  });

  it("flips wording when graph_local loses", () => {
    const report = fixture();
    report.diffs = report.diffs.map((row) =>
      row.mode === "graph_local" ? { ...row, mean_diff: -row.mean_diff, ci_low: -row.ci_high, ci_high: -row.ci_low } : row,
    );
    const [first, second] = plain(headline(report));
    expect(first).toContain("−0.14 [−0.24, −0.05], significant");
    expect(second).toContain("significantly better on thematic");
    expect(second).toContain("significantly worse on 2-hop, 3-hop");
  });
});

describe("number formatting", () => {
  it("rounds half away from zero without binary drift", () => {
    expect(fixed(0.825)).toBe("0.83");
    expect(fixed(0.475)).toBe("0.48");
    expect(signed(0.075)).toBe("+0.08");
    expect(signed(-0.025)).toBe("−0.03");
    expect(signed(0)).toBe("0.00");
    expect(fixed(-0.001)).toBe("0.00");
  });

  it("gives CI bounds that would print as 0.00 a third decimal", () => {
    expect(signedBound(-0.004)).toBe("−0.004");
    expect(bound(0.0049)).toBe("0.005");
    expect(signedBound(0)).toBe("0.00");
    expect(signedBound(-0.0168)).toBe("−0.02");
  });

  it("shows the 3-dp bound in the difference table", async () => {
    render(<EvalSection />);
    const diffs = await table(/difference against hybrid/);
    expect(diffs.getByRole("row", { name: /Thematic/ }).textContent).toContain("[−0.43, −0.004]");
  });
});
