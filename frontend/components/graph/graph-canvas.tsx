"use client";

import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { API_EDGE_LIMIT, computeLayout, relLabel, type GraphNode, type NeighbourGraph } from "@/components/graph/layout";
import { EDGE_PANEL_ID } from "@/components/graph/edge-panel";
import { Legend, NodeShape, typeLabel } from "@/components/graph/node-glyph";
import type { EntityType } from "@/lib/types";

const LABEL_MAX = 24;
const clip = (text: string) => (text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX - 1)}…` : text);

const activate = (handler: () => void) => (event: KeyboardEvent) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  handler();
};

type GraphCanvasProps = {
  graph: NeighbourGraph;
  pathNodeIds: string[];
  selectedKey: string | null;
  onSelect: (key: string, opener: SVGElement) => void;
  onRecentre: (node: GraphNode) => void;
  onShowList: () => void;
  children?: ReactNode;
};

export function GraphCanvas({ graph, pathNodeIds, selectedKey, onSelect, onRecentre, onShowList, children }: GraphCanvasProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 1000, height: 600 });

  useLayoutEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const width = Math.round(frame.clientWidth);
      // Same width keeps the same object, so the memoised layout is not recomputed.
      if (width) setSize((current) => (current.width === width ? current : { width, height: width < 640 ? 460 : 620 }));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);

  const positions = useMemo(
    () => computeLayout(graph.nodes.map((node) => node.id), graph.links, graph.centre.id, size.width, size.height),
    [graph, size],
  );
  // Slide the graph left so the open side panel (360px + inset) never covers a node.
  const xs = Object.values(positions).map((point) => point.x);
  const panelEdge = size.width - 384;
  const shift = selectedKey && size.width >= 640 ? Math.max(0, Math.min(Math.max(...xs) + 80 - panelEdge, Math.min(...xs) - 60)) : 0;
  const pathOrder = new Map(pathNodeIds.map((id, index) => [id, index]));
  const types = [...new Set<EntityType | null>(graph.nodes.map((node) => node.type))].sort((a, b) => (a ?? "~").localeCompare(b ?? "~"));
  // The API stops at 40 edges, so a capped count is a lower bound.
  const more = graph.hidden > 0 ? `+${graph.hidden}${graph.capped ? "+" : ""} more` : `${API_EDGE_LIMIT}+ relations`;

  return (
    <div
      ref={frameRef}
      id="graph-canvas"
      tabIndex={-1}
      data-surface="dark"
      style={{ height: size.height }}
      className="relative mx-3 animate-hero-settle overflow-hidden rounded-card border border-line bg-ink-night text-paper outline-none"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(70%_60%_at_50%_45%,#17445f66_0%,transparent_70%)]" />
      <svg
        viewBox={`0 0 ${size.width} ${size.height}`}
        role="group"
        aria-label={`Neighbourhood of ${graph.centre.name}: ${graph.nodes.length - 1} connected entities shown. The list view has the same data as text.`}
        className="relative block size-full"
      >
        <g style={{ transform: `translateX(${-shift}px)` }} className="transition-transform duration-300 ease-out">
          <g key={graph.centre.id} style={{ animation: "scrimIn .4s var(--ease-out) both" }}>
            {graph.links.map((link) => {
              const from = positions[link.source];
              const to = positions[link.target];
              if (!from || !to) return null;
              const selected = link.key === selectedKey;
              const label = [...new Set(link.relations.map((relation) => relLabel(relation.type)))].join(" · ");
              const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
              const pill = label.length * 6.4 + 16;
              const names = `${link.relations[0].sourceName} ${label} ${link.relations[0].targetName}`;
              return (
                <g
                  key={link.key}
                  role="button"
                  tabIndex={0}
                  aria-label={`${names}. Show evidence`}
                  aria-expanded={selected}
                  aria-controls={selected ? EDGE_PANEL_ID : undefined}
                  onClick={(event) => onSelect(link.key, event.currentTarget)}
                  onKeyDown={(event) => activate(() => onSelect(link.key, event.currentTarget))(event)}
                  className="group cursor-pointer outline-none"
                >
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="transparent" strokeWidth="16" />
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    strokeWidth={selected ? 1.75 : 1}
                    className={`transition-[stroke] duration-150 ease-std ${selected ? "stroke-paper/85" : link.onPath ? "stroke-paper/15" : "stroke-paper/20 group-hover:stroke-paper/65 group-focus-visible:stroke-paper/80"}`}
                  />
                  {link.onPath ? (
                    <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#ffffff6b" strokeWidth="1.25" strokeLinecap="round" strokeDasharray="4 9" className="animate-flow-travel" />
                  ) : null}
                  <g
                    transform={`translate(${mid.x} ${mid.y})`}
                    className={`pointer-events-none transition-opacity duration-150 ease-std ${selected || link.onPath ? "opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"}`}
                  >
                    <rect x={-pill / 2} y={-10} width={pill} height={20} rx={10} className="fill-ink-night stroke-paper/25 group-focus-visible:stroke-paper" />
                    <text textAnchor="middle" dy="4" className="fill-paper/85 font-mono text-[11px]">{label}</text>
                  </g>
                </g>
              );
            })}
            {graph.nodes.map((node) => {
              const point = positions[node.id];
              if (!point) return null;
              const centre = node.id === graph.centre.id;
              const step = pathOrder.get(node.id);
              const radius = centre ? 11 : step === undefined ? 7 : 8;
              const name = (
                <text
                  y={radius + (centre ? 22 : 18)}
                  textAnchor="middle"
                  paintOrder="stroke"
                  stroke="#101417"
                  strokeWidth="4"
                  strokeLinejoin="round"
                  className={centre ? "fill-paper text-[14px] font-medium" : "fill-paper/75 text-[12px] transition-[fill] duration-150 ease-std group-hover:fill-paper group-focus-visible:fill-paper"}
                >
                  {clip(node.name)}
                </text>
              );
              const halo =
                step === undefined ? null : (
                  <circle
                    r={radius * 2.6}
                    fill="#ffffff14"
                    className="animate-flow-pulse"
                    style={{ animationDelay: `${step * 600}ms`, transformBox: "fill-box", transformOrigin: "center" }}
                  />
                );
              if (centre) {
                return (
                  <g key={node.id} transform={`translate(${point.x} ${point.y})`} aria-label={`${node.name}, ${typeLabel(node.type)}, centre`} role="img">
                    {halo}
                    <circle r={radius + 7} fill="none" stroke="#ffffff38" />
                    <NodeShape type={node.type} size={radius} />
                    {name}
                  </g>
                );
              }
              return (
                <g
                  key={node.id}
                  transform={`translate(${point.x} ${point.y})`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${node.name}, ${typeLabel(node.type)}. Open its neighbourhood`}
                  onClick={() => onRecentre(node)}
                  onKeyDown={activate(() => onRecentre(node))}
                  className="group cursor-pointer outline-none"
                >
                  {halo}
                  <circle r={radius + 10} fill="transparent" />
                  <circle r={radius + 5} fill="none" strokeWidth="1.5" className="stroke-paper opacity-0 transition-opacity duration-150 ease-std group-focus-visible:opacity-100" />
                  <g className="transition-transform duration-150 ease-std group-hover:scale-[1.15]">
                    <NodeShape type={node.type} size={radius} />
                  </g>
                  {name}
                </g>
              );
            })}
          </g>
        </g>
      </svg>
      <Legend types={types} className="glass pointer-events-none absolute bottom-3 left-3 px-3 py-2 text-paper/85" />
      {graph.hidden > 0 || graph.capped ? (
        <button
          type="button"
          onClick={onShowList}
          className="glass absolute top-3 left-3 px-3 py-1.5 text-ui text-paper transition-[transform,background-color] duration-150 ease-std hover:bg-paper/10 active:scale-[.97]"
        >
          {more} · open list
        </button>
      ) : null}
      {children}
    </div>
  );
}
