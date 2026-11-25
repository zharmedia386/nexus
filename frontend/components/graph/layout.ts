import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import type { EntityDetail, EntityType, GraphPath } from "@/lib/types";

// Neighbours drawn on the canvas; the rest stay in the list view behind "+N more".
export const CANVAS_CAP = 24;
// Backend NEIGHBOUR_LIMIT: a response this long may have been truncated.
export const API_EDGE_LIMIT = 40;

export type Relation = {
  type: string;
  sourceName: string;
  targetName: string;
  role: string | null;
  relation: string | null;
  pct: number | null;
  since: number | null;
  until: number | null;
  quotes: string[];
  chunkIds: string[];
};

export type GraphNode = { id: string; name: string; type: EntityType | null };

export type GraphLink = {
  key: string;
  source: string;
  target: string;
  relations: Relation[];
  onPath: boolean;
};

export type NeighbourGraph = {
  centre: GraphNode;
  nodes: GraphNode[];
  links: GraphLink[];
  // Every neighbour link, uncapped, for the list view.
  all: { node: GraphNode; link: GraphLink }[];
  neighbours: number;
  hidden: number;
  capped: boolean;
};

export type Point = { x: number; y: number };

export const relLabel = (type: string) => type.toLowerCase().replaceAll("_", " ");

export const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);

export function buildGraph(
  detail: EntityDetail,
  path: GraphPath | null,
  types: Record<string, EntityType | null> = {},
): NeighbourGraph {
  const centre: GraphNode = { id: detail.id, name: detail.name, type: detail.type };
  // A path that skips the centre cannot be drawn from this neighbourhood, so it is left out.
  const walk = path?.node_ids.includes(detail.id) ? path : null;
  const onPath = new Set(walk?.node_ids ?? []);
  const byNeighbour = new Map<string, GraphLink>();
  const names = new Map<string, string>();

  const kinds = new Map<string, EntityType | null>();

  for (const edge of detail.edges) {
    names.set(edge.other_id, edge.other_name);
    kinds.set(edge.other_id, edge.other_type);
    const link = byNeighbour.get(edge.other_id) ?? {
      key: pairKey(detail.id, edge.other_id),
      source: detail.id,
      target: edge.other_id,
      relations: [],
      onPath: false,
    };
    link.relations.push({
      type: edge.type,
      sourceName: edge.outgoing ? detail.name : edge.other_name,
      targetName: edge.outgoing ? edge.other_name : detail.name,
      role: edge.role,
      relation: edge.relation,
      pct: edge.pct,
      since: edge.since,
      until: edge.until,
      quotes: edge.quotes,
      chunkIds: edge.chunk_ids,
    });
    byNeighbour.set(edge.other_id, link);
  }

  // Path neighbours always make the cut so the highlighted walk is never hidden.
  const ordered = [...byNeighbour.keys()].sort((a, b) => Number(onPath.has(b)) - Number(onPath.has(a)));
  const visible = ordered.slice(0, CANVAS_CAP);
  const nodes = new Map<string, GraphNode>([[centre.id, centre]]);
  const links = new Map<string, GraphLink>();
  for (const id of visible) {
    nodes.set(id, { id, name: names.get(id) ?? id, type: kinds.get(id) ?? types[id] ?? null });
    const link = byNeighbour.get(id)!;
    links.set(link.key, link);
  }

  for (const hop of walk?.hops ?? []) {
    for (const [id, name] of [[hop.src_id, hop.src_name], [hop.dst_id, hop.dst_name]]) {
      if (!nodes.has(id)) nodes.set(id, { id, name, type: types[id] ?? null });
    }
    const key = pairKey(hop.src_id, hop.dst_id);
    const relation: Relation = {
      type: hop.rel_type,
      sourceName: hop.forward ? hop.src_name : hop.dst_name,
      targetName: hop.forward ? hop.dst_name : hop.src_name,
      role: null,
      relation: null,
      pct: null,
      since: null,
      until: null,
      quotes: hop.quotes,
      chunkIds: hop.chunk_ids,
    };
    const existing = links.get(key);
    // Drawn along the walk so the travelling dashes move from source to destination.
    const walked = { source: hop.src_id, target: hop.dst_id, onPath: true };
    if (existing) {
      const known = existing.relations.some((item) => item.type === relation.type);
      links.set(key, { ...existing, ...walked, relations: known ? existing.relations : [...existing.relations, relation] });
    } else {
      links.set(key, { key, ...walked, relations: [relation] });
    }
  }

  return {
    centre,
    nodes: [...nodes.values()],
    links: [...links.values()],
    all: [...byNeighbour.entries()].map(([id, link]) => ({
      node: { id, name: names.get(id) ?? id, type: kinds.get(id) ?? null },
      link,
    })),
    neighbours: byNeighbour.size,
    hidden: byNeighbour.size - visible.length,
    capped: detail.edges.length >= API_EDGE_LIMIT,
  };
}

// Park–Miller LCG: d3's jiggle and init draw from it, so a fixed seed gives a fixed layout.
function seeded(seed: number) {
  let state = seed;
  return () => {
    state = (state * 48271) % 2147483647;
    return state / 2147483647;
  };
}

type SimNode = SimulationNodeDatum & { id: string };

export function computeLayout(
  nodeIds: string[],
  links: { source: string; target: string }[],
  centreId: string,
  width: number,
  height: number,
  seed = 7,
): Record<string, Point> {
  // Sorted input: the result depends on the graph, never on response order.
  const nodes: SimNode[] = [...nodeIds].sort().map((id) => (id === centreId ? { id, fx: 0, fy: 0 } : { id }));
  const simLinks: SimulationLinkDatum<SimNode>[] = links
    .map(({ source, target }) => ({ source, target }))
    .sort((a, b) => `${a.source}|${a.target}`.localeCompare(`${b.source}|${b.target}`));
  const aspect = width / height;

  const simulation = forceSimulation(nodes)
    .randomSource(seeded(seed))
    .force("link", forceLink<SimNode, SimulationLinkDatum<SimNode>>(simLinks).id((node) => node.id).distance(120).strength(0.6))
    .force("charge", forceManyBody().strength(-520))
    .force("collide", forceCollide(44))
    // Weaker x pull on wide canvases spreads the layout to the viewport's shape.
    .force("x", forceX(0).strength(0.05 / aspect))
    .force("y", forceY(0).strength(0.05 * aspect))
    .stop();
  simulation.tick(320);

  const padX = Math.min(110, width * 0.16);
  // Extra bottom room keeps nodes clear of the legend overlay.
  const [padTop, padBottom] = [52, 76];
  const xs = nodes.map((node) => node.x ?? 0);
  const ys = nodes.map((node) => node.y ?? 0);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = Math.min((width - 2 * padX) / Math.max(maxX - minX, 1), (height - padTop - padBottom) / Math.max(maxY - minY, 1), 2.4);
  const offsetX = width / 2 - ((minX + maxX) / 2) * scale;
  const offsetY = padTop + (height - padTop - padBottom) / 2 - ((minY + maxY) / 2) * scale;

  const round = (value: number) => Math.round(value * 10) / 10;
  return Object.fromEntries(
    nodes.map((node) => [node.id, { x: round((node.x ?? 0) * scale + offsetX), y: round((node.y ?? 0) * scale + offsetY) }]),
  );
}
