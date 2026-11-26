"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { CITATION_PATTERN, CitationChip, type OnCite } from "@/components/ask/answer-text";
import { EvidenceDrawer } from "@/components/ask/evidence-drawer";
import { Card } from "@/components/ui/card";
import { api, apiMessage } from "@/lib/api";
import type { Community } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; roots: Community[]; children: Map<string, Community[]> };


// Summaries past this length are clamped behind a toggle.
const LONG_SUMMARY_CHARS = 320;

function Summary({ text, onCite }: { text: string; onCite: OnCite }) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > LONG_SUMMARY_CHARS;
  const clamped = long && !expanded;
  const order = new Map<string, number>();
  const parts = text.split(CITATION_PATTERN);
  return (
    <div className="flex flex-col items-start gap-1">
      {/* inert keeps chips under the clamp out of the tab order */}
      <p inert={clamped} className={`text-body text-fg-2 ${clamped ? "line-clamp-4" : ""}`}>
        {parts.map((part, position) => {
          if (position % 2 === 0) return part;
          if (!order.has(part)) order.set(part, order.size + 1);
          return <CitationChip key={position} chunkId={part} index={order.get(part) ?? 0} verdict="neutral" onCite={onCite} />;
        })}
      </p>
      {long ? (
        <button type="button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)} className="-ml-2 rounded-pill px-2 py-1 text-ui text-fg-2 transition-colors duration-150 ease-std hover:bg-line hover:text-fg">
          {expanded ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}

function MemberChips({ community }: { community: Community }) {
  const router = useRouter();
  const hidden = community.size - community.member_names.length;
  return (
    <ul aria-label={`Members of ${community.title ?? community.id}`} className="flex flex-wrap gap-1.5">
      {community.member_names.map((name, position) => {
        const id = community.member_ids[position];
        return (
          <li key={id}>
            <button
              type="button"
              onClick={() => {
                router.push(`/explore?e=${encodeURIComponent(id)}`);
              }}
              className="inline-flex h-7 items-center rounded-pill border border-line px-3 text-ui transition-colors duration-150 ease-std hover:bg-line"
            >
              {name}
            </button>
          </li>
        );
      })}
      {hidden > 0 ? <li className="inline-flex h-7 items-center px-1 text-ui text-fg-2">+{hidden} more</li> : null}
    </ul>
  );
}

const countLabel = (community: Community) => `${community.size} ${community.size === 1 ? "entity" : "entities"}`;

function ChildCard({ community, onCite }: { community: Community; onCite: OnCite }) {
  return (
    <li id={`community-${community.id}`} className="scroll-mt-[88px] rounded-card border border-line p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h4 className="text-ui font-medium">{community.title ?? community.id}</h4>
        <span className="font-mono text-caption text-fg-2">{countLabel(community)}</span>
      </div>
      {community.summary ? <div className="mb-3"><Summary text={community.summary} onCite={onCite} /></div> : null}
      <MemberChips community={community} />
    </li>
  );
}

type CardProps = { community: Community; kids: Community[]; open: boolean; onToggle: () => void; onCite: OnCite };

function CommunityCard({ community, kids, open, onToggle, onCite }: CardProps) {
  const panelId = `community-panel-${community.id}`;
  return (
    <Card id={`community-${community.id}`} className={`scroll-mt-[88px] flex flex-col gap-4 p-5 md:p-6 ${open ? "md:col-span-2" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-subheading">{community.title ?? community.id}</h3>
        <span className="shrink-0 pt-1 font-mono text-caption text-fg-2">{countLabel(community)}</span>
      </div>
      {community.summary ? <Summary text={community.summary} onCite={onCite} /> : null}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className="-ml-3 self-start rounded-pill px-3 py-1.5 text-ui text-fg-2 transition-colors duration-150 ease-std hover:bg-line hover:text-fg"
      >
        {open ? "Hide detail" : kids.length ? `${kids.length} sub-themes and members` : "Members"}
      </button>
      <div id={panelId} hidden={!open} className="flex flex-col gap-4">
        {open ? (
          <>
            {kids.length ? (
              <ul className="grid gap-3">
                {kids.map((kid) => <ChildCard key={kid.id} community={kid} onCite={onCite} />)}
              </ul>
            ) : null}
            <MemberChips community={community} />
          </>
        ) : null}
      </div>
    </Card>
  );
}

function Skeleton() {
  return (
    <div aria-busy="true" aria-label="Loading themes" className="grid gap-4 md:grid-cols-2">
      {[0, 1, 2, 3].map((slot) => (
        <div key={slot} className="h-[220px] animate-pulse rounded-card bg-surface motion-reduce:animate-none" />
      ))}
    </div>
  );
}

export function ThemesSection() {
  const params = useSearchParams();
  const target = params.get("c");
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [evidence, setEvidence] = useState<{ chunkId: string; opener: HTMLElement } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      try {
        const [top, sub] = await Promise.all([api.communities(0, controller.signal), api.communities(1, controller.signal)]);
        const children = new Map<string, Community[]>();
        for (const community of sub) {
          if (community.parent_id) children.set(community.parent_id, [...(children.get(community.parent_id) ?? []), community]);
        }
        const roots = [...top].sort((a, b) => b.size - a.size);
        setLoad({ status: "ready", roots, children });
      } catch (error) {
        if (!controller.signal.aborted) setLoad({ status: "error", message: apiMessage(error) });
      }
    };
    void run();
    return () => controller.abort();
  }, [attempt]);

  // ?c may name a level-1 community; its parent card is the one to open.
  const targetRoot = useMemo(() => {
    if (!target || load.status !== "ready") return null;
    const root = load.roots.find((community) => community.id === target);
    if (root) return root.id;
    return load.roots.find((community) => load.children.get(community.id)?.some((kid) => kid.id === target))?.id ?? null;
  }, [target, load]);

  useEffect(() => {
    if (!target || !targetRoot) return;
    // Wait a frame so the opened panel is in the layout before centring.
    const frame = requestAnimationFrame(() => {
      document.getElementById(`community-${target}`)?.scrollIntoView({ block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  }, [target, targetRoot]);

  // A new ?c re-opens its card even if the reader collapsed it earlier.
  const [seenTarget, setSeenTarget] = useState(target);
  if (target !== seenTarget) {
    setSeenTarget(target);
    if (target) setToggled((current) => Object.fromEntries(Object.entries(current).filter(([id]) => id !== target)));
  }

  // The ?c target opens until the reader toggles it themselves.
  const isOpen = (id: string) => toggled[id] ?? id === targetRoot;

  return (
    <div className="mx-auto max-w-content px-6">
      {load.status === "loading" ? <Skeleton /> : null}
      {load.status === "error" ? (
        <Card role="alert" className="flex flex-wrap items-center justify-between gap-4 p-6">
          <p className="text-body text-fg-2">{load.message}</p>
          <button type="button" onClick={() => { setLoad({ status: "loading" }); setAttempt((value) => value + 1); }} className="rounded-pill border border-line px-4 py-1.5 text-ui hover:bg-line">
            Retry
          </button>
        </Card>
      ) : null}
      {load.status === "ready" && load.roots.length === 0 ? (
        <Card className="p-8"><p className="text-subheading text-fg-2">No communities yet. They appear after the graph is built and summarised.</p></Card>
      ) : null}
      {load.status === "ready" && load.roots.length ? (
        <ul className="grid items-start gap-4 md:grid-cols-2">
          {load.roots.map((community) => (
            <li key={community.id} className="contents">
              <CommunityCard
                community={community}
                kids={load.children.get(community.id) ?? []}
                open={isOpen(community.id)}
                onToggle={() => setToggled((current) => ({ ...current, [community.id]: !isOpen(community.id) }))}
                onCite={(chunkId, opener) => setEvidence({ chunkId, opener })}
              />
            </li>
          ))}
        </ul>
      ) : null}
      {evidence ? <EvidenceDrawer chunkId={evidence.chunkId} opener={evidence.opener} onClose={() => setEvidence(null)} /> : null}
    </div>
  );
}
