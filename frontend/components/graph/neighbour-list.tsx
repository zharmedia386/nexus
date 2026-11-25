import type { OnCite } from "@/components/ask/answer-text";
import { API_EDGE_LIMIT, relLabel, type GraphNode, type NeighbourGraph } from "@/components/graph/layout";
import { TypeSwatch, typeLabel } from "@/components/graph/node-glyph";

type NeighbourListProps = { graph: NeighbourGraph; onRecentre: (node: GraphNode) => void; onCite: OnCite };

export function NeighbourList({ graph, onRecentre, onCite }: NeighbourListProps) {
  return (
    <section aria-labelledby="neighbour-list-title" className="mx-auto max-w-content px-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="neighbour-list-title" className="text-heading-sm font-normal">
          {graph.centre.name} <span className="text-muted-fg">· {graph.neighbours} connected {graph.neighbours === 1 ? "entity" : "entities"}</span>
        </h2>
        {graph.capped ? <p className="text-caption text-muted-fg">The API returns the first {API_EDGE_LIMIT} relations; more may exist.</p> : null}
      </div>
      {graph.all.length === 0 ? <p className="text-body text-fg-2">No relations stored for this entity.</p> : null}
      <ul className="divide-y divide-line overflow-hidden rounded-card bg-surface">
        {graph.all.map(({ node, link }) => (
          <li key={node.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:gap-6 sm:p-5">
            <div className="sm:w-56 sm:shrink-0">
              <button
                type="button"
                onClick={() => onRecentre(node)}
                aria-label={`${node.name}, ${typeLabel(node.type)}. Open its neighbourhood`}
                className="flex items-center gap-2 rounded-control text-left text-body text-fg underline-offset-4 hover:underline"
              >
                <TypeSwatch type={node.type} />
                {node.name}
              </button>
              <p className="mt-0.5 pl-5 text-caption text-muted-fg">{typeLabel(node.type)}</p>
            </div>
            <ul className="flex min-w-0 flex-1 flex-col gap-3">
              {link.relations.map((relation, index) => (
                <li key={index} className="flex flex-col gap-1.5">
                  <p className="text-ui text-fg-2">
                    {relation.sourceName} <span className="font-mono text-fg">—{relLabel(relation.type)}→</span> {relation.targetName}
                    {relation.role ? <span className="text-muted-fg"> · {relation.role}</span> : null}
                    {relation.pct !== null ? <span className="text-muted-fg"> · {relation.pct}%</span> : null}
                    {relation.since !== null || relation.until !== null ? (
                      <span className="font-mono text-muted-fg"> · {relation.since ?? "?"}–{relation.until ?? "present"}</span>
                    ) : null}
                  </p>
                  {relation.quotes.map((quote, quoteIndex) => (
                    <p key={quoteIndex} className="flex flex-wrap items-start gap-x-3 gap-y-1 text-ui text-fg-2">
                      <q className="min-w-0 flex-1 border-l border-line pl-3">{quote}</q>
                      {relation.chunkIds[quoteIndex] ? (
                        <button
                          type="button"
                          onClick={(event) => onCite(relation.chunkIds[quoteIndex], event.currentTarget)}
                          className="shrink-0 rounded-pill border border-line px-2 py-0.5 font-mono text-caption text-fg-2 transition-[background-color,color] duration-150 ease-std hover:bg-bg hover:text-fg"
                        >
                          {relation.chunkIds[quoteIndex]}
                        </button>
                      ) : null}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
