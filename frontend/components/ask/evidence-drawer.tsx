"use client";

import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { api, apiMessage } from "@/lib/api";
import type { ChunkRow, DocumentRow } from "@/lib/types";

type Evidence =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; chunk: ChunkRow; doc: DocumentRow };

const FOCUSABLE = 'button, [href], [tabindex]:not([tabindex="-1"])';

type DrawerProps = { chunkId: string; opener: HTMLElement | null; onClose: () => void };

export function EvidenceDrawer({ chunkId, opener, onClose }: DrawerProps) {
  const [evidence, setEvidence] = useState<Evidence>({ status: "loading" });
  const panelRef = useRef<HTMLDivElement>(null);
  const markRef = useRef<HTMLElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const chunk = await api.chunk(chunkId, controller.signal);
        const doc = await api.document(chunk.doc_id, controller.signal);
        setEvidence({ status: "ready", chunk, doc });
      } catch (error) {
        if (controller.signal.aborted) return;
        setEvidence({ status: "error", message: apiMessage(error) });
      }
    };
    void load();
    return () => controller.abort();
  }, [chunkId]);

  // Focus moves into the dialog on open and back to the opener on close (Safari never focuses clicked buttons).
  useLayoutEffect(() => {
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, [opener]);

  useEffect(() => {
    // Scroll only the drawer; scrollIntoView would also move the page behind the scrim.
    const container = scrollRef.current;
    const mark = markRef.current;
    if (evidence.status !== "ready" || !container || !mark) return;
    container.scrollTop = mark.offsetTop - container.clientHeight / 4;
  }, [evidence]);

  // Backend offsets are Python code-point indices; JS strings index UTF-16 units.
  const codePoints = evidence.status === "ready" ? Array.from(evidence.doc.content) : [];

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !panelRef.current) return;
    const items = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const first = items[0];
    const last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  };

  return (
    <div className="fixed inset-0 z-40" onKeyDown={onKeyDown}>
      <div aria-hidden="true" onClick={onClose} className="absolute inset-0 animate-scrim-in bg-black/30" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        data-surface="dark"
        className="glass-strong absolute inset-x-0 bottom-0 flex max-h-[88dvh] animate-sheet-in flex-col rounded-b-none text-paper md:inset-y-3 md:right-3 md:left-auto md:max-h-none md:w-[520px] md:animate-drawer-in md:rounded-b-[16px]"
      >
        <header className="flex items-start justify-between gap-4 border-b border-paper/10 p-5">
          <div className="min-w-0">
            <p className="mb-1 font-mono text-caption text-paper/60">
              Evidence · {evidence.status === "ready" ? evidence.doc.id : "…"} · {chunkId}
            </p>
            <h2 id="evidence-title" className="text-heading-sm font-normal text-balance">
              {evidence.status === "ready" ? evidence.doc.title : evidence.status === "error" ? "Evidence unavailable" : "Loading source…"}
            </h2>
            {evidence.status === "ready" ? (
              <p className="mt-2 font-mono text-caption text-paper/60">
                chars {evidence.chunk.start_char}–{evidence.chunk.end_char} · {evidence.doc.doc_type} · {evidence.doc.lang} · {evidence.doc.year}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            data-autofocus
            onClick={onClose}
            aria-label="Close evidence"
            className="grid size-9 shrink-0 place-items-center rounded-pill bg-paper/10 transition-[background-color,transform] duration-150 ease-std hover:bg-paper/20 active:scale-[.94]"
          >
            <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
              <path d="m4 4 8 8m0-8-8 8" />
            </svg>
          </button>
        </header>
        <div ref={scrollRef} tabIndex={0} aria-label="Document text" className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain p-5">
          {evidence.status === "loading" ? (
            <div className="flex flex-col gap-2" aria-busy="true">
              {[92, 78, 96, 64, 88].map((width) => (
                <span key={width} className="h-3 animate-pulse rounded-pill bg-paper/10" style={{ width: `${width}%` }} />
              ))}
            </div>
          ) : evidence.status === "error" ? (
            <p role="alert" className="text-body text-paper/80">{evidence.message}</p>
          ) : (
            <p className="text-body whitespace-pre-wrap text-paper/65">
              {codePoints.slice(0, evidence.chunk.start_char).join("")}
              <mark ref={markRef} className="bg-highlight text-paper">
                {codePoints.slice(evidence.chunk.start_char, evidence.chunk.end_char).join("")}
              </mark>
              {codePoints.slice(evidence.chunk.end_char).join("")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
