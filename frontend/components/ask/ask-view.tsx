"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AnswerCard, MODE_LABELS, type Run } from "@/components/ask/answer-card";
import { EvidenceDrawer } from "@/components/ask/evidence-drawer";
import { api, apiMessage } from "@/lib/api";
import { writeParams } from "@/lib/sections";
import type { Mode } from "@/lib/types";

const MODES: Mode[] = ["rag", "hybrid", "graph_local", "graph_global", "auto"];
const DEFAULT_MODES: Mode[] = ["hybrid", "graph_local"];
const MAX_MODES = 3;
const QUERY_TIMEOUT_MS = 120_000;

// Real questions from eval/questions.jsonl; m2_001 is the multi-hop case graph_local wins.
const EXAMPLES = [
  { id: "m2_001", label: "Multi-hop", text: "At which company does the holder of a stake in PT Nusantara Mulia currently serve as Direktur Keuangan?" },
  { id: "sh_001", label: "Single hop", text: "Who is the current Direktur Utama of APSL?" },
  { id: "th_001", label: "Thematic", text: "Which companies belong to Pelita Gemilang Group and how are they connected?" },
];

function parseModes(raw: string | null): Mode[] {
  const picked = MODES.filter((mode) => raw?.split(",").includes(mode)).slice(0, MAX_MODES);
  return picked.length ? picked : DEFAULT_MODES;
}

