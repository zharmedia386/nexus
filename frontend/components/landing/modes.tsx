import Link from "next/link";
import { fixed, seconds, summaryRow } from "@/components/eval/derive";
import { REPORT } from "@/lib/showcase";
import type { EvalCategory, Mode } from "@/lib/types";

const { models } = REPORT;
const score = (mode: Mode, category: EvalCategory) => fixed(summaryRow(REPORT, mode, category)?.answer_match ?? 0);
const p50ms = (mode: Mode) => summaryRow(REPORT, mode, "all")?.p50_ms ?? Infinity;
const p50 = (mode: Mode) => seconds(p50ms(mode));
const ragFastest = (["hybrid", "graph_local"] as const).every((mode) => p50ms("rag") < p50ms(mode));

const ROWS: { mode: Mode; name: string; sees: string; wins: string }[] = [
  {
    mode: "rag",
    name: "Vector RAG",
    sees: `Chunks whose ${models.EMBEDDING_MODEL} embedding sits closest to the question, cut at ${models.SIMILARITY_THRESHOLD} similarity, top ${models.RERANKER_TOP_N}.`,
    wins: `${ragFastest ? "Fastest of the three, p50" : "p50"} ${p50("rag")}. On thematic questions it scores ${score("rag", "thematic")} against hybrid's ${score("hybrid", "thematic")}.`,
  },
  {
    mode: "hybrid",
    name: "Hybrid",
    sees: `Dense and BM25 keyword hits from Milvus, fused, then reranked by ${models.RERANKER_MODEL} down to ${models.RERANKER_TOP_N} chunks.`,
    wins: `Thematic questions (${score("hybrid", "thematic")}), where the answer is spread across many documents.`,
  },
  {
    mode: "graph_local",
    name: "Graph local",
    sees: "Entities named in the question, linked into Neo4j and walked edge by edge. Each followed edge brings the chunk it was extracted from.",
    wins: `Multi-hop: ${score("graph_local", "multi_hop_2")} on 2-hop and ${score("graph_local", "multi_hop_3")} on 3-hop, where hybrid scores ${score("hybrid", "multi_hop_2")} and ${score("hybrid", "multi_hop_3")}.`,
  },
];

export function Modes() {
  return (
    <section aria-labelledby="modes-title" className="mx-auto max-w-content px-6 pt-24 md:pt-[104px]">
      <h2 id="modes-title" className="text-heading font-normal md:text-heading-lg">Three ways to retrieve</h2>
      <p className="mt-4 mb-10 max-w-[60ch] text-body-lg text-muted-fg">
        Same corpus, same answer model ({models.LLM_MODEL}), different evidence. The score is answer match on all {REPORT.answerable} answerable questions.
      </p>
      <div role="table" aria-label="Retrieval modes" className="flex flex-col">
        <div role="row" className="sr-only gap-8 pb-3 text-ui font-medium text-fg-2 md:not-sr-only md:grid md:grid-cols-[160px_1fr_1fr_120px]">
          <span role="columnheader">Mode</span>
          <span role="columnheader">What it sees</span>
          <span role="columnheader">Where it wins</span>
          <span role="columnheader" className="text-right">Answer match</span>
        </div>
        {ROWS.map((row) => {
          const value = summaryRow(REPORT, row.mode, "all")?.answer_match ?? 0;
          const lead = row.mode === "graph_local";
          return (
            <div key={row.mode} role="row" className="grid gap-x-8 gap-y-3 border-t border-line py-6 md:grid-cols-[160px_1fr_1fr_120px]">
              <span role="rowheader" className="flex flex-col gap-1">
                <span className="text-heading-sm">{row.name}</span>
                <span className="font-mono text-caption text-muted-fg">{row.mode}</span>
              </span>
              <span role="cell" className="text-body text-fg-2">{row.sees}</span>
              <span role="cell" className="text-body text-fg">{row.wins}</span>
              <span role="cell" className="flex flex-col gap-2 md:items-end">
                <span className={`font-mono text-heading-sm tabular-nums ${lead ? "" : "text-fg-2"}`}>{fixed(value)}</span>
                <span aria-hidden="true" className="block h-1 w-full max-w-[120px] overflow-hidden rounded-pill bg-line">
                  <span className={`block h-full origin-left rounded-pill ${lead ? "bg-fg" : "bg-ash"}`} style={{ transform: `scaleX(${value})` }} />
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <Link href="/how-it-works" className="mt-6 inline-flex items-center gap-1.5 text-body text-fg underline decoration-line underline-offset-4 transition-colors duration-150 ease-std hover:decoration-fg">
        How each mode works
      </Link>
    </section>
  );
}
