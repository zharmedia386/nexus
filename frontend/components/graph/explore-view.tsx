"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { EvidenceDrawer } from "@/components/ask/evidence-drawer";
import { PathStrip } from "@/components/ask/path-strip";
import { EdgePanel } from "@/components/graph/edge-panel";
import { EntitySearch } from "@/components/graph/entity-search";
import { GraphCanvas } from "@/components/graph/graph-canvas";
import { buildGraph, type GraphNode } from "@/components/graph/layout";
import { NeighbourList } from "@/components/graph/neighbour-list";
import { Card } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { ApiError, api, apiMessage } from "@/lib/api";
import { writeParams } from "@/lib/routes";
import type { EntityDetail, EntityType, GraphPath } from "@/lib/types";

type Picked = { id: string; name: string };

type EntityLoad = { id: string } & ({ status: "ready"; detail: EntityDetail } | { status: "error"; message: string });

type PathLoad = { key: string; names: Record<string, string> } & (
  | { status: "found"; path: GraphPath; types: Record<string, EntityType | null> }
  | { status: "none" }
  | { status: "error"; message: string }
);

type View = "graph" | "list";

const VIEWS: { id: View; label: string }[] = [
  { id: "graph", label: "Graph" },
  { id: "list", label: "List" },
];

const fromParam = (id: string | null): Picked | null => (id ? { id, name: "" } : null);

const failure = (error: unknown) =>
  error instanceof ApiError && error.status === 404 ? "That entity is not in the graph." : apiMessage(error);

function CanvasMessage({ children }: { children: ReactNode }) {
  return (
    <div data-surface="dark" className="relative mx-3 grid h-[460px] place-items-center overflow-hidden rounded-card border border-line bg-ink-night px-6 text-paper sm:h-[620px]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_55%_at_50%_45%,#17445f59_0%,transparent_70%)]" />
      <div className="glass relative max-w-sm animate-overlay-in p-5 text-center text-body text-paper/85">{children}</div>
    </div>
  );
}

const NARROW = "(max-width: 639px)";

function subscribeNarrow(onChange: () => void) {
  const query = window.matchMedia?.(NARROW);
  query?.addEventListener("change", onChange);
  return () => query?.removeEventListener("change", onChange);
}

