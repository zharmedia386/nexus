"use client";

import { useEffect, useState, type ReactNode } from "react";
import { DiffCell, JudgeBars, ModeTable, Ring, ScoreCell, type ModeRow } from "@/components/eval/charts";
import {
  ANSWERABLE,
  BASELINE,
  CATEGORY_LABEL,
  MODES,
  MODE_LABEL,
  SPOTLIGHT,
  caveats,
  categoryN,
  diffRow,
  fixed,
  headline,
  seconds,
  summaryRow,
} from "@/components/eval/derive";
import { Card } from "@/components/ui/card";
import { Reveal } from "@/components/ui/reveal";
import { API_URL, ApiError, api, apiMessage } from "@/lib/api";
import type { EvalReport, Mode } from "@/lib/types";

type Load = { status: "loading" } | { status: "missing" } | { status: "error"; message: string } | { status: "ready"; report: EvalReport };

const COMPARED = MODES.filter((mode) => mode !== BASELINE);

function Block({ title, note, children, delayMs = 0, narrow = false }: { title: string; note?: ReactNode; children: ReactNode; delayMs?: number; narrow?: boolean }) {
  return (
    <Reveal delayMs={delayMs} className="flex flex-col gap-5">
      <div className={`flex flex-col gap-1 ${narrow ? "" : "md:flex-row md:items-baseline md:justify-between md:gap-6"}`}>
        <h3 className="text-heading-sm">{title}</h3>
        {note ? <p className={`max-w-xl text-ui text-muted-fg ${narrow ? "" : "md:text-right"}`}>{note}</p> : null}
      </div>
      {children}
    </Reveal>
  );
}

const NotRun = ({ what }: { what: string }) => (
  <p className="rounded-panel border border-dashed border-ash px-4 py-6 text-ui text-fg-2">
    <span className="font-mono text-mono">not run</span> · {what}
  </p>
);

