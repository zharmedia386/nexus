import { REPORT } from "@/lib/showcase";

export const total = (counts: Partial<Record<string, number>>) => Object.values(counts).reduce<number>((sum, count) => sum + (count ?? 0), 0);
const { dataset, models } = REPORT;
export const DOCUMENTS = Object.values(dataset.docs).reduce((sum, byLang) => sum + total(byLang), 0);

const STAGES: { name: string; detail: string; stores: string[] }[] = [
  { name: "World", detail: `${total(dataset.entities)} planted entities, ${total(dataset.edges).toLocaleString("en-US")} relations`, stores: [`seed ${dataset.seed}`] },
  { name: "Documents", detail: `${DOCUMENTS} filings, news and notes in Indonesian and English`, stores: ["Postgres"] },
  { name: "Chunks", detail: `Split and embedded with ${models.EMBEDDING_MODEL}`, stores: ["Postgres"] },
  { name: "Indexes", detail: "Vectors and keywords on one side, extracted entities and Leiden communities on the other", stores: ["Milvus · dense + BM25", "Neo4j · graph"] },
  { name: "Modes", detail: "rag, hybrid, graph_local, graph_global, and an auto router", stores: ["LangGraph", "FastAPI"] },
  { name: "Verifier", detail: "Splits the answer into claims and checks each against the chunk it cites", stores: [String(models.LLM_MODEL)] },
  { name: "Eval", detail: `${REPORT.answerable + REPORT.unanswerable} questions, paired bootstrap CIs per mode`, stores: [`run ${REPORT.run_id.slice(0, 8)}`] },
];

// One stage per step from synthetic world to scored answer; a dashed rail joins them like a graph path.
export function PipelineDiagram() {
  return (
    <ol aria-label="Pipeline" className="grid gap-0 lg:grid-cols-7">
      {STAGES.map((stage, index) => (
        <li
          key={stage.name}
          className="relative flex flex-col gap-2 border-l border-dashed border-ash pb-8 pl-6 before:absolute before:top-1 before:-left-[5px] before:size-[9px] before:rounded-full before:border before:border-ash before:bg-bg last:pb-0 lg:border-t lg:border-l-0 lg:pt-6 lg:pr-4 lg:pb-0 lg:pl-0 lg:before:-top-[5px] lg:before:left-0"
        >
          <span className="font-mono text-caption text-muted-fg">{String(index + 1).padStart(2, "0")}</span>
          <span className="text-body-lg">{stage.name}</span>
          <span className="text-ui text-fg-2">{stage.detail}</span>
          <span className="mt-auto flex flex-col gap-1 pt-1">
            {stage.stores.map((store) => (
              <span key={store} className="font-mono text-caption text-fg">{store}</span>
            ))}
          </span>
        </li>
      ))}
    </ol>
  );
}
