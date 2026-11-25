"use client";

import { Fragment, useState } from "react";
import type { OnCite } from "@/components/ask/answer-text";
import type { GraphPath } from "@/lib/types";

const relLabel = (relType: string) => relType.toLowerCase().replaceAll("_", " ");

function Connector({ forward }: { forward: boolean }) {
  return (
    <svg
      viewBox="0 0 64 12"
      data-direction={forward ? "forward" : "backward"}
      className="h-3 w-16 overflow-visible sm:w-20"
      fill="none"
      aria-hidden="true"
    >
      <line x1="6" y1="6" x2="58" y2="6" stroke="#ffffff6b" strokeWidth="1.25" strokeLinecap="round" strokeDasharray="3 5" className="animate-flow-travel" style={forward ? undefined : { animationDirection: "reverse" }} />
      <path d={forward ? "M55 2.5 59.5 6 55 9.5" : "M9 2.5 4.5 6 9 9.5"} stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type PathStripProps = { path: GraphPath; onCite: OnCite };

export function PathStrip({ path, onCite }: PathStripProps) {
  const [open, setOpen] = useState<number | null>(null);
  const hop = open === null ? undefined : path.hops[open];
  // Chunks beyond the stored quotes still deserve a way to open them.
  const extraChunkIds = hop ? hop.chunk_ids.slice(hop.quotes.length) : [];

  return (
    <div data-surface="dark" className="rounded-panel bg-ink-night p-4 text-paper">
      <p className="mb-3 flex items-center justify-between font-mono text-caption text-paper/60">
        <span>Graph path · {path.hops.length} {path.hops.length === 1 ? "hop" : "hops"}</span>
        <span className="hidden sm:inline">select a hop for its quotes</span>
      </p>
      <ol className="flex flex-wrap items-center gap-y-2">
        {path.hops.map((item, index) => {
          const active = open === index;
          return (
            <Fragment key={index}>
              {index === 0 ? <Node name={item.src_name} active={active} /> : null}
              <li className="flex">
                <button
                  type="button"
                  aria-expanded={active}
                  aria-label={`${item.forward ? `${item.src_name} ${relLabel(item.rel_type)} ${item.dst_name}` : `${item.dst_name} ${relLabel(item.rel_type)} ${item.src_name}`}. Show quotes`}
                  onClick={() => setOpen(active ? null : index)}
                  className={`group flex flex-col items-center rounded-control px-1 py-0.5 transition-[background-color,color] duration-150 ease-std ${active ? "bg-paper/12 text-paper" : "text-paper/70 hover:text-paper"}`}
                >
                  <span className="mb-1 font-mono text-caption leading-none">{relLabel(item.rel_type)}</span>
                  <Connector forward={item.forward} />
                </button>
              </li>
              <Node name={item.dst_name} active={active || open === index + 1} />
            </Fragment>
          );
        })}
      </ol>
      {hop ? (
        <ul key={open} className="mt-4 flex flex-col gap-2 border-t border-paper/10 pt-3">
          {hop.quotes.map((quote, index) => (
            <li key={index} style={{ animationDelay: `${index * 40}ms` }} className="flex animate-item-in items-start gap-3 text-ui text-paper/80">
              <span aria-hidden="true" className="mt-1.5 h-3 w-px shrink-0 bg-paper/40" />
              <span className="flex-1">“{quote}”</span>
              {hop.chunk_ids[index] ? (
                <button
                  type="button"
                  onClick={(event) => onCite(hop.chunk_ids[index], event.currentTarget)}
                  className="shrink-0 rounded-pill border border-paper/20 px-2 py-0.5 font-mono text-caption text-paper/80 transition-colors duration-150 ease-std hover:bg-paper/10 hover:text-paper"
                >
                  {hop.chunk_ids[index]}
                </button>
              ) : null}
            </li>
          ))}
          {extraChunkIds.length ? (
            <li className="flex flex-wrap items-center gap-2">
              {extraChunkIds.map((chunkId) => (
                <button key={chunkId} type="button" onClick={(event) => onCite(chunkId, event.currentTarget)} className="shrink-0 rounded-pill border border-paper/20 px-2 py-0.5 font-mono text-caption text-paper/80 transition-colors duration-150 ease-std hover:bg-paper/10 hover:text-paper">
                  {chunkId}
                </button>
              ))}
            </li>
          ) : null}
          {hop.quotes.length === 0 && extraChunkIds.length === 0 ? <li className="text-ui text-paper/60">No quotes stored for this edge.</li> : null}
        </ul>
      ) : null}
    </div>
  );
}

function Node({ name, active }: { name: string; active: boolean }) {
  return (
    <li className="flex items-center gap-2 rounded-pill border border-paper/20 bg-paper/5 px-3 py-1 text-ui">
      <span aria-hidden="true" className={`size-1.5 rounded-full bg-paper ${active ? "animate-flow-pulse" : "opacity-60"}`} />
      {name}
    </li>
  );
}