export function AskView() {
  const params = useSearchParams();
  const [question, setQuestion] = useState(() => params.get("q") ?? "");
  const [modes, setModes] = useState<Mode[]>(() => parseModes(params.get("modes")));
  const [asked, setAsked] = useState<{ question: string; modes: Mode[] } | null>(null);
  const [runs, setRuns] = useState<Partial<Record<Mode, Run>>>({});
  const [evidence, setEvidence] = useState<{ chunkId: string; opener: HTMLElement } | null>(null);
  const [focused, setFocused] = useState(false);
  const controllers = useRef(new Map<Mode, AbortController>());

  const runMode = async (text: string, mode: Mode) => {
    controllers.current.get(mode)?.abort();
    const controller = new AbortController();
    controllers.current.set(mode, controller);
    setRuns((current) => ({ ...current, [mode]: { status: "loading", startedAt: Date.now() } }));
    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort(), QUERY_TIMEOUT_MS);
    const signal = AbortSignal.any ? AbortSignal.any([controller.signal, timeout.signal]) : controller.signal;
    // Fallback for browsers without AbortSignal.any: the timer aborts the request directly.
    if (signal === controller.signal) timeout.signal.addEventListener("abort", () => controller.abort());
    try {
      const answer = await api.query({ question: text, mode, verify: true }, signal);
      // A re-ask or cancel superseded this run; drop the late response.
      if (controller.signal.aborted && !timeout.signal.aborted) return;
      setRuns((current) => ({ ...current, [mode]: { status: "done", answer } }));
    } catch (error) {
      if (timeout.signal.aborted) {
        setRuns((current) => ({ ...current, [mode]: { status: "error", message: `Timed out after ${QUERY_TIMEOUT_MS / 1000} s` } }));
      } else if (!controller.signal.aborted) {
        setRuns((current) => ({ ...current, [mode]: { status: "error", message: apiMessage(error) } }));
      }
    } finally {
      clearTimeout(timer);
    }
  };

  const ask = (text: string, selected: Mode[]) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    controllers.current.forEach((controller) => controller.abort());
    controllers.current.clear();
    setRuns({});
    setAsked({ question: trimmed, modes: selected });
    writeParams({ q: trimmed, modes: selected.join(",") });
    // Each mode settles independently so one failure never blanks the others.
    selected.forEach((mode) => void runMode(trimmed, mode));
  };

  const cancel = (mode: Mode) => {
    controllers.current.get(mode)?.abort();
    setRuns((current) => ({ ...current, [mode]: { status: "cancelled" } }));
  };

  // A shared link (?q=&modes=) runs once on arrival.
  const initial = useRef({ question, modes });
  useEffect(() => {
    const pending = controllers.current;
    if (initial.current.question) ask(initial.current.question, initial.current.modes);
    return () => pending.forEach((controller) => controller.abort());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleMode = (mode: Mode) =>
    setModes((current) => {
      if (current.includes(mode)) return current.length > 1 ? current.filter((item) => item !== mode) : current;
      return current.length < MAX_MODES ? MODES.filter((item) => item === mode || current.includes(item)) : current;
    });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(question, modes);
  };

  const cols = asked?.modes.length === 3 ? "lg:grid-cols-3" : asked?.modes.length === 2 ? "md:grid-cols-2" : "";

  return (
    <>
      <div className="mx-auto max-w-content px-6">
        <div data-surface="dark" className="relative flex flex-col gap-5 overflow-hidden rounded-card bg-ink-night p-5 text-paper md:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_90%_at_90%_-20%,var(--accent)_0%,transparent_65%)]" />
          <form onSubmit={submit} className="relative flex h-14 items-center gap-2 rounded-pill bg-paper py-1.5 pr-1.5 pl-5 text-carbon shadow-soft">
            <label htmlFor="question" className="sr-only">Question</label>
            <div className="relative flex min-w-0 flex-1 items-center">
              <input
                id="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                autoComplete="off"
                className="peer w-full min-w-0 bg-transparent text-body-lg outline-none placeholder:text-transparent"
                placeholder="Ask about companies, owners and boards"
              />
              {!question ? (
                <span aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center gap-2 truncate text-body-lg text-graphite/75">
                  {!focused ? <span className="h-5 w-px shrink-0 bg-carbon animate-cursor-blink" /> : null}
                  <span className="truncate">Ask about companies, owners and boards</span>
                </span>
              ) : null}
            </div>
            <button
              type="submit"
              disabled={!question.trim()}
              className="inline-flex h-11 shrink-0 items-center gap-2 rounded-pill bg-carbon px-[22px] text-body font-medium text-paper transition-[transform,opacity] duration-150 ease-std hover:opacity-90 active:scale-[.97] disabled:opacity-40 focus-visible:outline-carbon"
            >
              Ask
              <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </button>
          </form>

          <div className="relative flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div role="group" aria-labelledby="modes-label" className="flex flex-wrap items-center gap-1.5">
              <span id="modes-label" className="mr-2 text-ui text-paper/60">Compare up to {MAX_MODES}</span>
              {MODES.map((mode) => {
                const pressed = modes.includes(mode);
                const blocked = !pressed && modes.length >= MAX_MODES;
                return (
                  <button
                    key={mode}
                    type="button"
                    aria-pressed={pressed}
                    disabled={blocked}
                    onClick={() => toggleMode(mode)}
                    className={`h-8 rounded-pill px-3.5 font-mono text-mono transition-[background-color,color,transform] duration-150 ease-std active:scale-[.97] disabled:opacity-40 ${pressed ? "bg-paper text-carbon" : "border border-paper/25 text-paper/80 hover:border-paper/50 hover:text-paper"}`}
                  >
                    {mode}
                  </button>
                );
              })}
            </div>
            <div className="flex min-w-0 flex-col gap-2 md:max-w-[46%]">
              <span className="text-ui text-paper/60">Try a question from the eval set</span>
              <ul className="flex flex-col gap-1">
                {EXAMPLES.map((example) => (
                  <li key={example.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setQuestion(example.text);
                        ask(example.text, modes);
                      }}
                      className="group flex w-full items-baseline gap-3 rounded-control px-2 py-1 -mx-2 text-left text-ui text-paper/80 transition-colors duration-150 ease-std hover:bg-paper/8 hover:text-paper"
                    >
                      <span className="w-[72px] shrink-0 font-mono text-caption text-paper/60">{example.label}</span>
                      <span className="truncate">{example.text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      <section aria-label="Answers" className="mx-auto max-w-content px-6 pt-10">
        {asked ? (
          <>
            <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <p className="max-w-2xl text-subheading text-balance">{asked.question}</p>
              <Legend />
            </div>
            <div className={`grid grid-cols-1 items-start gap-3 ${cols}`}>
              {asked.modes.map((mode, index) => {
                const run = runs[mode];
                return run ? (
                  <AnswerCard
                    key={mode}
                    mode={mode}
                    index={index}
                    run={run}
                    onCite={(chunkId, opener) => setEvidence({ chunkId, opener })}
                    onCancel={() => cancel(mode)}
                    onRetry={() => void runMode(asked.question, mode)}
                  />
                ) : null;
              })}
            </div>
          </>
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {(["rag", "hybrid", "graph_local"] as const).map((mode) => (
              <div key={mode} className="rounded-card border border-dashed border-line p-6">
                <p className="mb-1 font-mono text-mono text-muted-fg">{mode}</p>
                <p className="text-body text-fg-2">{MODE_LABELS[mode]} answers appear here with verified citations.</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {evidence ? <EvidenceDrawer chunkId={evidence.chunkId} opener={evidence.opener} onClose={() => setEvidence(null)} /> : null}
    </>
  );
}

function Legend() {
  const items = [
    { label: "supported", className: "bg-verdict-ok" },
    { label: "unsupported", className: "bg-verdict-bad" },
    { label: "unverified", className: "border border-dashed border-ash" },
  ];
  return (
    <ul aria-label="Citation colours" className="flex shrink-0 items-center gap-4 text-ui text-muted-fg">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={`size-2.5 rounded-full ${item.className}`} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
