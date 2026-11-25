import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import comb
from pathlib import Path
from statistics import fmean
from typing import get_args

from nexus.datagen.models import Edge, EntityType, World
from nexus.datagen.planner import CONTEXT_TYPES, DocPlan
from nexus.datagen.reference import REFERENCE_DOC_ID, TICKER
from nexus.eval.harness import RUNS_DIR
from nexus.eval.metrics import normalize
from nexus.graph.resolve import Mention, ResolvedGraph, ResolvedRelation, entity_key
from nexus.graph.schema import ExtractionResult

# FAMILY_OF reads "src is <relation> of dst", so a swapped pair is right with the inverse label.
INVERSE_RELATION = {
    "spouse": "spouse",
    "sibling": "sibling",
    "in-law": "in-law",
    "parent": "child",
    "child": "parent",
}
SYMMETRIC_TYPES = frozenset({"PARTNERS_WITH"})
ENTITY_TYPES: tuple[EntityType, ...] = get_args(EntityType)

Gold = dict[Mention, str | None]
FormIndex = dict[tuple[EntityType, str], set[str]]


@dataclass(frozen=True)
class PRF:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class Counts:
    tp: int
    predicted: int
    gold: int

    def prf(self) -> PRF:
        # Empty predictions against non-empty gold score 0, never a vacuous 1.
        precision = self.tp / self.predicted if self.predicted else float(not self.gold)
        recall = self.tp / self.gold if self.gold else float(not self.predicted)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return PRF(round(precision, 4), round(recall, 4), round(f1, 4), self.gold)


@dataclass
class RelationReport:
    macro: PRF
    micro: PRF
    temporal_accuracy: float | None
    temporal_support: int
    by_type: dict[str, PRF]
    unscored_by_type: dict[str, int]


@dataclass(frozen=True)
class ERReport:
    precision: float
    recall: float
    f1: float
    collision_merges: int
    ticker_links: int
    ticker_total: int


@dataclass
class GraphEval:
    docs: int
    entity_macro: PRF
    entity_micro: PRF
    relations: RelationReport
    er: ERReport
    dropped_unverified: int
    dropped_unknown_entity: int
    unmapped_mentions_by_type: dict[str, int]
    config: dict[str, object] = field(default_factory=dict)


def _add(index: FormIndex, entity_id: str, entity_type: EntityType, forms: list[str]) -> None:
    for form in forms:
        if key := entity_key(form, entity_type):
            index.setdefault((entity_type, key), set()).add(entity_id)


def _doc_indexes(doc_id: str, world: World, plans: dict[str, DocPlan]) -> list[FormIndex]:
    entities = {entity.id: entity for entity in world.entities}
    if doc_id == REFERENCE_DOC_ID:
        index: FormIndex = {}
        for entity in world.entities:
            if entity.type == "Company":
                _add(index, entity.id, entity.type, [entity.name, *entity.aliases])
        return [index]
    plan = plans.get(doc_id)
    if plan is None:
        return []
    # The planned surface form wins over another entity's canonical name or alias.
    surface: FormIndex = {}
    names: FormIndex = {}
    for entity_id, form in plan.surface_forms.items():
        entity = entities[entity_id]
        _add(surface, entity_id, entity.type, [form])
        _add(names, entity_id, entity.type, [entity.name, *entity.aliases])
    return [surface, names]


def _lookup(name: str, indexes: list[FormIndex]) -> str | None:
    for index in indexes:
        found = set().union(*(index.get((t, entity_key(name, t)), set()) for t in ENTITY_TYPES))
        if found:
            # Ambiguous forms (e.g. two colliding namesakes in one doc) cannot be attributed.
            return found.pop() if len(found) == 1 else None
    return None


def gold_ids(mentions: list[Mention], world: World, plans: dict[str, DocPlan]) -> Gold:
    indexes: dict[str, list[FormIndex]] = {}
    gold: Gold = {}
    for mention in mentions:
        if mention.doc_id not in indexes:
            indexes[mention.doc_id] = _doc_indexes(mention.doc_id, world, plans)
        gold[mention] = _lookup(mention.name, indexes[mention.doc_id])
    return gold


def gold_id(mention: Mention, world: World, plans: dict[str, DocPlan]) -> str | None:
    return gold_ids([mention], world, plans)[mention]


def _mentions(graph: ResolvedGraph) -> list[Mention]:
    return [mention for entity in graph.entities for mention in entity.mentions]


def _entity_counts(mentions: list[Mention], gold: Gold, plan: DocPlan) -> Counts:
    doc_mentions = [mention for mention in mentions if mention.doc_id == plan.doc_id]
    mapped = {gold[m] for m in doc_mentions if gold[m] is not None}
    unmapped = {normalize(m.name) for m in doc_mentions if gold[m] is None}
    return Counts(
        len(mapped & plan.surface_forms.keys()),
        len(mapped) + len(unmapped),
        len(plan.surface_forms),
    )