export function ExploreView() {
  const params = useSearchParams();
  const [trail, setTrail] = useState<Picked[]>(() => {
    const start = fromParam(params.get("e"));
    return start ? [start] : [];
  });
  const [from, setFrom] = useState(() => fromParam(params.get("from")));
  const [to, setTo] = useState(() => fromParam(params.get("to")));
  const [entity, setEntity] = useState<EntityLoad | null>(null);
  const [pathLoad, setPathLoad] = useState<PathLoad | null>(null);
  const [selected, setSelected] = useState<{ centre: string; key: string; opener: SVGElement } | null>(null);
  const [evidence, setEvidence] = useState<{ chunkId: string; opener: HTMLElement } | null>(null);
  // Phones default to the list; the server snapshot is the graph, so hydration never mismatches.
  const narrow = useSyncExternalStore(subscribeNarrow, () => window.matchMedia?.(NARROW).matches ?? false, () => false);
  const [chosenView, setChosenView] = useState<View | null>(null);
  const view = chosenView ?? (narrow ? "list" : "graph");

  // With no entity in the URL, open the best-connected one without writing it to the URL.
  const [starter, setStarter] = useState<Picked | null>(null);
  const centre = trail.at(-1) ?? starter;
  const centreId = centre?.id ?? null;
  const trailId = trail.at(-1)?.id ?? null;
  const fromId = from?.id ?? null;
  const toId = to?.id ?? null;
  const pathKey = fromId && toId && fromId !== toId ? `${fromId}>${toId}` : null;

  useEffect(() => {
    if (!centreId) return;
    const controller = new AbortController();
    const load = async () => {
      try {
        const detail = await api.entity(centreId, controller.signal);
        setEntity({ id: centreId, status: "ready", detail });
      } catch (error) {
        if (!controller.signal.aborted) setEntity({ id: centreId, status: "error", message: failure(error) });
      }
    };
    void load();
    return () => controller.abort();
  }, [centreId]);

  useEffect(() => {
    if (!pathKey || !fromId || !toId) return;
    const controller = new AbortController();
    const load = async () => {
      try {
        const path = await api.path(fromId, toId, controller.signal);
        // Hops carry names but not types; endpoints also name boxes restored from the URL.
        const settled = await Promise.allSettled((path?.node_ids ?? [fromId, toId]).map((id) => api.entity(id, controller.signal)));
        if (controller.signal.aborted) return;
        const nodes = settled.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []));
        // A failed lookup must not hide a found path; hop names stand in for it.
        const names: Record<string, string> = Object.fromEntries(
          (path?.hops ?? []).flatMap((hop) => [[hop.src_id, hop.src_name], [hop.dst_id, hop.dst_name]]),
        );
        for (const node of nodes) names[node.id] = node.name;
        if (!path) {
          setPathLoad({ key: pathKey, names, status: "none" });
          return;
        }
        setPathLoad({ key: pathKey, names, status: "found", path, types: Object.fromEntries(nodes.map((node) => [node.id, node.type])) });
        // Re-centre on the start when the current neighbourhood cannot show the path.
        setTrail((current) => {
          const last = current.at(-1);
          return last && path.node_ids.includes(last.id) ? current : [...current, { id: fromId, name: names[fromId] ?? "" }];
        });
      } catch (error) {
        if (!controller.signal.aborted) setPathLoad({ key: pathKey, names: {}, status: "error", message: failure(error) });
      }
    };
    void load();
    return () => controller.abort();
  }, [pathKey, fromId, toId]);

  const linked = useRef(trail.length > 0 || from !== null || to !== null);
  useEffect(() => {
    if (linked.current) return;
    const controller = new AbortController();
    const load = async () => {
      try {
        const top = (await api.graphStats(controller.signal)).top[0];
        if (top) setStarter({ id: top.id, name: top.name });
      } catch {
        // Stats unavailable: the canvas keeps its search hint.
      }
    };
    void load();
    return () => controller.abort();
  }, []);

  // ?e can change after mount (Themes member chips); adopt it unless it is already the centre.
  const urlEntity = params.get("e");
  const [seenUrlEntity, setSeenUrlEntity] = useState(urlEntity);
  if (urlEntity !== seenUrlEntity) {
    setSeenUrlEntity(urlEntity);
    if (urlEntity && urlEntity !== trailId) setTrail([{ id: urlEntity, name: "" }]);
  }

  useEffect(() => {
    writeParams({ e: trailId, from: fromId, to: toId });
  }, [trailId, fromId, toId]);

  const currentPath = pathLoad && pathLoad.key === pathKey ? pathLoad : null;
  const found = currentPath?.status === "found" ? currentPath : null;
  const pathLoading = pathKey !== null && currentPath === null;
  const detail = entity?.status === "ready" ? entity.detail : null;
  const entityLoading = centreId !== null && entity?.id !== centreId;

  const graph = useMemo(() => (detail ? buildGraph(detail, found?.path ?? null, found?.types) : null), [detail, found]);
  const selectedLink = selected && graph && selected.centre === graph.centre.id ? graph.links.find((link) => link.key === selected.key) ?? null : null;

  const nameOf = (picked: Picked | null) => picked?.name || (picked && currentPath?.names[picked.id]) || "";
  const crumbs = trail.length || !starter ? trail : [starter];
  const crumbName = (item: Picked) => item.name || (detail?.id === item.id ? detail.name : "…");

  const centreName = centre?.name || (detail && detail.id === centreId ? detail.name : "");

  const recentre = (node: GraphNode | Picked) => {
    if (node.id === centreId) return;
    setTrail((current) => [...(current.length || !starter ? current : [starter]), { id: node.id, name: node.name }]);
  };

  const closePanel = () => {
    // A re-centre remounts the edges; fall back to the canvas when the opener is gone.
    (selected?.opener.isConnected ? selected.opener : document.getElementById("graph-canvas"))?.focus();
    setSelected(null);
  };

  const onCite = (chunkId: string, opener: HTMLElement) => setEvidence({ chunkId, opener });

  return (
    <>
      <div className="mx-auto grid max-w-content gap-4 px-6 md:grid-cols-[2fr_3fr]">
        <Card className="flex flex-col gap-3 p-5">
          <p className="font-mono text-caption text-muted-fg">Neighbourhood</p>
          <EntitySearch key={`centre-${centreId}-${centreName}`} id="entity-search" defaultValue={centreName} label="Entity" placeholder="Company, person or group" onPick={recentre} />
        </Card>
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-caption text-muted-fg">Path finder · up to 4 hops</p>
            {from || to ? (
              <button
                type="button"
                onClick={() => {
                  setFrom(null);
                  setTo(null);
                }}
                className="rounded-pill px-2 text-caption text-muted-fg transition-colors duration-150 ease-std hover:text-fg"
              >
                Clear
              </button>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <EntitySearch key={`from-${fromId}-${nameOf(from)}`} id="path-from" label="From" placeholder="Start entity" defaultValue={nameOf(from)} onPick={(row) => setFrom({ id: row.id, name: row.name })} />
            <EntitySearch key={`to-${toId}-${nameOf(to)}`} id="path-to" label="To" placeholder="End entity" defaultValue={nameOf(to)} onPick={(row) => setTo({ id: row.id, name: row.name })} />
          </div>
        </Card>
      </div>

      <section aria-live="polite" className="mx-auto max-w-content px-6 empty:hidden">
        {fromId && fromId === toId ? <p className="mt-4 text-ui text-muted-fg">Pick two different entities to trace a path.</p> : null}
        {pathLoading ? (
          <div data-surface="dark" className="mt-4 flex h-[72px] items-center rounded-panel bg-ink-night px-4 text-paper">
            <span className="t-shimmer text-ui" data-text="Tracing the shortest path…">Tracing the shortest path…</span>
          </div>
        ) : null}
        {found ? (
          <div className="mt-4 animate-fade-up">
            <PathStrip path={found.path} onCite={onCite} />
          </div>
        ) : null}
        {currentPath?.status === "none" ? (
          <Card className="mt-4 flex animate-fade-up flex-col gap-1 p-5">
            <p className="text-body text-fg">No path within 4 hops between {nameOf(from)} and {nameOf(to)}.</p>
            <p className="text-ui text-muted-fg">The two entities are not connected through the stored relations, or the link is longer than four hops.</p>
          </Card>
        ) : null}
        {currentPath?.status === "error" ? <p role="alert" className="mt-4 text-ui text-verdict-bad">Path lookup failed: {currentPath.message}</p> : null}
      </section>

      <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-3 px-6 pt-10 pb-4">
        <nav aria-label="Exploration history" className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setTrail((current) => current.slice(0, -1))}
            disabled={trail.length < 2}
            aria-label="Back to previous entity"
            className="grid size-9 shrink-0 place-items-center rounded-pill bg-surface text-fg transition-[background-color,transform,opacity] duration-150 ease-std hover:bg-line active:scale-[.94] disabled:opacity-40"
          >
            <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M10 3.5 5.5 8l4.5 4.5" />
            </svg>
          </button>
          <ol className="flex min-w-0 items-center gap-1 overflow-hidden text-ui">
            {crumbs.length === 0 ? <li className="text-muted-fg">No entity open</li> : null}
            {crumbs.length > 4 ? <li aria-hidden="true" className="text-muted-fg">…</li> : null}
            {crumbs.map((item, index) =>
              index < crumbs.length - 4 ? null : (
                <li key={`${item.id}-${index}`} className="flex min-w-0 items-center gap-1">
                  {index > Math.max(0, crumbs.length - 4) ? <span aria-hidden="true" className="text-ash">/</span> : null}
                  {index === crumbs.length - 1 ? (
                    <span aria-current="page" className="truncate rounded-pill px-2 py-1 font-medium text-fg">{crumbName(item)}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setTrail((current) => current.slice(0, index + 1))}
                      className="truncate rounded-pill px-2 py-1 text-fg-2 transition-colors duration-150 ease-std hover:bg-surface hover:text-fg"
                    >
                      {crumbName(item)}
                    </button>
                  )}
                </li>
              ),
            )}
          </ol>
        </nav>
        <Tabs tabs={VIEWS} value={view} onChange={setChosenView} label="Graph view" />
      </div>

      <div>
        {!centre ? (
          <CanvasMessage>Search for a company, person or group to open its neighbourhood, or trace a path between two entities.</CanvasMessage>
        ) : entity?.id === centreId && entity.status === "error" ? (
          <CanvasMessage>
            <span role="alert">{entity.message}</span>
          </CanvasMessage>
        ) : !graph ? (
          <CanvasMessage>
            <span className="t-shimmer" data-text="Loading neighbourhood…">Loading neighbourhood…</span>
          </CanvasMessage>
        ) : view === "graph" ? (
          <GraphCanvas
            graph={graph}
            pathNodeIds={found?.path.node_ids.includes(graph.centre.id) ? found.path.node_ids : []}
            selectedKey={selectedLink?.key ?? null}
            onSelect={(key, opener) => setSelected({ centre: graph.centre.id, key, opener })}
            onRecentre={recentre}
            onShowList={() => setChosenView("list")}
          >
            {entityLoading ? (
              <p className="glass absolute top-3 right-3 px-3 py-1.5 text-ui">
                <span className="t-shimmer" data-text="Loading…">Loading…</span>
              </p>
            ) : null}
            {selectedLink ? <EdgePanel link={selectedLink} onClose={closePanel} onCite={onCite} /> : null}
          </GraphCanvas>
        ) : (
          <NeighbourList graph={graph} onRecentre={recentre} onCite={onCite} />
        )}
      </div>

      {evidence ? <EvidenceDrawer chunkId={evidence.chunkId} opener={evidence.opener} onClose={() => setEvidence(null)} /> : null}
    </>
  );
}