function answerRows(report: EvalReport): ModeRow[] {
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

function diffRows(report: EvalReport, domain: number): ModeRow[] {
  return ANSWERABLE.map((category) => {
    const cells: ModeRow["cells"] = {};
    for (const mode of COMPARED) {
      const diff = diffRow(report, mode, category);
      if (diff) cells[mode] = <DiffCell diff={diff} domain={domain} />;
    }
    const n = report.diffs.find((row) => row.category === category)?.n;
    return { key: category, label: CATEGORY_LABEL[category], sub: n === undefined ? undefined : `n=${n} pairs`, cells };
  });
}

function costRows(report: EvalReport): ModeRow[] {
  const all = (mode: Mode) => summaryRow(report, mode, "all");
  const unanswerable = (mode: Mode) => summaryRow(report, mode, "unanswerable");
  const cell = (text: string | undefined) => (text === undefined ? undefined : <span className="font-mono text-body tabular-nums">{text}</span>);
  const row = (key: string, label: string, sub: string | undefined, read: (mode: Mode) => string | undefined): ModeRow => ({
    key,
    label,
    sub,
    cells: Object.fromEntries(MODES.map((mode) => [mode, cell(read(mode))])),
  });
  const abstainN = unanswerable(SPOTLIGHT)?.n;
  return [
    row("p50", "Latency p50", "end to end", (mode) => { const row = all(mode); return row && seconds(row.p50_ms); }),
    row("p95", "Latency p95", "end to end", (mode) => { const row = all(mode); return row && seconds(row.p95_ms); }),
    row("calls", "LLM calls", "mean per question", (mode) => { const row = all(mode); return row && fixed(row.mean_llm_calls, 1); }),
    row("abstain", "Abstain accuracy", abstainN === undefined ? "unanswerable" : `unanswerable, n=${abstainN}`, (mode) => {
      const value = unanswerable(mode)?.abstain_accuracy;
      return value === undefined ? undefined : fixed(value);
    }),
  ];
}

function GraphQuality({ graph }: { graph: NonNullable<EvalReport["graph"]> }) {
  const { relations, er } = graph;
  const facts = [
    er ? { value: `${er.ticker_links}/${er.ticker_total}`, label: "ticker links resolved" } : null,
    er ? { value: String(er.collision_merges), label: "name-collision merges" } : null,
    { value: String(graph.docs), label: "documents scored" },
  ].filter((fact) => fact !== null);
  return (
    <Card className="flex flex-col gap-6 p-5 md:p-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <Ring value={graph.entity_macro.f1} label="Entity F1" detail={`macro · support ${graph.entity_macro.support}`} />
        <Ring value={relations.macro.f1} label="Relation F1" detail={`macro · support ${relations.macro.support}`} />
        {er ? <Ring value={er.f1} label="Entity resolution F1" detail={`P ${fixed(er.precision)} · R ${fixed(er.recall)}`} /> : null}
        <Ring value={relations.temporal_accuracy} label="Temporal accuracy" detail={`${relations.temporal_support} dated relations`} />
      </div>
      <dl className="grid grid-cols-3 gap-3 border-t border-line pt-5">
        {facts.map((fact) => (
          <div key={fact.label} className="flex flex-col gap-0.5">
            <dt className="order-2 text-caption text-muted-fg">{fact.label}</dt>
            <dd className="order-1 font-mono text-subheading tabular-nums">{fact.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function Report({ report }: { report: EvalReport }) {
  const lines = headline(report);
  const widest = Math.max(...report.diffs.map((row) => Math.max(Math.abs(row.ci_low), Math.abs(row.ci_high))), 0.25);
  const domain = Math.ceil(widest * 10) / 10;
  const model = report.models.LLM_MODEL;
  return (
    <div className="flex flex-col gap-16 md:gap-20">
      <Reveal className="flex flex-col gap-5">
        {lines.length ? (
          <p className="max-w-[56rem] text-heading-sm text-balance">
            {lines[0]} <span className="text-fg-2">{lines[1]}</span>
          </p>
        ) : null}
        <p className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-caption text-muted-fg">
          <span>run {report.run_id.slice(0, 8)}</span>
          {model ? <span>· {model}</span> : null}
          <span>· {report.answerable + report.unanswerable} questions × {MODES.length} modes</span>
          <span>· claim split {report.claim_split_version}</span>
          <span>· 95% paired bootstrap CI</span>
          <a href={`${API_URL}/eval/report`} download="eval-report.json" className="rounded-sm text-fg underline decoration-line underline-offset-4 hover:decoration-fg">
            Download JSON
          </a>
        </p>
      </Reveal>

      <Block title="Answer match by question type" note={<>Share of answers naming the gold entities, with 95% CI. A dot marks the best mode in each row; the dark column is {MODE_LABEL[SPOTLIGHT].toLowerCase()}.</>}>
        <ModeTable caption="answer_match with 95% confidence interval, by question type and retrieval mode" modes={MODES} spotlight={SPOTLIGHT} rows={answerRows(report)} minWidth="min-w-[760px]" />
      </Block>

      <Block title={`Difference vs ${MODE_LABEL[BASELINE].toLowerCase()}`} note={`Paired bootstrap on the same questions. Intervals span ±${fixed(domain)} around zero; colour only where the 95% CI excludes 0.`}>
        <ModeTable caption={`answer_match difference against ${BASELINE} with 95% CI and significance`} modes={COMPARED} rows={diffRows(report, domain)} minWidth="min-w-[720px]" />
      </Block>

      <Block title="Cost" note="Latency and model calls across all questions; abstain accuracy on the questions with no answer in the corpus.">
        <ModeTable caption="Latency, LLM calls and abstain accuracy by retrieval mode" modes={MODES} spotlight={SPOTLIGHT} rows={costRows(report)} minWidth="min-w-[680px]" rowHeader="Measure" />
      </Block>

      <div className="grid gap-16 lg:grid-cols-2 lg:gap-8">
        <Block narrow title="Graph quality" note={report.graph ? "Extraction scored against the planted world." : undefined}>
          {report.graph ? <GraphQuality graph={report.graph} /> : <NotRun what="graph extraction has not been scored against ground truth." />}
        </Block>
        <Block narrow title="Thematic judge" note={report.judges?.length ? "Pairwise LLM verdicts, judged in both answer orders; a disagreement between the two orders counts as a tie." : undefined} delayMs={80}>
          {report.judges?.length ? (
            <Card className="flex flex-col gap-8 p-5 md:p-6">
              {report.judges.map((judge) => (
                <JudgeBars key={`${judge.mode_a}-${judge.mode_b}`} judge={judge} />
              ))}
            </Card>
          ) : (
            <NotRun what="no pairwise judge results in this report." />
          )}
        </Block>
      </div>

      <Reveal>
        <section aria-labelledby="eval-caveats" className="rounded-card border border-line p-5 md:p-8">
          <h3 id="eval-caveats" className="mb-4 text-heading-sm">Read before quoting</h3>
          <ul className="grid gap-3 md:grid-cols-2 md:gap-x-10">
            {caveats(report).map((item) => (
              <li key={item} className="flex gap-3 text-body text-fg-2">
                <span aria-hidden="true" className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-ash" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <p className="mt-6 font-mono text-caption text-muted-fg">
            Full write-up: docs/report/eval-report.md in the repository, generated from run {report.run_id}.
          </p>
        </section>
      </Reveal>
    </div>
  );
}

function Skeleton() {
  return (
    <div aria-busy="true" aria-label="Loading evaluation report" className="flex flex-col gap-6">
      <div className="h-16 max-w-3xl animate-pulse rounded-panel bg-surface motion-reduce:animate-none" />
      <div className="h-[420px] animate-pulse rounded-card bg-surface motion-reduce:animate-none" />
    </div>
  );
}

export function EvalSection() {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      try {
        setLoad({ status: "ready", report: await api.evalReport(controller.signal) });
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) setLoad({ status: "missing" });
        else setLoad({ status: "error", message: apiMessage(error) });
      }
    };
    void run();
    return () => controller.abort();
  }, [attempt]);

  return (
    <div className="mx-auto max-w-content px-6">
      {load.status === "loading" ? <Skeleton /> : null}
      {load.status === "missing" ? <NotRun what="no evaluation report has been generated yet." /> : null}
      {load.status === "error" ? (
        <Card role="alert" className="flex flex-wrap items-center justify-between gap-4 p-6">
          <p className="text-body text-fg-2">{load.message}</p>
          <button type="button" onClick={() => { setLoad({ status: "loading" }); setAttempt((value) => value + 1); }} className="rounded-pill border border-line px-4 py-1.5 text-ui hover:bg-line">
            Retry
          </button>
        </Card>
      ) : null}
      {load.status === "ready" ? <Report report={load.report} /> : null}
    </div>
  );
}