def entity_scores(mentions: list[Mention], gold: Gold, plan: DocPlan) -> PRF:
    return _entity_counts(mentions, gold, plan).prf()


def entity_gold(graph: ResolvedGraph, gold: Gold) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for entity in graph.entities:
        votes = Counter(gold[m] for m in entity.mentions if gold[m] is not None).most_common(2)
        tied = len(votes) == 2 and votes[0][1] == votes[1][1]
        mapping[entity.id] = votes[0][0] if votes and not tied else None
    return mapping


def _matches(relation: ResolvedRelation, src: str | None, dst: str | None, edge: Edge) -> bool:
    if relation.type != edge.type or src is None or dst is None:
        return False
    forward = (src, dst) == (edge.src, edge.dst)
    backward = (dst, src) == (edge.src, edge.dst)
    if edge.type == "SERVES_AS":
        return forward and relation.role == edge.props.get("role")
    if edge.type == "FAMILY_OF":
        label = str(edge.props.get("relation"))
        return (forward and relation.relation == label) or (
            backward and relation.relation == INVERSE_RELATION.get(label)
        )
    return forward or (backward and edge.type in SYMMETRIC_TYPES)


def relation_scores(
    graph: ResolvedGraph, gold: Gold, world: World, plans: dict[str, DocPlan]
) -> RelationReport:
    edges = {edge.id: edge for edge in world.edges}
    endpoint = entity_gold(graph, gold)
    gold_edges = {edge_id for plan in plans.values() for edge_id in plan.edge_ids}
    matched_by_doc: dict[str, set[str]] = defaultdict(set)
    wrong_by_doc: dict[str, set[tuple]] = defaultdict(set)
    matched: dict[str, list[ResolvedRelation]] = defaultdict(list)
    wrong: set[tuple] = set()
    unscored: Counter[str] = Counter()
    for relation in graph.relations:
        src, dst = endpoint[relation.src_id], endpoint[relation.dst_id]
        docs = sorted(set(relation.doc_ids) & plans.keys())
        if not docs or relation.type in CONTEXT_TYPES:
            # Context types are never planned and ref/unplanned docs have no gold edges.
            unscored[relation.type] += 1
            continue
        # Temporal variants of one claim collapse, so duplicates neither add TPs nor extra FPs.
        key = (relation.type, src or relation.src_id, dst or relation.dst_id, relation.role)
        key += (relation.relation,)
        hit = None
        for doc_id in docs:
            edge_id = next(
                (e for e in plans[doc_id].edge_ids if _matches(relation, src, dst, edges[e])),
                None,
            )
            if edge_id is None:
                wrong_by_doc[doc_id].add(key)
            else:
                matched_by_doc[doc_id].add(edge_id)
                hit = hit or edge_id
        if hit is None:
            wrong.add(key)
        else:
            matched[hit].append(relation)

    per_doc = [
        Counts(
            len(matched_by_doc[doc_id]),
            len(matched_by_doc[doc_id]) + len(wrong_by_doc[doc_id]),
            len(plan.edge_ids),
        ).prf()
        for doc_id, plan in plans.items()
    ]
    gold_types = Counter(edges[e].type for e in gold_edges)
    hit_types = Counter(edges[e].type for e in matched)
    wrong_types = Counter(key[0] for key in wrong)
    by_type = {
        rel_type: Counts(
            hit_types[rel_type], hit_types[rel_type] + wrong_types[rel_type], gold_types[rel_type]
        ).prf()
        for rel_type in sorted(gold_types.keys() | wrong_types.keys())
    }
    # An edge is temporally right only if every claim matched to it carries the gold years.
    temporal = [
        all((r.since, r.until) == (edges[e].since, edges[e].until) for r in relations)
        for e, relations in matched.items()
    ]
    return RelationReport(
        macro=_macro(per_doc),
        micro=Counts(len(matched), len(matched) + len(wrong), len(gold_edges)).prf(),
        temporal_accuracy=round(fmean(temporal), 4) if temporal else None,
        temporal_support=len(temporal),
        by_type=by_type,
        unscored_by_type=dict(sorted(unscored.items())),
    )


def _macro(scores: list[PRF]) -> PRF:
    if not scores:
        return PRF(0.0, 0.0, 0.0, 0)
    return PRF(
        round(fmean(s.precision for s in scores), 4),
        round(fmean(s.recall for s in scores), 4),
        round(fmean(s.f1 for s in scores), 4),
        sum(s.support for s in scores),
    )


