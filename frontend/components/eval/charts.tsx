import type { ReactNode } from "react";
import { ANSWERABLE, CATEGORY_LABEL, MODES, MODE_LABEL, bound, categoryN, fixed, signed, signedBound, summaryRow } from "@/components/eval/derive";
import type { EvalDiff, EvalJudge, EvalReport, Mode } from "@/lib/types";

export type ModeRow = { key: string; label: ReactNode; sub?: ReactNode; cells: Partial<Record<Mode, ReactNode>> };

type ModeTableProps = { caption: string; modes: Mode[]; spotlight?: Mode; rows: ModeRow[]; minWidth: string; rowHeader?: string };

// Design-system comparison table: one mode per column, the spotlight mode as a dark column.
export function ModeTable({ caption, modes, spotlight, rows, minWidth, rowHeader = "Question type" }: ModeTableProps) {
  return (
    <div className="relative -mx-6 overflow-x-auto px-6 pb-2" tabIndex={0} role="region" aria-label={caption}>
      <table className={`w-full border-separate border-spacing-0 text-left ${minWidth}`}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 bg-bg pb-3 align-bottom text-ui font-medium text-fg-2">{rowHeader}</th>
            {modes.map((mode) => (
              <th
                key={mode}
                scope="col"
                data-spotlight={mode === spotlight || undefined}
                className={`px-2 pt-4 pb-3 align-bottom text-ui font-medium sm:px-4 ${mode === spotlight ? "rounded-t-panel bg-spotlight text-paper" : "text-fg-2"}`}
              >
                {MODE_LABEL[mode]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const last = index === rows.length - 1;
            return (
              <tr key={row.key}>
                <th scope="row" className="sticky left-0 z-10 border-t border-line bg-bg py-3 pr-4 align-top font-normal">
                  <span className="block text-ui text-fg">{row.label}</span>
                  {row.sub ? <span className="block font-mono text-caption text-muted-fg">{row.sub}</span> : null}
                </th>
                {modes.map((mode) => (
                  <td
                    key={mode}
                    data-spotlight={mode === spotlight || undefined}
                    className={`border-t px-2 py-3 align-top sm:px-4 ${
                      mode === spotlight ? `border-paper/10 bg-spotlight text-paper ${last ? "rounded-b-panel" : ""}` : "border-line"
                    }`}
                  >
                    {row.cells[mode] ?? <span className="text-muted-fg">–</span>}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {modes.length > 3 ? <p aria-hidden="true" className="sticky left-0 pt-3 text-caption text-muted-fg sm:hidden">Scroll sideways for every mode</p> : null}
    </div>
  );
}

type ScoreProps = { value: number; low: number; high: number; best: boolean };

// Value over a 0–1 CI track; inherits currentColor so it reads on the dark column too.
export function ScoreCell({ value, low, high, best }: ScoreProps) {
  return (
    <div className="flex flex-col gap-1.5" title={`${fixed(value)}, 95% CI ${bound(low)}–${bound(high)}`}>
      <span className={`font-mono text-body tabular-nums ${best ? "font-medium" : "opacity-75"}`}>
        {fixed(value)}
        {best ? <span className="sr-only"> (best in row)</span> : null}
        {best ? <span aria-hidden="true" className="ml-1.5 inline-block size-1.5 -translate-y-0.5 rounded-full bg-current" /> : null}
      </span>
      <span aria-hidden="true" className="relative block h-1 w-full max-w-[104px] rounded-pill bg-current/15">
        <span className="absolute inset-y-0 rounded-pill bg-current/45" style={{ left: `${low * 100}%`, width: `${Math.max(high - low, 0.01) * 100}%` }} />
        <span className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-current" style={{ left: `${value * 100}%` }} />
      </span>
      <span className="font-mono text-caption whitespace-nowrap tabular-nums opacity-75">
        <span className="sr-only">95% CI </span>
        {bound(low)}–{bound(high)}
      </span>
    </div>
  );
}

type DiffProps = { diff: EvalDiff; domain: number };

const tone = (diff: EvalDiff) => (!diff.significant ? "flat" : diff.mean_diff > 0 ? "better" : "worse");

// One forest-plot row segment: CI interval around a zero line, coloured only when the CI excludes 0.
export function DiffCell({ diff, domain }: DiffProps) {
  const x = (value: number) => 50 + (value / domain) * 50;
  const verdict = tone(diff);
  const stroke = verdict === "better" ? "var(--verdict-ok)" : verdict === "worse" ? "var(--verdict-bad)" : "var(--ash)";
  return (
    <div data-verdict={verdict} className="flex min-w-[132px] flex-col gap-1.5">
      <span aria-hidden="true" className="relative block h-3">
        <span className="absolute inset-y-0 left-1/2 w-px bg-ash/70" />
        <span className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded-pill" style={{ left: `${x(diff.ci_low)}%`, width: `${Math.max(x(diff.ci_high) - x(diff.ci_low), 0.5)}%`, background: stroke }} />
        <span className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-bg" style={{ left: `${x(diff.mean_diff)}%`, background: stroke }} />
      </span>
      <span className="flex flex-wrap items-baseline gap-x-1.5 font-mono text-caption tabular-nums">
        <span className={`text-ui ${verdict === "flat" ? "text-fg-2" : "font-medium text-fg"}`}>{signed(diff.mean_diff)}</span>
        <span className="text-muted-fg">
          <span className="sr-only">95% CI </span>[{signedBound(diff.ci_low)}, {signedBound(diff.ci_high)}]
        </span>
        {verdict === "flat" ? (
          <span className="sr-only">not significant</span>
        ) : (
          <span className={`rounded-pill px-1.5 font-sans text-caption ${verdict === "better" ? "bg-verdict-ok-bg text-verdict-ok" : "bg-verdict-bad-bg text-verdict-bad"}`}>
            {verdict === "better" ? "better" : "worse"}
            <span className="sr-only">, significant</span>
          </span>
        )}
      </span>
    </div>
  );
}

type RingProps = { value: number; label: string; detail: string };

export function Ring({ value, label, detail }: RingProps) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  return (
    <figure className="flex items-center gap-4">
      <svg viewBox="0 0 64 64" className="size-16 shrink-0 -rotate-90" role="img" aria-label={`${label} ${fixed(value)}`}>
        <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--line)" strokeWidth="5" />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="var(--fg)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value)}
        />
      </svg>
      <figcaption className="flex flex-col">
        <span className="font-mono text-heading-sm tabular-nums">{fixed(value)}</span>
        <span className="text-ui text-fg">{label}</span>
        <span className="font-mono text-caption text-muted-fg">{detail}</span>
      </figcaption>
    </figure>
  );
}

const SWATCH = { a: "var(--node-company)", tie: "var(--ash)", b: "var(--node-person)" };

export function JudgeBars({ judge }: { judge: EvalJudge }) {
  const nameA = MODE_LABEL[judge.mode_a];
  const nameB = MODE_LABEL[judge.mode_b];
  const lengthA = judge.mean_chars[judge.mode_a];
  const lengthB = judge.mean_chars[judge.mode_b];
  const n = Object.values(judge.win_rates)[0]?.n;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-body">
          {nameA} <span className="text-fg-2">vs</span> {nameB}
        </h4>
        <span className="font-mono text-caption text-muted-fg">
          {judge.categories.join(", ")} · n={n ?? "–"} · prompt v{judge.judge_prompt_version}
        </span>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-caption text-fg-2" aria-label="Legend">
        {[
          [SWATCH.a, `${nameA} wins`],
          [SWATCH.tie, "Tie"],
          [SWATCH.b, `${nameB} wins`],
        ].map(([color, text]) => (
          <li key={text} className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px]" style={{ background: color }} aria-hidden="true" />
            {text}
          </li>
        ))}
      </ul>
      <dl className="flex flex-col gap-3">
        {Object.entries(judge.win_rates).map(([criterion, rate]) => {
          const total = rate.a_wins + rate.ties + rate.b_wins || 1;
          const segments = [
            { key: "a", count: rate.a_wins, color: SWATCH.a, text: `${nameA} wins` },
            { key: "tie", count: rate.ties, color: SWATCH.tie, text: "ties" },
            { key: "b", count: rate.b_wins, color: SWATCH.b, text: `${nameB} wins` },
          ];
          return (
            <div key={criterion} className="grid grid-cols-[112px_1fr] items-center gap-x-3 gap-y-1 sm:grid-cols-[120px_1fr_88px]">
              <dt className="text-ui capitalize">{criterion}</dt>
              <dd className="flex h-2.5 gap-0.5 overflow-hidden rounded-[4px]" aria-hidden="true">
                {segments.map((segment) =>
                  segment.count ? (
                    <span key={segment.key} title={`${segment.count} ${segment.text}`} style={{ flexGrow: segment.count / total, background: segment.color }} />
                  ) : null,
                )}
              </dd>
              <dd className="col-start-2 font-mono text-caption tabular-nums text-fg-2 sm:col-start-3 sm:text-right">
                <span className="sr-only">
                  {segments.map((segment) => `${segment.count} ${segment.text}`).join(", ")}
                  {rate.errors ? `, ${rate.errors} errors` : ""}
                </span>
                <span aria-hidden="true">
                  {rate.a_wins} · {rate.ties} · {rate.b_wins}
                  {rate.errors ? ` (${rate.errors} err)` : ""}
                </span>
              </dd>
            </div>
          );
        })}
      </dl>
      {lengthA !== undefined && lengthB !== undefined ? (
        <p className="text-caption text-muted-fg">
          Mean answer length: {nameA} <span className="tabular-nums">{lengthA.toLocaleString("en-US")}</span> chars, {nameB}{" "}
          <span className="tabular-nums">{lengthB.toLocaleString("en-US")}</span> chars.
        </p>
      ) : null}
    </div>
  );
}

export function answerRows(report: EvalReport): ModeRow[] {
  return ANSWERABLE.map((category) => {
    const scores = MODES.map((mode) => summaryRow(report, mode, category)?.answer_match ?? null);
    const top = Math.max(...scores.map((score) => score ?? -1));
    // No "best" mark when every mode ties.
    const contested = scores.some((score) => score !== null && score < top);
    const cells: ModeRow["cells"] = {};
    for (const mode of MODES) {
      const row = summaryRow(report, mode, category);
      if (!row || row.answer_match === null || row.answer_match_ci_low === null || row.answer_match_ci_high === null) continue;
      cells[mode] = (
        <ScoreCell value={row.answer_match} low={row.answer_match_ci_low} high={row.answer_match_ci_high} best={contested && row.answer_match === top} />
      );
    }
    return { key: category, label: CATEGORY_LABEL[category], sub: `n=${categoryN(report, category)}`, cells };
  });
}
