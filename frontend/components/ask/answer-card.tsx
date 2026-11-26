"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnswerText, type OnCite } from "@/components/ask/answer-text";
import { PathStrip } from "@/components/ask/path-strip";
import { Chip } from "@/components/ui/chip";
import type { Answer, Mode } from "@/lib/types";

export type Run =
  | { status: "loading"; startedAt: number }
  | { status: "done"; answer: Answer }
  | { status: "error"; message: string }
  | { status: "cancelled" };

export const MODE_LABELS: Record<Mode, string> = {
  rag: "Vector RAG",
  hybrid: "Hybrid",
  graph_local: "Graph local",
  graph_global: "Graph global",
  auto: "Auto router",
};

const THINKING: Record<Mode, string> = {
  rag: "Searching chunks",
  hybrid: "Fusing dense and keyword hits",
  graph_local: "Walking the graph",
  graph_global: "Reading community summaries",
  auto: "Routing the question",
};

// Rambling answers would stretch one card far past its comparison partner.
const LONG_ANSWER = 900;

function Elapsed({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, []);
  return <span className="font-mono text-mono tabular-nums text-fg-2">{((now - startedAt) / 1000).toFixed(1)}s</span>;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-mono text-mono tabular-nums text-fg">{value}</span>
      <span className="text-caption text-fg-2">{label}</span>
    </span>
  );
}

type AnswerCardProps = {
  mode: Mode;
  run: Run;
  index: number;
  onCite: OnCite;
  onCancel: () => void;
  onRetry: () => void;
};

export function AnswerCard({ mode, run, index, onCite, onCancel, onRetry }: AnswerCardProps) {
  const answer = run.status === "done" ? run.answer : null;
  const [expanded, setExpanded] = useState(false);
  const long = (answer?.text.length ?? 0) > LONG_ANSWER;
  const clamped = long && !expanded;

  return (
    <article
      aria-labelledby={`card-${mode}`}
      aria-busy={run.status === "loading"}
      style={{ animationDelay: `${index * 70}ms` }}
      className="flex min-h-[320px] animate-overlay-in flex-col gap-5 rounded-card bg-surface p-6"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`card-${mode}`} className="text-heading-sm font-normal">{MODE_LABELS[mode]}</h2>
        <div className="flex items-center gap-2">
          {answer?.routed_mode ? <Chip mono className="h-6 bg-bg">→ {answer.routed_mode}</Chip> : null}
          <span className="font-mono text-caption text-fg-2">{mode}</span>
        </div>
      </header>

      {run.status === "loading" ? (
        <div className="flex flex-1 flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <span role="status" className="t-shimmer text-body" data-text={THINKING[mode]}>{THINKING[mode]}</span>
            <Elapsed startedAt={run.startedAt} />
          </div>
          <div className="flex flex-col gap-2.5" aria-hidden="true">
            {[96, 88, 72].map((width) => (
              <span key={width} className="h-3 animate-pulse rounded-pill bg-line" style={{ width: `${width}%` }} />
            ))}
          </div>
          <button type="button" onClick={onCancel} className="mt-auto -ml-3 self-start rounded-pill px-3 py-1.5 text-ui text-fg-2 transition-colors duration-150 ease-std hover:bg-line hover:text-fg">
            Cancel
          </button>
        </div>
      ) : null}

      {run.status === "error" || run.status === "cancelled" ? (
        <div role={run.status === "error" ? "alert" : undefined} className="flex flex-1 flex-col items-start gap-3">
          <p className="text-body text-fg-2">
            {run.status === "error" ? <>This mode failed: <span className="font-mono text-mono text-fg">{run.message}</span></> : "Cancelled."}
          </p>
          <button type="button" onClick={onRetry} className="rounded-pill border border-line px-3 py-1.5 text-ui transition-colors duration-150 ease-std hover:bg-line">
            Run again
          </button>
        </div>
      ) : null}

      {answer ? (
        <>
          <div className="flex-1">
            <div
              id={`answer-${mode}`}
              className={clamped ? "max-h-[26rem] overflow-hidden [mask-image:linear-gradient(to_bottom,#000_70%,transparent)]" : ""}
            >
              <AnswerText answer={answer} onCite={onCite} />
            </div>
            {long ? (
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={`answer-${mode}`}
                onClick={() => setExpanded((value) => !value)}
                className="mt-2 -ml-3 rounded-pill px-3 py-1.5 text-ui text-fg-2 transition-colors duration-150 ease-std hover:bg-line hover:text-fg"
              >
                {expanded ? "Show less" : `Show full answer · ${answer.text.length.toLocaleString("en")} chars`}
              </button>
            ) : null}
          </div>
          {answer.graph_paths.map((path, pathIndex) => (
            <PathStrip key={pathIndex} path={path} onCite={onCite} />
          ))}
          {answer.communities.length ? (
            <div className="flex flex-col gap-2">
              <p className="text-caption text-fg-2">Communities used</p>
              <ul className="flex flex-wrap gap-1.5">
                {answer.communities.map((id) => (
                  <li key={id}>
                    <Link
                      href={`/themes?c=${encodeURIComponent(id)}`}
                      className="inline-flex h-7 items-center rounded-pill border border-line px-3 font-mono text-mono transition-colors duration-150 ease-std hover:bg-line">
                      {id}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <footer className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-4">
            <Meta value={`${(answer.latency_ms / 1000).toFixed(1)}s`} label="latency" />
            <Meta value={String(answer.llm_calls)} label={answer.llm_calls === 1 ? "LLM call" : "LLM calls"} />
            <Meta value={String(answer.verify_calls)} label={answer.verify_calls === 1 ? "verify call" : "verify calls"} />
            {answer.abstained ? <Chip className="h-6 border-ash text-fg-2">abstained</Chip> : null}
          </footer>
        </>
      ) : null}
    </article>
  );
}
