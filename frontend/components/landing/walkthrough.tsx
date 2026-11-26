"use client";

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { AnswerText, type OnCite } from "@/components/ask/answer-text";
import { PathStrip } from "@/components/ask/path-strip";
import { seconds } from "@/components/eval/derive";
import { NodeShape, typeLabel } from "@/components/graph/node-glyph";
import { useGsap } from "@/lib/motion";
import { WALKTHROUGH } from "@/lib/showcase";
import type { Answer, EntityType } from "@/lib/types";

const { question, graph, baseline } = WALKTHROUGH;
const path = graph.graph_paths[0];
const ENTITY_PREFIX: Record<string, EntityType> = { company: "Company", person: "Person", group: "Group", sector: "Sector", location: "Location" };
const typeOf = (id: string) => ENTITY_PREFIX[id.split("_")[0]] ?? null;
const relLabel = (relType: string) => relType.toLowerCase().replaceAll("_", " ");
const baselineFound = path.chunk_ids.filter((chunkId) => baseline.hits.some((hit) => hit.chunk_id === chunkId)).length;
const supported = graph.claims.filter((claim) => claim.supported).length;

// The hop quote is the sentence the edge was extracted from; fall back to the chunk's first sentence.
function citedSentence(answer: Answer, chunkId: string): string {
  const text = answer.hits.find((hit) => hit.chunk_id === chunkId)?.text ?? "";
  const quotes = answer.graph_paths.flatMap((item) => item.hops).filter((hop) => hop.chunk_ids.includes(chunkId)).flatMap((hop) => hop.quotes);
  return quotes.find((quote) => text.includes(quote)) ?? text.split(/(?<=[.!?])\s+/)[0] ?? "";
}

function Step({ index, title, children }: { index: number; title: string; children: ReactNode }) {
  return (
    <li data-walkthrough-step className="grid gap-5 border-t border-line pt-6 md:grid-cols-[180px_1fr] md:gap-10 md:pt-8">
      <div className="flex items-baseline gap-3 md:flex-col md:gap-2">
        <span className="font-mono text-mono text-muted-fg">0{index}</span>
        <h3 className="text-heading-sm font-normal">{title}</h3>
      </div>
      <div className="min-w-0">{children}</div>
    </li>
  );
}

function GraphWalk() {
  return (
    <div data-surface="dark" className="rounded-card bg-ink-night p-5 text-paper md:p-6">
      <p className="mb-5 flex items-baseline justify-between gap-3">
        <span className="font-mono text-mono">graph_local</span>
        <span className="text-caption text-paper/60">{path.hops.length} hops, one quote each</span>
      </p>
      <ol aria-label="Graph path" className="flex flex-col">
        {path.node_names.map((name, index) => {
          const hop = path.hops[index];
          const type = typeOf(path.node_ids[index]);
          return (
            <Fragment key={path.node_ids[index]}>
              <li data-node className="flex items-center gap-3">
                <svg viewBox="-8 -8 16 16" className="size-5 shrink-0 overflow-visible" aria-hidden="true">
                  <NodeShape type={type} size={5.5} />
                </svg>
                <span className="text-body-lg">{name}</span>
                <span className="text-caption text-paper/50">{typeLabel(type)}</span>
              </li>
              {hop ? (
                <li data-hop className="grid grid-cols-[20px_1fr] gap-3">
                  <svg viewBox="0 0 20 100" preserveAspectRatio="none" className="h-full w-5" aria-hidden="true">
                    <line data-edge x1="10" y1="0" x2="10" y2="100" pathLength={1} strokeDasharray="1" stroke="#ffffff73" strokeWidth="1.25" />
                  </svg>
                  <div data-hop-text className="flex flex-col gap-1.5 py-4">
                    <span className="font-mono text-caption text-paper/60">{relLabel(hop.rel_type)}</span>
                    <q className="text-ui text-paper/85">{hop.quotes[0]}</q>
                    <span className="font-mono text-caption text-paper/50">{hop.chunk_ids[0]}</span>
                  </div>
                </li>
              ) : null}
            </Fragment>
          );
        })}
      </ol>
    </div>
  );
}

