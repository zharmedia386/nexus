import type { CSSProperties } from "react";

const NODES: [number, number, number][] = [
  [60, 250, 3], [150, 120, 4], [230, 290, 3], [310, 180, 6], [400, 70, 3], [430, 300, 4],
  [520, 200, 5], [600, 90, 3], [640, 310, 3], [720, 170, 6], [800, 60, 3], [850, 280, 4],
  [930, 160, 5], [980, 300, 3], [360, 330, 2.5], [560, 30, 2.5], [100, 40, 2.5], [700, 250, 2.5],
];
const EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 3], [1, 16], [16, 4], [3, 4], [3, 5], [2, 14], [14, 5], [5, 6],
  [4, 7], [7, 15], [15, 10], [6, 7], [6, 8], [8, 17], [17, 9], [7, 9], [9, 10], [9, 11],
  [11, 13], [12, 13], [10, 12], [11, 12],
];
// Four nodes, three hops: the same shape as the walkthrough answer further down the page.
const PATH = [3, 6, 9, 12];

const line = (from: number, to: number) => ({
  x1: NODES[from][0], y1: NODES[from][1], x2: NODES[to][0], y2: NODES[to][1],
});

// Decorative: an abstract multi-hop walk; real graph data lives in /explore.
export function NetworkHero({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`relative h-[240px] animate-hero-settle md:h-[320px] ${className}`}>
      <svg viewBox="0 0 1000 360" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 size-full">
        <g stroke="#ffffff1f" strokeWidth="1">
          {EDGES.map(([from, to]) => <line key={`${from}-${to}`} {...line(from, to)} />)}
        </g>
        <g stroke="#ffffff6b" strokeWidth="1.25" strokeLinecap="round" strokeDasharray="4 9" fill="none">
          {PATH.slice(1).map((to, index) => (
            <line key={to} {...line(PATH[index], to)} className="animate-flow-travel" />
          ))}
        </g>
        {NODES.map(([cx, cy, r], index) =>
          PATH.includes(index) ? null : <circle key={index} cx={cx} cy={cy} r={r} fill="#ffffff47" />,
        )}
        {PATH.map((index, step) => {
          const [cx, cy, r] = NODES[index];
          const pulse: CSSProperties = { animationDelay: `${step * 600}ms`, transformBox: "fill-box", transformOrigin: "center" };
          return (
            <g key={index}>
              <circle cx={cx} cy={cy} r={r * 2.6} fill="#ffffff14" className="animate-flow-pulse" style={pulse} />
              <circle cx={cx} cy={cy} r={r} fill="#ffffff" />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
