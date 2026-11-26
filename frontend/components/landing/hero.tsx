"use client";

import Link from "next/link";
import { useRef, type ReactNode } from "react";
import { DOCUMENTS } from "@/components/content/pipeline-diagram";
import { fixed, summaryRow } from "@/components/eval/derive";
import { NetworkHero } from "@/components/network-hero";
import { buttonClass } from "@/components/ui/button";
import { useGsap } from "@/lib/motion";
import { GRAPH_STATS, REPORT } from "@/lib/showcase";

const FORMATS = {
  decimal: (value: number) => fixed(value),
  integer: (value: number) => Math.round(value).toLocaleString("en-US"),
};
type Format = keyof typeof FORMATS;

const graphLocal = summaryRow(REPORT, "graph_local", "all")?.answer_match ?? 0;
const hybrid = summaryRow(REPORT, "hybrid", "all")?.answer_match ?? 0;

function Figure({ value, format }: { value: number; format: Format }) {
  const text = FORMATS[format](value);
  return (
    <span data-final={text} className="sizer inline-grid justify-items-end tabular-nums">
      <span data-count={value} data-format={format}>{text}</span>
    </span>
  );
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col-reverse gap-1 border-t border-paper/15 pt-4">
      <dt className="text-ui text-paper/65">{label}</dt>
      <dd className="flex items-baseline gap-2 text-heading font-normal md:text-heading-lg">{children}</dd>
    </div>
  );
}

const Muted = ({ children }: { children: string }) => <span className="text-body-lg text-paper/50">{children}</span>;

export function Hero() {
  const scope = useRef<HTMLElement>(null);

  useGsap(scope, ({ gsap, reduced }) => {
    if (reduced) return;
    scope.current?.querySelectorAll<HTMLElement>("[data-count]").forEach((element, index) => {
      const format = FORMATS[element.dataset.format as Format];
      const state = { value: 0 };
      // Start value set synchronously; the frame stays sized by the sizer, so nothing shifts.
      element.textContent = format(0);
      gsap.to(state, {
        value: Number(element.dataset.count),
        duration: 1.4,
        delay: 0.4 + index * 0.08,
        ease: "expo.out",
        onUpdate: () => {
          element.textContent = format(state.value);
        },
      });
    });
  });

  return (
    <section ref={scope} data-surface="dark" aria-labelledby="hero-title" className="relative mx-3 mt-3 overflow-hidden rounded-card bg-ink-night text-paper">
      <div className="mx-auto max-w-content px-6 pt-32 md:pt-36">
        <div className="animate-content-reveal">
          <p className="mb-5 font-mono text-mono text-paper/60">GraphRAG · local-first</p>
          <h1 id="hero-title" className="text-display-sm font-normal text-balance md:text-display">Answers that show their path.</h1>
        </div>
        <div className="grid gap-8 pt-8 md:grid-cols-[5fr_7fr] md:items-start">
          <div className="flex animate-content-reveal flex-col gap-8">
            <p className="max-w-md text-body-lg text-paper/75">
              Local GraphRAG over {DOCUMENTS} fictional Indonesian business documents. Every answer cites its sources and quotes each graph hop.
            </p>
            <div className="flex flex-wrap gap-3">
              <a href="#film" className={buttonClass("light")}>Watch the film</a>
              <Link
                href="/ask"
                className="inline-flex h-11 items-center rounded-pill px-[22px] text-body font-medium text-paper ring-1 ring-paper/25 ring-inset transition-[background-color,transform] duration-150 ease-std hover:bg-paper/10 active:scale-[.97]"
              >
                Open app
              </Link>
            </div>
          </div>
          <NetworkHero className="-mx-6 md:mx-0" />
        </div>
        <dl className="grid animate-content-reveal gap-6 pt-6 pb-10 sm:grid-cols-3 sm:gap-8">
          <Stat label="answer match, graph local vs hybrid">
            <Figure value={graphLocal} format="decimal" />
            <Muted>vs</Muted>
            <span className="text-paper/60"><Figure value={hybrid} format="decimal" /></span>
          </Stat>
          <Stat label="entities and relations, extracted graph">
            <Figure value={GRAPH_STATS.nodes} format="integer" />
            <Muted>/</Muted>
            <Figure value={GRAPH_STATS.relationships} format="integer" />
          </Stat>
          <Stat label={`eval questions, ${REPORT.answerable} answerable`}>
            <Figure value={REPORT.answerable + REPORT.unanswerable} format="integer" />
          </Stat>
        </dl>
      </div>
    </section>
  );
}
