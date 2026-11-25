import type { ReactNode } from "react";
import type { Answer } from "@/lib/types";

export type Verdict = "supported" | "unsupported" | "unverified" | "neutral";

export const VERDICT_STYLES: Record<Verdict, string> = {
  supported: "bg-verdict-ok-bg text-verdict-ok border-transparent",
  unsupported: "bg-verdict-bad-bg text-verdict-bad border-transparent",
  unverified: "bg-transparent text-fg-2 border-dashed border-ash",
  neutral: "bg-transparent text-fg-2 border-solid border-ash",
};

// Mirrors backend CITATION_PATTERN: any [chunk-id-like] token is a citation.
export const CITATION_PATTERN = /\[([A-Za-z0-9_.:-]{1,64})\]/g;
const INLINE = /(\[[A-Za-z0-9_.:-]{1,64}\]|\*\*[^*]+\*\*)/;
const LIST_MARKER = /^\s*(?:[-*+]|\d+[.)])\s+/;
const ORDERED_MARKER = /^\s*\d+[.)]\s+/;
const HEADING = /^\s*#+\s+/;
const CITATIONS_ONLY = /^(\s*\[[A-Za-z0-9_.:-]{1,64}\])+\s*$/;

const normalize = (text: string) =>
  text.replace(CITATION_PATTERN, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");

// Containment only counts when the shorter text is substantial, so "Yes." never borrows a long claim.
const MIN_OVERLAP_CHARS = 25;
const MIN_OVERLAP_RATIO = 0.6;

function overlaps(a: string, b: string) {
  const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
  return (
    shorter.length >= MIN_OVERLAP_CHARS &&
    shorter.length / longer.length >= MIN_OVERLAP_RATIO &&
    longer.includes(shorter)
  );
}

// Chip verdict = verdict of the claim split from the sentence that cites the chunk.
export function verdictFor(chunkId: string, sentence: string, answer: Answer): Verdict {
  if (!answer.hits.some((hit) => hit.chunk_id === chunkId)) return "unverified";
  const key = normalize(sentence);
  if (!key) return "unverified";
  const cited = answer.claims.filter((candidate) => candidate.chunk_ids.includes(chunkId));
  const claim =
    cited.find((candidate) => normalize(candidate.text) === key) ??
    cited.find((candidate) => overlaps(normalize(candidate.text), key));
  if (!claim || claim.supported === null) return "unverified";
  return claim.supported ? "supported" : "unsupported";
}

type Block =
  | { kind: "p" | "h"; line: string }
  | { kind: "ul" | "ol"; items: string[] }
  | { kind: "cites"; ids: string[] };

function toBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const last = blocks.at(-1);
    if (!line) continue;
    if (CITATIONS_ONLY.test(line)) {
      const ids = [...line.matchAll(CITATION_PATTERN)].map((match) => match[1]);
      if (last?.kind === "cites") last.ids.push(...ids);
      else blocks.push({ kind: "cites", ids });
    } else if (HEADING.test(line)) {
      blocks.push({ kind: "h", line: line.replace(HEADING, "") });
    } else if (LIST_MARKER.test(line)) {
      const kind = ORDERED_MARKER.test(line) ? "ol" : "ul";
      const item = line.replace(LIST_MARKER, "");
      if (last?.kind === kind) last.items.push(item);
      else blocks.push({ kind, items: [item] });
    } else {
      blocks.push({ kind: "p", line });
    }
  }
  return blocks;
}

export type OnCite = (chunkId: string, opener: HTMLElement) => void;

type CiteProps = {
  chunkId: string;
  index: number;
  verdict: Verdict;
  onCite: OnCite;
};

const VERDICT_ICON: Partial<Record<Verdict, string>> = {
  supported: "M2.5 6.2 4.8 8.5 9.5 3.5",
  unsupported: "M3.5 3.5l5 5m0-5-5 5",
};

export function CitationChip({ chunkId, index, verdict, onCite }: CiteProps) {
  const icon = VERDICT_ICON[verdict];
  return (
    <button
      type="button"
      data-verdict={verdict}
      title={`${chunkId} · ${verdict}`}
      aria-label={`Evidence ${index}, ${chunkId}, ${verdict}`}
      onClick={(event) => onCite(chunkId, event.currentTarget)}
      className={`inline-flex h-5 translate-y-[-1px] items-center gap-0.5 rounded-pill border px-1.5 align-middle font-mono text-caption tabular-nums transition-[transform,filter] duration-150 ease-std hover:brightness-95 active:scale-[.94] ${VERDICT_STYLES[verdict]}`}
    >
      {icon ? (
        <svg viewBox="0 0 12 12" className="size-2.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d={icon} />
        </svg>
      ) : null}
      {index}
    </button>
  );
}