def er_scores(graph: ResolvedGraph, gold: Gold, world: World) -> ERReport:
    cells: Counter[tuple[str, str]] = Counter()
    entity_of: dict[Mention, str] = {}
    golds_of: dict[str, set[str]] = defaultdict(set)
    for entity in graph.entities:
        for mention in entity.mentions:
            entity_of[mention] = entity.id
            if (gold_entity := gold[mention]) is not None:
                cells[(entity.id, gold_entity)] += 1
                golds_of[entity.id].add(gold_entity)
    by_entity: Counter[str] = Counter()
    by_gold: Counter[str] = Counter()
    for (entity_id, gold_entity), count in cells.items():
        by_entity[entity_id] += count
        by_gold[gold_entity] += count
    pairs = Counts(
        sum(comb(n, 2) for n in cells.values()),
        sum(comb(n, 2) for n in by_entity.values()),
        sum(comb(n, 2) for n in by_gold.values()),
    ).prf()
    collision_merges = sum(
        any(a in golds and b in golds for a, b in world.collisions) for golds in golds_of.values()
    )
    mentions_of: dict[str, list[Mention]] = defaultdict(list)
    for mention in entity_of:
        if (gold_entity := gold[mention]) is not None:
            mentions_of[gold_entity].append(mention)
    linked = total = 0
    for company in world.entities:
        tickers = {normalize(a) for a in company.aliases if TICKER.fullmatch(a)}
        own = mentions_of[company.id]
        ticker_mentions = [m for m in own if normalize(m.name) in tickers]
        name_entities = {entity_of[m] for m in own if normalize(m.name) not in tickers}
        # Only tickers seen alongside a name mention can be linked at all.
        if company.type != "Company" or not ticker_mentions or not name_entities:
            continue
        total += 1
        linked += all(entity_of[m] in name_entities for m in ticker_mentions)
    return ERReport(pairs.precision, pairs.recall, pairs.f1, collision_merges, linked, total)


def evaluate_graph(
    graph: ResolvedGraph,
    extractions: dict[str, ExtractionResult],
    world: World,
    plans: dict[str, DocPlan],
) -> GraphEval:
    mentions = _mentions(graph)
    gold = gold_ids(mentions, world, plans)
    entity_counts = [_entity_counts(mentions, gold, plan) for plan in plans.values()]
    scored = [m for m in mentions if m.doc_id in plans]
    return GraphEval(
        docs=len(plans),
        entity_macro=_macro([counts.prf() for counts in entity_counts]),
        entity_micro=Counts(
            sum(c.tp for c in entity_counts),
            sum(c.predicted for c in entity_counts),
            sum(c.gold for c in entity_counts),
        ).prf(),
        relations=relation_scores(graph, gold, world, plans),
        er=er_scores(graph, gold, world),
        dropped_unverified=sum(e.dropped_unverified for e in extractions.values()),
        dropped_unknown_entity=sum(e.dropped_unknown_entity for e in extractions.values()),
        unmapped_mentions_by_type=dict(
            sorted(Counter(m.type for m in scored if gold[m] is None).items())
        ),
    )


def _row(label: str, score: PRF) -> str:
    return f"| {label} | {score.precision} | {score.recall} | {score.f1} | {score.support} |"


def to_markdown(stamp: str, result: GraphEval) -> str:
    relations, er = result.relations, result.er
    lines = [
        f"# Graph eval {stamp}",
        "",
        *(f"- {key}: {value}" for key, value in result.config.items()),
        f"- docs scored: {result.docs}",
        "",
        "| metric | precision | recall | f1 | support |",
        "|---|---|---|---|---|",
        _row("entity (macro over docs)", result.entity_macro),
        _row("entity (micro)", result.entity_micro),
        _row("relation (macro over docs)", relations.macro),
        _row("relation (micro)", relations.micro),
        f"| entity resolution (pairwise) | {er.precision} | {er.recall} | {er.f1} | - |",
        "",
        f"- temporal accuracy: {relations.temporal_accuracy} (n={relations.temporal_support})",
        f"- collision merges: {er.collision_merges}",
        f"- ticker links: {er.ticker_links}/{er.ticker_total}",
        f"- dropped (unverified quote): {result.dropped_unverified}",
        f"- dropped (unknown entity): {result.dropped_unknown_entity}",
        f"- unmapped mentions by type: {result.unmapped_mentions_by_type}",
        f"- not scored (no gold edge type / no planned doc): {relations.unscored_by_type}",
        "",
        "| relation type | precision | recall | f1 | support |",
        "|---|---|---|---|---|",
        *(_row(rel_type, score) for rel_type, score in relations.by_type.items()),
    ]
    return "\n".join(lines) + "\n"


def write_graph_report(result: GraphEval, out_dir: Path = RUNS_DIR) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"graph-{stamp}"
    payload = {"timestamp": stamp, **asdict(result)}
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    path = base.with_suffix(".md")
    path.write_text(to_markdown(stamp, result), encoding="utf-8")
    return path
