import Link from "next/link";
import { ModeTable, ScoreCell, type ModeRow } from "@/components/eval/charts";
import { CATEGORY_LABEL, categoryN, diffRow, fixed, signed, signedBound, summaryRow } from "@/components/eval/derive";
import { REPORT } from "@/lib/showcase";
import type { EvalCategory, Mode } from "@/lib/types";

const MODES: Mode[] = ["rag", "hybrid", "graph_local"];
const CATEGORIES: EvalCategory[] = ["single_hop", "multi_hop_2", "multi_hop_3", "temporal", "thematic", "all"];

const score = (mode: Mode, category: EvalCategory) => fixed(summaryRow(REPORT, mode, category)?.answer_match ?? 0);
const overall = diffRow(REPORT, "graph_local", "all");
const thematic = diffRow(REPORT, "graph_local", "thematic");
const flat = REPORT.diffs
  .filter((row) => row.mode === "graph_local" && row.category !== "all" && !row.significant)
  .map((row) => CATEGORY_LABEL[row.category].toLowerCase());

const rows: ModeRow[] = CATEGORIES.map((category) => {
  const scores = MODES.map((mode) => summaryRow(REPORT, mode, category)?.answer_match ?? 0);
  const best = Math.max(...scores);
  return {
    key: category,
    label: CATEGORY_LABEL[category],
    sub: `n=${categoryN(REPORT, category)}`,
    cells: Object.fromEntries(
      MODES.map((mode) => {
        const row = summaryRow(REPORT, mode, category);
        return [mode, row?.answer_match != null ? <ScoreCell value={row.answer_match} low={row.answer_match_ci_low ?? 0} high={row.answer_match_ci_high ?? 0} best={row.answer_match === best} /> : null];
      }),
    ),
  };
});

export function Proof() {
  return (
    <section aria-labelledby="proof-title" className="mx-auto max-w-content px-6 pt-24 md:pt-[104px]">
      <h2 id="proof-title" className="text-heading font-normal md:text-heading-lg">What the eval says</h2>
      <p className="mt-4 mb-10 max-w-[60ch] text-body-lg text-muted-fg">
        {REPORT.answerable + REPORT.unanswerable} questions with gold answers, scored per mode in eval run {REPORT.run_id.slice(0, 8)}. Answer match, with 95% bootstrap intervals.
      </p>
      <div className="grid gap-12 lg:grid-cols-[1fr_2fr]">
        <div className="flex flex-col gap-8">
          {overall ? (
            <figure className="flex flex-col gap-2">
              <p className="text-display-sm font-normal tabular-nums">{signed(overall.mean_diff)}</p>
              <figcaption className="flex flex-col gap-1">
                <span className="text-body text-fg">Graph local minus hybrid, paired over {overall.n} answerable questions</span>
                <span className="font-mono text-caption text-muted-fg">95% CI [{signedBound(overall.ci_low)}, {signedBound(overall.ci_high)}]</span>
              </figcaption>
            </figure>
          ) : null}
          <ul className="flex flex-col gap-4 text-body text-fg-2">
            <li>
              The gain comes from multi-hop questions: {score("graph_local", "multi_hop_2")} vs {score("hybrid", "multi_hop_2")} on 2-hop, {score("graph_local", "multi_hop_3")} vs {score("hybrid", "multi_hop_3")} on 3-hop.
            </li>
            {flat.length ? <li>No significant difference on {flat.join(" and ")}.</li> : null}
            {thematic?.significant && thematic.mean_diff < 0 ? (
              <li className="text-fg">
                Thematic questions go the other way: {score("graph_local", "thematic")} vs {score("hybrid", "thematic")}, a significant {signed(thematic.mean_diff)}. Hybrid stays the better choice there.
              </li>
            ) : null}
          </ul>
          <Link href="/benchmarks" className="inline-flex text-body text-fg underline decoration-line underline-offset-4 transition-colors duration-150 ease-std hover:decoration-fg">
            All five modes and the caveats
          </Link>
        </div>
        <div className="min-w-0">
          <ModeTable caption="Answer match by question type, with 95% CI" modes={MODES} spotlight="graph_local" rows={rows} minWidth="min-w-0" />
        </div>
      </div>
    </section>
  );
}