type AnswerTextProps = { answer: Answer; onCite: OnCite };

export function AnswerText({ answer, onCite }: AnswerTextProps) {
  const order = new Map<string, number>();
  const indexOf = (chunkId: string) => {
    if (!order.has(chunkId)) order.set(chunkId, order.size + 1);
    return order.get(chunkId) ?? 0;
  };

  const inline = (sentence: string, verdictSource: string, key: string): ReactNode[] =>
  {
    const nodes: ReactNode[] = [];
    // Chips stay glued to the word before and the punctuation after, so a line never starts with a chip.
    let glue: ReactNode[] | null = null;
    sentence.split(INLINE).forEach((token, position) => {
      const cite = /^\[([A-Za-z0-9_.:-]{1,64})\]$/.exec(token);
      if (cite) {
        if (!glue) {
          const group: ReactNode[] = [];
          const last = nodes.pop();
          const word = typeof last === "string" ? /\S+\s*$/.exec(last) : null;
          if (typeof last === "string") {
            nodes.push(word ? last.slice(0, word.index) : last);
            if (word) group.push(word[0]);
          } else if (last !== undefined) {
            group.push(last);
          }
          nodes.push(<span key={`${key}-g${position}`} className="whitespace-nowrap">{group}</span>);
          glue = group;
        }
        const chunkId = cite[1];
        glue.push(
          <CitationChip
            key={`${key}-${position}`}
            chunkId={chunkId}
            index={indexOf(chunkId)}
            verdict={verdictFor(chunkId, verdictSource, answer)}
            onCite={onCite}
          />,
        );
        return;
      }
      if (!token) return;
      if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
        glue = null;
        nodes.push(<strong key={`${key}-${position}`} className="font-medium">{token.slice(2, -2)}</strong>);
        return;
      }
      const text = token.replaceAll("**", "");
      if (glue && !text.trim()) {
        glue.push(text);
        return;
      }
      if (glue) {
        const punctuation = /^[^\s]*/.exec(text)?.[0] ?? "";
        glue.push(punctuation);
        glue = null;
        nodes.push(text.slice(punctuation.length));
        return;
      }
      nodes.push(text);
    });
    return nodes;
  };

  // Citation-only sentences cite the sentence before them on the same line (backend rule).
  const line = (text: string, key: string) => {
    let previous = "";
    return text.split(/(?<=[.!?])\s+/).flatMap((sentence, index) => {
      const source = normalize(sentence) ? sentence : previous;
      previous = source;
      return [index > 0 ? " " : null, ...inline(sentence, source, `${key}-${index}`)];
    });
  };

  return (
    <div className="flex flex-col gap-3 text-body-lg text-fg">
      {toBlocks(answer.text).map((block, index) => {
        const key = `b${index}`;
        const style = { animationDelay: `${index * 40}ms` };
        const motion = "animate-item-in";
        switch (block.kind) {
          case "h":
            return <p key={key} style={style} className={`${motion} font-medium`}>{line(block.line, key)}</p>;
          case "ul":
          case "ol": {
            const List = block.kind;
            return (
              <List key={key} style={style} className={`${motion} flex flex-col gap-1.5 pl-5 ${block.kind === "ol" ? "list-decimal" : "list-disc"} marker:text-ash`}>
                {block.items.map((item, itemIndex) => <li key={itemIndex} className="pl-1">{line(item, `${key}-${itemIndex}`)}</li>)}
              </List>
            );
          }
          case "cites":
            return (
              <p key={key} style={style} className={`${motion} flex flex-wrap items-center gap-1 text-ui text-fg-2`}>
                <span className="mr-1">Sources</span>
                {block.ids.map((chunkId, chipIndex) => (
                  <CitationChip
                    key={`${key}-${chipIndex}`}
                    chunkId={chunkId}
                    index={indexOf(chunkId)}
                    verdict="unverified"
                    onCite={onCite}
                  />
                ))}
              </p>
            );
          default:
            return <p key={key} style={style} className={motion}>{line(block.line, key)}</p>;
        }
      })}
    </div>
  );
}
