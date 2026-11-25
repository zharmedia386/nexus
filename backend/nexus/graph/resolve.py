import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from itertools import combinations
from math import comb

from pydantic import BaseModel

from nexus.config import get_settings
from nexus.datagen.models import EntityType, RelType
from nexus.datagen.reference import TICKER
from nexus.db.repo import ChunkRow
from nexus.eval.metrics import normalize
from nexus.graph.schema import ExtractionResult
from nexus.llm import chat_json

MAX_FACTS = 8
ADJUDICATE_PROMPT_VERSION = "v1"
GROUP_TOKENS = frozenset({"grup", "group"})


@dataclass(frozen=True)
class Mention:
    chunk_id: str
    doc_id: str
    name: str
    type: EntityType


@dataclass
class ResolvedEntity:
    id: str
    type: EntityType
    name: str
    aliases: list[str]
    mentions: list[Mention]


@dataclass
class ResolvedRelation:
    type: RelType
    src_id: str
    dst_id: str
    role: str | None
    pct: float | None
    relation: str | None
    kind: str | None
    since: int | None
    until: int | None
    chunk_ids: list[str] = field(default_factory=list)
    doc_ids: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    quote_spans: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class ResolvedGraph:
    entities: list[ResolvedEntity]
    relations: list[ResolvedRelation]
    skipped_alias_unions: int = 0
    adjudication_bound: int = 0
    adjudications: int = 0


@dataclass(frozen=True)
class PersonContext:
    name: str
    facts: list[str]


class SamePerson(BaseModel):
    same: bool
    reason: str


Adjudicator = Callable[[PersonContext, PersonContext], bool]
Block = tuple[str, str]


def adjudicate_people(a: PersonContext, b: PersonContext) -> bool:
    def describe(person: PersonContext) -> str:
        facts = "\n".join(f"- {fact}" for fact in person.facts) or "- (no facts)"
        return f"Name: {person.name}\nFacts:\n{facts}"

    messages = [
        {
            "role": "system",
            "content": "You decide whether two person mentions from Indonesian corporate "
            "documents refer to the same real person. Answer same=true only if their facts "
            "are consistent and share a concrete link (same company, family member or "
            "event); otherwise same=false.",
        },
        {"role": "user", "content": f"Person A\n{describe(a)}\n\nPerson B\n{describe(b)}"},
    ]
    return chat_json(messages, SamePerson, temperature=0.0, timeout=120).same


def pair_key(a: PersonContext, b: PersonContext) -> str:
    payloads = sorted(json.dumps(asdict(person), ensure_ascii=False) for person in (a, b))
    # Version and model in the key make cached verdicts stale when either changes.
    version = f"{ADJUDICATE_PROMPT_VERSION}|{get_settings().LLM_MODEL}"
    return hashlib.sha256("\n".join([version, *payloads]).encode()).hexdigest()


def entity_key(name: str, entity_type: EntityType) -> str:
    key = normalize(name)
    if entity_type == "Group":
        key = " ".join(token for token in key.split() if token not in GROUP_TOKENS)
    return key


def entity_id(entity_type: EntityType, canonical_key: str) -> str:
    digest = hashlib.sha1(f"{entity_type}|{canonical_key}".encode()).hexdigest()[:10]
    return f"{entity_type.lower()}_{digest}"


class UnionFind[T]:
    def __init__(self) -> None:
        self.parent: dict[T, T] = {}

    def find(self, item: T) -> T:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: T, b: T) -> None:
        root_a, root_b = self.find(a), self.find(b)
        # Smaller root wins so components are independent of union order.
        if root_a != root_b:
            low, high = sorted((root_a, root_b))
            self.parent[high] = low


def _build_entity(
    entity_type: EntityType, canonical_key: str, mentions: list[Mention], aliases: set[str]
) -> ResolvedEntity:
    counts = Counter(mention.name for mention in mentions)
    name = min(counts, key=lambda surface: (-counts[surface], -len(surface), surface))
    return ResolvedEntity(
        id=entity_id(entity_type, canonical_key),
        type=entity_type,
        name=name,
        aliases=sorted((aliases | counts.keys()) - {name}),
        mentions=sorted(mentions, key=lambda m: (m.doc_id, m.chunk_id, m.name)),
    )