function Baseline() {
  const onPath = new Set(path.chunk_ids);
  return (
    <div data-baseline className="flex flex-col gap-4 rounded-card bg-surface p-5 md:p-6">
      <p className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-mono">hybrid</span>
        <span className="text-caption text-muted-fg">abstained · {seconds(baseline.latency_ms)}</span>
      </p>
      <p className="text-body-lg">{baseline.text}</p>
      <p className="text-ui text-fg-2">
        Its {baseline.hits.length} reranked chunks held {baselineFound} of the {path.chunk_ids.length} passages the path quotes, and the answer model abstained.
      </p>
      <ul aria-label="Chunks hybrid retrieved" className="mt-auto flex flex-wrap gap-1.5">
        {baseline.hits.map((hit) => (
          <li key={hit.chunk_id} className={`rounded-pill border px-2 py-0.5 font-mono text-caption ${onPath.has(hit.chunk_id) ? "border-fg text-fg" : "border-line text-muted-fg"}`}>
            {hit.chunk_id}
            {onPath.has(hit.chunk_id) ? <span className="sr-only"> (on the graph path)</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

type Cited = { chunkId: string; opener: HTMLElement };

function SourceQuote({ cited, onClose }: { cited: Cited; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  const hit = graph.hits.find((item) => item.chunk_id === cited.chunkId);

  useEffect(() => panel.current?.focus(), [cited]);

  const close = () => {
    onClose();
    cited.opener.focus();
  };

  return (
    <div
      ref={panel}
      role="dialog"
      aria-labelledby="walkthrough-source"
      tabIndex={-1}
      onKeyDown={(event) => event.key === "Escape" && close()}
      className="mt-5 flex animate-item-in flex-col gap-3 rounded-panel border border-line bg-bg p-4 outline-none"
    >
      <div className="flex items-center justify-between gap-3">
        <h4 id="walkthrough-source" className="font-mono text-mono">
          <span className="sr-only">Source </span>
          {cited.chunkId}
        </h4>
        <button type="button" onClick={close} className="rounded-pill px-2.5 py-1 text-ui text-fg-2 transition-colors duration-150 ease-std hover:bg-surface hover:text-fg">
          Close
        </button>
      </div>
      <blockquote className="border-l-2 border-fg pl-3 text-body text-fg">
        <mark className="bg-highlight text-fg">{citedSentence(graph, cited.chunkId)}</mark>
      </blockquote>
      {hit ? <p className="font-mono text-caption text-muted-fg">from {hit.doc_id}, saved with the answer</p> : null}
    </div>
  );
}

function AnswerCard() {
  const [cited, setCited] = useState<Cited | null>(null);
  const onCite: OnCite = (chunkId, opener) => setCited({ chunkId, opener });

  return (
    <article aria-labelledby="walkthrough-answer" className="rounded-card bg-surface p-5 md:p-6">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h4 id="walkthrough-answer" className="font-mono text-mono">graph_local answer</h4>
        <span className="font-mono text-caption text-muted-fg">
          {supported} of {graph.claims.length} claims supported · {seconds(graph.latency_ms)} · {graph.llm_calls} LLM calls
        </span>
      </header>
      <div data-answer>
        <AnswerText answer={graph} onCite={onCite} />
      </div>
      <div className="mt-5">
        <PathStrip path={path} onCite={onCite} />
      </div>
      {cited ? <SourceQuote cited={cited} onClose={() => setCited(null)} /> : null}
    </article>
  );
}

export function Walkthrough() {
  const scope = useRef<HTMLElement>(null);
  const replay = useRef<() => void>(() => {});
  const [canReplay, setCanReplay] = useState(false);

  useGsap(scope, ({ gsap, reduced }) => {
    // The server markup is already the end state.
    setCanReplay(!reduced);
    if (reduced || !scope.current) return;
    const steps = scope.current.querySelectorAll<HTMLElement>("[data-walkthrough-step]");
    const timelines: ReturnType<typeof gsap.timeline>[] = [];
    const timelineFor = (step: HTMLElement) => {
      const timeline = gsap.timeline({ scrollTrigger: { trigger: step, start: "top 78%", once: true } }).from(step, { autoAlpha: 0, y: 16, duration: 0.6, ease: "expo.out" });
      timelines.push(timeline);
      return timeline;
    };

    const typed = steps[0].querySelector<HTMLElement>("[data-typed]");
    // Empty before first paint of the step, so the full question never flashes before typing.
    if (typed) typed.textContent = "";
    // Replays the steps in reading order: each waits, hidden at its start, until the one before has finished.
    replay.current = () => {
      if (typed) typed.textContent = "";
      let offset = 0;
      for (const timeline of timelines) {
        timeline.pause(0).delay(offset).restart(true);
        offset += timeline.duration();
      }
    };
    const progress = { chars: 0 };
    timelineFor(steps[0]).to(progress, {
      chars: question.length,
      duration: 1.6,
      ease: "none",
      onUpdate: () => {
        if (typed) typed.textContent = question.slice(0, Math.round(progress.chars));
      },
    }, 0.2);

    const walk = timelineFor(steps[1]);
    const nodes = steps[1].querySelectorAll("[data-node]");
    const hops = steps[1].querySelectorAll("[data-hop]");
    walk.from(steps[1].querySelector("[data-baseline]"), { autoAlpha: 0, duration: 0.5 }, 0.3);
    nodes.forEach((node, index) => {
      walk.fromTo(node, { opacity: 0.25 }, { opacity: 1, duration: 0.3 });
      const hop = hops[index];
      if (!hop) return;
      walk.fromTo(hop.querySelector("[data-edge]"), { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.5, ease: "power2.inOut" });
      walk.from(hop.querySelector("[data-hop-text]"), { autoAlpha: 0, x: -6, duration: 0.4, ease: "expo.out" }, "<0.2");
    });

    const answer = timelineFor(steps[2]);
    answer.fromTo(
      steps[2].querySelectorAll("[data-answer] > div > p, [data-answer] li"),
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0)", duration: 0.55, ease: "power2.out", stagger: 0.35, clearProps: "clipPath" },
      0.3,
    );
  });

  return (
    <section ref={scope} id="walkthrough" aria-labelledby="walkthrough-title" className="mx-auto max-w-content px-6 pt-24 md:pt-[104px]">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="walkthrough-title" className="text-heading font-normal md:text-heading-lg">One question, two retrievers</h2>
        {canReplay ? (
          <button
            type="button"
            aria-label="Replay the walkthrough"
            onClick={() => replay.current()}
            className="inline-flex h-9 items-center gap-2 rounded-pill border border-line px-4 text-ui text-fg transition-[background-color,transform] duration-150 ease-std hover:bg-surface active:scale-[.97]"
          >
            <svg viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v2.6h2.6" />
            </svg>
            Replay
          </button>
        ) : null}
      </div>
      <p className="mt-4 mb-10 max-w-[60ch] text-body-lg text-muted-fg">
        A multi-hop question, replayed from responses saved off the running system. Hybrid search gives up. The graph walk names the company and quotes every hop.
      </p>
      <ol className="flex flex-col gap-10 md:gap-14">
        <Step index={1} title="The question">
          <div className="rounded-card bg-surface p-5 md:p-6">
            <p className="mb-3 text-caption text-muted-fg">Same input to both modes</p>
            <p data-final={question} className="sizer grid text-body-lg md:text-subheading">
              <span data-typed>{question}</span>
            </p>
          </div>
        </Step>
        <Step index={2} title="Retrieval">
          <div className="grid gap-3 lg:grid-cols-[3fr_2fr]">
            <GraphWalk />
            <Baseline />
          </div>
        </Step>
        <Step index={3} title="Cited answer">
          <AnswerCard />
        </Step>
      </ol>
    </section>
  );
}
