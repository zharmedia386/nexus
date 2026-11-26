import type { EvalCategory, EvalDiff, EvalReport, EvalSummaryRow, Mode } from "@/lib/types";

export const MODES: Mode[] = ["rag", "hybrid", "graph_local", "graph_global", "auto"];
export const BASELINE: Mode = "hybrid";
export const SPOTLIGHT: Mode = "graph_local";
export const ANSWERABLE: EvalCategory[] = ["all", "single_hop", "multi_hop_2", "multi_hop_3", "temporal", "thematic"];

export const MODE_LABEL: Record<Mode, string> = {
  rag: "RAG",
  hybrid: "Hybrid",
  graph_local: "Graph local",
  graph_global: "Graph global",
  auto: "Auto",
};

export const CATEGORY_LABEL: Record<EvalCategory, string> = {
  all: "All answerable",
  single_hop: "Single-hop",
  multi_hop_2: "2-hop",
  multi_hop_3: "3-hop",
  temporal: "Temporal",
  thematic: "Thematic",
  unanswerable: "Unanswerable",
};

// Half away from zero; the epsilon absorbs binary drift (0.825 is stored as 0.82499…).
export function fixed(value: number, digits = 2) {
  const scale = 10 ** digits;
  const rounded = (Math.sign(value) * Math.round(Math.abs(value) * scale + 1e-9)) / scale;
  return Math.abs(rounded).toFixed(digits) === (0).toFixed(digits) ? (0).toFixed(digits) : rounded.toFixed(digits);
}
// A non-zero CI bound that would print as 0.00 gets a third decimal, so it never looks like it touches 0.
export const bound = (value: number) => fixed(value, value !== 0 && fixed(value) === fixed(0) ? 3 : 2);
const withSign = (value: number, text: string) => (Number(text) === 0 ? text : value > 0 ? `+${text}` : `−${text}`);
export const signed = (value: number) => withSign(value, fixed(Math.abs(value)));
export const signedBound = (value: number) => withSign(value, bound(Math.abs(value)));
export const seconds = (ms: number) => `${fixed(ms / 1000, 1)} s`;

export const summaryRow = (report: EvalReport, mode: Mode, category: EvalCategory): EvalSummaryRow | undefined =>
  report.summary.find((row) => row.mode === mode && row.category === category);

export const diffRow = (report: EvalReport, mode: Mode, category: EvalCategory): EvalDiff | undefined =>
  report.diffs.find((row) => row.mode === mode && row.category === category);

// Questions behind a category's answer_match: "all" counts answerable questions only.
export const categoryN = (report: EvalReport, category: EvalCategory) =>
  category === "all" ? report.answerable : (report.summary.find((row) => row.category === category)?.n ?? 0);

const ci = (row: EvalSummaryRow) =>
  row.answer_match_ci_low !== null && row.answer_match_ci_high !== null
    ? `[${bound(row.answer_match_ci_low)}\u2060–\u2060${bound(row.answer_match_ci_high)}]`
    : "";

const list = (categories: EvalCategory[]) => categories.map((category) => CATEGORY_LABEL[category].toLowerCase()).join(", ");

// Mirrors the report's §1 summary: spotlight vs baseline overall, then per-category significance with sign.
export function headline(report: EvalReport): string[] {
  const spot = summaryRow(report, SPOTLIGHT, "all");
  const base = summaryRow(report, BASELINE, "all");
  const overall = diffRow(report, SPOTLIGHT, "all");
  if (!spot || !base || !overall || spot.answer_match === null || base.answer_match === null) return [];
  const verdict = overall.significant ? "significant at 95%" : "not significant at 95%";
  const first =
    `${MODE_LABEL[SPOTLIGHT]} scores ${fixed(spot.answer_match)} ${ci(spot)} answer match against ${MODE_LABEL[BASELINE].toLowerCase()}'s ` +
    `${fixed(base.answer_match)} ${ci(base)} on ${report.answerable} answerable questions: a paired difference of ` +
    `${signed(overall.mean_diff)} [${signedBound(overall.ci_low)},\u00a0${signedBound(overall.ci_high)}], ${verdict}.`;
  const rows = report.diffs.filter((row) => row.mode === SPOTLIGHT && row.category !== "all");
  const better = rows.filter((row) => row.significant && row.mean_diff > 0).map((row) => row.category);
  const worse = rows.filter((row) => row.significant && row.mean_diff < 0).map((row) => row.category);
  const flat = rows.filter((row) => !row.significant).map((row) => row.category);
  const clauses = [
    better.length ? `significantly better on ${list(better)}` : "",
    worse.length ? `significantly worse on ${list(worse)}` : "",
    flat.length ? `no significant difference on ${list(flat)}` : "",
  ].filter(Boolean);
  if (!clauses.length) return [first];
  const second = clauses.join("; ");
  return [first, `By question type it is ${second}.`];
}

// Used only when the report carries no caveats of its own; every figure is read from the report.
export function caveats(report: EvalReport): string[] {
  if (report.caveats?.length) return report.caveats;
  const model = report.models.LLM_MODEL;
  const rows = report.summary.filter((row) => row.mode === SPOTLIGHT && row.category !== "all");
  const spans = report.summary
    .filter((row) => row.answer_match_ci_low !== null && row.answer_match_ci_high !== null && row.category !== "all")
    .map((row) => (row.answer_match_ci_high ?? 0) - (row.answer_match_ci_low ?? 0));
  const items = [
    `Synthetic data: documents, questions and gold answers come from a planted world (seed ${report.dataset.seed}). Treat these scores as an upper bound; real corpora will likely score lower.`,
    `One run (${report.run_id.slice(0, 8)}) at a fixed configuration; run-to-run variance is not measured.`,
    "answer_match is a mention check: an answer that names the gold entity while hedging still scores 1.",
    `Small n per category (${rows.map((row) => `${CATEGORY_LABEL[row.category].toLowerCase()} ${row.n}`).join(", ")})` +
      (spans.length ? `; the widest 95% CI spans ${fixed(Math.max(...spans))}.` : "."),
  ];
  if (report.judges?.length && model) {
    items.push(`The thematic judge ran on the project's gateway model at report time (LLM_MODEL ${model}), the same family as the answering model in this run's config; LLM judges favour longer answers, so mean lengths are shown beside each verdict.`);
  }
  if (report.graph?.er) {
    items.push(`${report.graph.er.collision_merges} entity-resolution collision merges: distinct people sharing a name were merged, which can create false graph paths.`);
  }
  const globalSingle = summaryRow(report, "graph_global", "single_hop")?.answer_match;
  const baseSingle = summaryRow(report, BASELINE, "single_hop")?.answer_match;
  if (globalSingle != null && baseSingle != null) {
    items.push(
      `Graph global answers from community summaries, so it is weak on factual questions by design (single-hop ${fixed(globalSingle)} vs ${MODE_LABEL[BASELINE].toLowerCase()} ${fixed(baseSingle)}); its target is thematic questions.`,
    );
  }
  if (report.claim_split_version) {
    items.push(`Claim splitter ${report.claim_split_version} drops non-claim lines (headings, step labels, abstentions) before verification; this run's dropped lines were not hand-checked.`);
  }
  const { review_marked: marked, review_rows: total } = report.dataset;
  if (marked !== undefined && total !== undefined && marked < total) {
    items.push(`Gold answers are generated from the world graph; ${marked} of ${total} questions have been human-reviewed.`);
  }
  return items;
}