def resolve(
    extractions: dict[str, ExtractionResult],
    chunks: list[ChunkRow],
    *,
    adjudicate: Adjudicator = adjudicate_people,
    max_adjudications: int = 500,
) -> ResolvedGraph:
    ordered = sorted(
        (chunk for chunk in chunks if chunk.id in extractions),
        key=lambda chunk: (chunk.doc_id, chunk.ordinal),
    )
    blocks = UnionFind[Block]()
    mentions_by_block: dict[Block, list[Mention]] = defaultdict(list)
    aliases_by_block: dict[Block, set[str]] = defaultdict(set)
    block_of: dict[tuple[str, str], Block] = {}
    alias_edges: list[tuple[Block, Block, str]] = []
    for chunk in ordered:
        for entity in extractions[chunk.id].entities:
            key = entity_key(entity.name, entity.type)
            if not key:
                continue
            block = (entity.type, key)
            blocks.find(block)
            mentions_by_block[block].append(
                Mention(chunk.id, chunk.doc_id, entity.name, entity.type)
            )
            block_of.setdefault((chunk.id, entity.name), block)
            for alias in entity.aliases:
                if alias_key := entity_key(alias, entity.type):
                    alias_edges.append((block, (entity.type, alias_key), alias))

    # A non-ticker alias naming another mentioned entity is more likely a confusion than a link.
    skipped_alias_unions = 0
    for block, alias_block, alias in alias_edges:
        if (
            block != alias_block
            and alias_block in mentions_by_block
            and not TICKER.fullmatch(alias)
        ):
            skipped_alias_unions += 1
            continue
        blocks.union(block, alias_block)
        aliases_by_block[block].add(alias)

    components: dict[Block, list[Block]] = defaultdict(list)
    for block in mentions_by_block:
        components[blocks.find(block)].append(block)

    # Non-person entities: one per component. Persons: one candidate per (component, doc).
    entity_of_block: dict[Block, str] = {}
    entities: list[ResolvedEntity] = []
    candidates: dict[Block, dict[str, list[Mention]]] = {}
    for root, members in components.items():
        mentions = [mention for block in members for mention in mentions_by_block[block]]
        aliases = set().union(*(aliases_by_block[block] for block in members))
        if root[0] != "Person":
            entity = _build_entity(root[0], root[1], mentions, aliases)
            entities.append(entity)
            entity_of_block.update(dict.fromkeys(members, entity.id))
            continue
        per_doc: dict[str, list[Mention]] = defaultdict(list)
        for mention in mentions:
            per_doc[mention.doc_id].append(mention)
        candidates[root] = per_doc

    # Person endpoints resolve to (component, doc) candidates until clusters are known.
    def endpoint(chunk: ChunkRow, name: str) -> str | tuple[Block, str] | None:
        block = block_of.get((chunk.id, name))
        if block is None:
            return None
        if block[0] == "Person":
            return blocks.find(block), chunk.doc_id
        return entity_of_block[block]

    raw_relations = []
    spouses: dict[tuple[Block, str], set[str]] = defaultdict(set)
    quotes: dict[tuple[Block, str], list[str]] = defaultdict(list)
    for chunk in ordered:
        for verified in extractions[chunk.id].relations:
            src = endpoint(chunk, verified.relation.src)
            dst = endpoint(chunk, verified.relation.dst)
            if src is None or dst is None:
                continue
            raw_relations.append((chunk, verified, src, dst))
            spouse = (
                verified.relation.type == "FAMILY_OF" and verified.relation.relation == "spouse"
            )
            for person, other in ((src, dst), (dst, src)):
                if isinstance(person, tuple):
                    quotes[person].append(verified.relation.quote)
                    if spouse and isinstance(other, tuple) and other[0] != person[0]:
                        spouses[person].add(entity_id("Person", other[0][1]))

    # Same-key persons merge by default; only clusters married to different spouses conflict.
    clusters_by_root: dict[Block, UnionFind[str]] = {}
    married_by_root: dict[Block, list[str]] = {}
    bound = 0
    for root, per_doc in candidates.items():
        married = married_by_root[root] = [doc for doc in sorted(per_doc) if spouses[(root, doc)]]
        clusters = clusters_by_root[root] = UnionFind[str]()
        for doc_a, doc_b in combinations(married, 2):
            if spouses[(root, doc_a)] & spouses[(root, doc_b)]:
                clusters.union(doc_a, doc_b)
        # Spouse clusters are pairwise disjoint and each root pair is asked at most once.
        bound += comb(len({clusters.find(doc) for doc in married}), 2)
    if bound > max_adjudications:
        raise RuntimeError(f"person adjudication needs up to {bound} calls (> {max_adjudications})")

    person_of: dict[tuple[Block, str], str] = {}
    calls = 0
    for root in sorted(candidates):
        docs = sorted(candidates[root])
        clusters = clusters_by_root[root]
        married = married_by_root[root]

        def context(cluster_root: str, root: Block = root, clusters=clusters, docs=married):
            members = [doc for doc in docs if clusters.find(doc) == cluster_root]
            facts = dict.fromkeys(q for doc in members for q in quotes[(root, doc)])
            name = candidates[root][cluster_root][0].name
            return PersonContext(name, list(facts)[:MAX_FACTS])

        rejected: set[tuple[str, str]] = set()
        merged_any = True
        while merged_any:
            merged_any = False
            cluster_roots = sorted({clusters.find(doc) for doc in married})
            for pair in combinations(cluster_roots, 2):
                if pair in rejected:
                    continue
                calls += 1
                if calls > max_adjudications:
                    raise RuntimeError(f"person adjudication exceeded {max_adjudications} calls")
                if adjudicate(context(pair[0]), context(pair[1])):
                    clusters.union(*pair)
                    merged_any = True
                    break
                rejected.add(pair)
        # Docs without a spouse join the earliest cluster.
        anchor = min((clusters.find(doc) for doc in married), default=docs[0])
        for doc in docs:
            if not spouses[(root, doc)]:
                clusters.union(anchor, doc)
        grouped: dict[str, list[str]] = defaultdict(list)
        for doc in docs:
            grouped[clusters.find(doc)].append(doc)
        # Earliest-doc cluster keeps the plain key; split ids embed their first doc id.
        for position, cluster_docs in enumerate(sorted(grouped.values())):
            canonical = root[1] if position == 0 else f"{root[1]}@{cluster_docs[0]}"
            mentions = [m for doc in cluster_docs for m in candidates[root][doc]]
            aliases = set().union(*(aliases_by_block[b] for b in components[root]))
            entity = _build_entity("Person", canonical, mentions, aliases)
            entities.append(entity)
            person_of.update(dict.fromkeys(((root, doc) for doc in cluster_docs), entity.id))

    merged: dict[tuple, ResolvedRelation] = {}
    for chunk, verified, src, dst in raw_relations:
        relation = verified.relation
        src_id = person_of[src] if isinstance(src, tuple) else src
        dst_id = person_of[dst] if isinstance(dst, tuple) else dst
        key = (relation.type, src_id, dst_id, relation.role, relation.relation)
        key += (relation.since, relation.until)
        resolved = merged.setdefault(
            key,
            ResolvedRelation(
                type=relation.type,
                src_id=src_id,
                dst_id=dst_id,
                role=relation.role,
                pct=relation.pct,
                relation=relation.relation,
                kind=relation.kind,
                since=relation.since,
                until=relation.until,
            ),
        )
        resolved.pct = resolved.pct if resolved.pct is not None else relation.pct
        resolved.kind = resolved.kind or relation.kind
        span = (chunk.start_char + verified.quote_start, chunk.start_char + verified.quote_end)
        if any(
            chunk_id == chunk.id and existing == span
            for chunk_id, existing in zip(resolved.chunk_ids, resolved.quote_spans, strict=True)
        ):
            continue
        resolved.chunk_ids.append(chunk.id)
        resolved.doc_ids.append(chunk.doc_id)
        resolved.quotes.append(relation.quote)
        resolved.quote_spans.append(span)

    def sort_key(key: tuple) -> tuple:
        return tuple((value is None, value if value is not None else 0) for value in key)

    return ResolvedGraph(
        entities=sorted(entities, key=lambda entity: entity.id),
        relations=[merged[key] for key in sorted(merged, key=sort_key)],
        skipped_alias_unions=skipped_alias_unions,
        adjudication_bound=bound,
        adjudications=calls,
    )
