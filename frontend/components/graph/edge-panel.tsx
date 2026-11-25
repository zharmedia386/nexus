"use client";

import { useLayoutEffect, useRef } from "react";
import type { OnCite } from "@/components/ask/answer-text";
import { relLabel, type GraphLink, type Relation } from "@/components/graph/layout";

function details(relation: Relation) {
  const rows: [string, string][] = [];
  if (relation.role) rows.push(["role", relation.role]);
  if (relation.relation) rows.push(["relation", relation.relation]);
  if (relation.pct !== null) rows.push(["stake", `${relation.pct}%`]);
  if (relation.since !== null || relation.until !== null) {
    rows.push(["period", `${relation.since ?? "?"} – ${relation.until ?? "present"}`]);
  }
  return rows;
}

export function QuoteList({ relation, onCite }: { relation: Relation; onCite: OnCite }) {
  if (relation.quotes.length === 0) return <p className="text-ui text-paper/60">No quotes stored for this edge.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {relation.quotes.map((quote, index) => (
        <li key={index} className="flex animate-item-in flex-col items-start gap-2 text-ui text-paper/80" style={{ animationDelay: `${index * 40}ms` }}>
          <q className="border-l border-paper/30 pl-3 text-pretty">{quote}</q>
          {relation.chunkIds[index] ? (
            <button
              type="button"
              onClick={(event) => onCite(relation.chunkIds[index], event.currentTarget)}
              className="ml-3 rounded-pill border border-paper/20 px-2 py-0.5 font-mono text-caption text-paper/80 transition-[background-color,color,transform] duration-150 ease-std hover:bg-paper/10 hover:text-paper active:scale-[.97]"
            >
              {relation.chunkIds[index]}
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export const EDGE_PANEL_ID = "edge-panel";

type EdgePanelProps = { link: GraphLink; onClose: () => void; onCite: OnCite };

export function EdgePanel({ link, onClose, onCite }: EdgePanelProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    closeRef.current?.focus();
  }, [link.key]);

  return (
    <section
      id={EDGE_PANEL_ID}
      aria-labelledby="edge-panel-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
      className="glass absolute inset-x-3 bottom-3 z-10 flex max-h-[62%] animate-overlay-in flex-col text-paper sm:inset-x-auto sm:top-3 sm:right-3 sm:bottom-auto sm:max-h-[calc(100%-24px)] sm:w-[360px]"
    >
      <header className="flex items-start justify-between gap-3 border-b border-paper/10 p-4">
        <div className="min-w-0">
          <p className="mb-1 font-mono text-caption text-paper/60">
            {link.relations.length === 1 ? "Relation" : `${link.relations.length} relations`}{link.onPath ? " · on path" : ""}
          </p>
          <h2 id="edge-panel-title" className="text-subheading font-normal text-balance">
            {link.relations[0].sourceName} <span className="text-paper/50">·</span> {link.relations[0].targetName}
          </h2>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Close relation"
          className="grid size-9 shrink-0 place-items-center rounded-pill bg-paper/10 transition-[background-color,transform] duration-150 ease-std hover:bg-paper/20 active:scale-[.94]"
        >
          <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <path d="m4 4 8 8m0-8-8 8" />
          </svg>
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
        <ol className="flex flex-col gap-5">
          {link.relations.map((relation, index) => (
            <li key={`${relation.type}-${index}`} className="flex flex-col gap-3">
              <p className="text-body">
                {relation.sourceName} <span className="font-mono text-mono text-paper/70">—{relLabel(relation.type)}→</span> {relation.targetName}
              </p>
              {details(relation).length ? (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-ui">
                  {details(relation).map(([term, value]) => (
                    <div key={term} className="contents">
                      <dt className="text-paper/60">{term}</dt>
                      <dd className="font-mono text-paper/90">{value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              <QuoteList relation={relation} onCite={onCite} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
