import type { EntityType } from "@/lib/types";

// Three validated colour slots; Sector and Location are context nodes drawn hollow in neutral ink.
export const TYPE_STYLES: Record<EntityType, { label: string; fill: string | null }> = {
  Company: { label: "Company", fill: "var(--node-company)" },
  Person: { label: "Person", fill: "var(--node-person)" },
  Group: { label: "Group", fill: "var(--node-group)" },
  Sector: { label: "Sector", fill: null },
  Location: { label: "Location", fill: null },
};

export const typeLabel = (type: EntityType | null) => (type ? TYPE_STYLES[type].label : "Entity");

type GlyphProps = { type: EntityType | null; size: number; className?: string };

// Shape is a second channel beside colour, so type never rests on hue alone.
export function NodeShape({ type, size, className }: GlyphProps) {
  const fill = type ? TYPE_STYLES[type].fill : null;
  const hollow = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, className: `text-ash ${className ?? ""}` };
  const solid = { fill: fill ?? "none", className };
  switch (type) {
    case "Company":
      return <rect x={-size} y={-size} width={size * 2} height={size * 2} rx={size * 0.4} {...solid} />;
    case "Group":
      return <rect x={-size * 0.9} y={-size * 0.9} width={size * 1.8} height={size * 1.8} rx={size * 0.25} transform="rotate(45)" {...solid} />;
    case "Person":
      return <circle r={size} {...solid} />;
    case "Sector":
      return <rect x={-size * 0.85} y={-size * 0.85} width={size * 1.7} height={size * 1.7} rx={size * 0.2} transform="rotate(45)" {...hollow} />;
    case "Location":
      return <circle r={size} {...hollow} />;
    default:
      return <circle r={size} strokeDasharray="2 2" {...hollow} />;
  }
}

export function TypeSwatch({ type }: { type: EntityType | null }) {
  return (
    <svg viewBox="-7 -7 14 14" className="size-3 shrink-0 overflow-visible" aria-hidden="true">
      <NodeShape type={type} size={5} />
    </svg>
  );
}

export function Legend({ types, className = "" }: { types: (EntityType | null)[]; className?: string }) {
  return (
    <ul aria-label="Node types" className={`flex flex-wrap items-center gap-x-4 gap-y-1.5 text-caption ${className}`}>
      {types.map((type) => (
        <li key={type ?? "unknown"} className="flex items-center gap-1.5">
          <TypeSwatch type={type} />
          {typeLabel(type)}
        </li>
      ))}
    </ul>
  );
}
