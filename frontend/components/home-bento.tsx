"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { Chip } from "@/components/ui/chip";
import { Reveal } from "@/components/ui/reveal";
import { api } from "@/lib/api";
import { onSectionLink, type SectionId } from "@/lib/sections";
import type { EvalReport, EvalSummaryRow, GraphStats, Mode } from "@/lib/types";

type Stats = {
  report: EvalReport | null;
  graph: GraphStats | null;
  communities: number | null;
  loading: boolean;
};

const percent = (value: number) => `${Math.round(value * 100)}%`;
const overall = (report: EvalReport | null, mode: Mode): EvalSummaryRow | undefined =>
  report?.summary.find((row) => row.mode === mode && row.category === "all");

function useHomeStats(): Stats {
  const [stats, setStats] = useState<Stats>({ report: null, graph: null, communities: null, loading: true });

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      const [report, graph, communities] = await Promise.allSettled([
        api.evalReport(controller.signal),
        api.graphStats(controller.signal),
        api.communities(0, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setStats({
        report: report.status === "fulfilled" ? report.value : null,
        graph: graph.status === "fulfilled" ? graph.value : null,
        communities: communities.status === "fulfilled" ? communities.value.length : null,
        loading: false,
      });
    };
    void load();
    return () => controller.abort();
  }, []);

  return stats;
}

function Stat({ value, label, loading }: { value: string | null; label: string; loading: boolean }) {
  return (
    <p className="flex items-baseline gap-2">
      <span className={`text-heading font-normal tabular-nums ${loading ? "animate-pulse text-ash" : ""}`}>
        {value ?? "—"}
      </span>
      <span className="text-ui text-fg-2">{value || loading ? label : "API offline"}</span>
    </p>
  );
}

type EntryProps = {
  section: SectionId;
  index: string;
  title: string;
  body: string;
  className?: string;
  delayMs: number;
  children: ReactNode;
};

function Entry({ section, index, title, body, className = "", delayMs, children }: EntryProps) {
  return (
    <Reveal delayMs={delayMs} className={className}>
      <Link
        href={`/#${section}`}
        onClick={(event) => onSectionLink(event, section)}
        className="group flex h-full min-h-[300px] flex-col justify-between gap-8 rounded-card bg-surface p-7 transition-[transform,background-color] duration-200 ease-std hover:bg-line/60 active:scale-[.99] md:p-8"
      >
        <div>
          <div className="mb-6 flex items-center justify-between">
            <span className="font-mono text-mono text-fg-2">{index}</span>
            <svg viewBox="0 0 16 16" className="size-4 text-fg-2 transition-transform duration-200 ease-out group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-fg" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M5 11 11 5M6 5h5v5" />
            </svg>
          </div>
          <h3 className="mb-2 text-heading-sm font-normal">{title}</h3>
          <p className="max-w-sm text-body text-fg-2">{body}</p>
        </div>
        {children}
      </Link>
    </Reveal>
  );
}

function ModeBar({ label, row, highlight }: { label: string; row?: EvalSummaryRow; highlight: boolean }) {
  return (
    <div className="grid grid-cols-[96px_1fr_44px] items-center gap-3">
      <span className="font-mono text-mono text-fg-2">{label}</span>
      <span className="h-2 overflow-hidden rounded-pill bg-line">
        <span
          className={`block h-full origin-left rounded-pill transition-transform duration-500 ease-out ${highlight ? "bg-fg" : "bg-ash"}`}
          style={{ transform: `scaleX(${row?.answer_match ?? 0})` }}
        />
      </span>
      <span className="text-right font-mono text-mono tabular-nums">{row?.answer_match != null ? percent(row.answer_match) : "—"}</span>
    </div>
  );
}

export function HomeBento() {
  const { report, graph, communities, loading } = useHomeStats();
  const graphLocal = overall(report, "graph_local");
  const hybrid = overall(report, "hybrid");
  const auto = overall(report, "auto");

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
      <Entry
        section="ask"
        index="01"
        title="Ask"
        body="Plain RAG, hybrid, graph-local or graph-global, or let the router pick. Claims are verified against their sources."
        className="md:col-span-4"
        delayMs={0}
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex h-12 w-full max-w-md items-center gap-3 rounded-pill bg-bg px-5 text-body text-fg-2 shadow-soft">
            <span className="truncate">Who sits on the board of the parent company?</span>
            <span aria-hidden="true" className="h-5 w-px shrink-0 bg-fg animate-cursor-blink" />
          </div>
          <Stat value={auto ? `${(auto.p50_ms / 1000).toFixed(1)}s` : null} label="p50, auto mode" loading={loading} />
        </div>
      </Entry>
      <Entry
        section="explore"
        index="02"
        title="Explore"
        body="Search an entity, open its neighbourhood, trace a path."
        className="md:col-span-2"
        delayMs={70}
      >
        <div className="flex flex-col gap-2">
          <Stat value={graph?.nodes.toLocaleString("en") ?? null} label="entities" loading={loading} />
          {graph ? <Chip mono className="self-start">{graph.relationships.toLocaleString("en")} relationships</Chip> : null}
        </div>
      </Entry>
      <Entry
        section="themes"
        index="03"
        title="Themes"
        body="Graph communities with summaries you can cite."
        className="md:col-span-2"
        delayMs={140}
      >
        <Stat value={communities?.toString() ?? null} label="communities" loading={loading} />
      </Entry>
      <Entry
        section="eval"
        index="04"
        title="Eval"
        body="Answer match on the full question set. Graph retrieval against the strongest non-graph baseline."
        className="md:col-span-4"
        delayMs={210}
      >
        {report || loading ? (
          <div className="flex flex-col gap-3">
            <ModeBar label="graph_local" row={graphLocal} highlight />
            <ModeBar label="hybrid" row={hybrid} highlight={false} />
          </div>
        ) : (
          <Stat value={null} label="" loading={false} />
        )}
      </Entry>
    </div>
  );
}
