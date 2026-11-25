import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from nexus.datagen.models import Edge, World

DocType = Literal["news", "annual_report", "disclosure", "press_release", "analyst_note"]
Lang = Literal["id", "en"]
Kind = Literal["report", "structure", "change", "profile", "deal"]

CONTEXT_TYPES = frozenset({"IN_SECTOR", "HEADQUARTERED_IN"})
MIN_SIZE, SMALL_CAP, REPORT_CAP, MAX_COMPONENTS = 3, 12, 24, 3
EN_SHARE, ALIAS_RATE = 0.3, 0.4
YEAR_RANGE = (2019, 2025)
CHANGE_SINCE = 2022
BLOOD_RELATIONS = frozenset({"parent", "child", "sibling"})
DEAL_TYPES = frozenset({"PARTNERS_WITH", "INVESTED_IN"})


KIND_DOC_TYPE: dict[Kind, DocType] = {
    "report": "annual_report",
    "structure": "analyst_note",
    "change": "disclosure",
    "profile": "news",
    "deal": "press_release",
}


class DocPlan(BaseModel):
    doc_id: str
    doc_type: DocType
    lang: Lang
    year: int
    edge_ids: list[str]
    surface_forms: dict[str, str]


@dataclass(eq=False)
class _Bundle:
    kind: Kind
    scope: str
    edges: list[Edge] = field(default_factory=list)


class _Planner:
    def __init__(self, world: World, n_docs: int, seed: int) -> None:
        self.world = world
        self.n_docs = n_docs
        self.rng = random.Random(seed)
        self.entities = {entity.id: entity for entity in world.entities}
        self.paths_of: dict[str, set[str]] = {}
        for path in world.hidden_paths:
            for edge_id in path.edge_ids:
                self.paths_of.setdefault(edge_id, set()).add(path.id)
        self.anchor: dict[str, str] = {}
        self.root: dict[str, str] = {}
        self.spill: list[tuple[Kind, Edge]] = []

    def plan(self) -> list[DocPlan]:
        bundles = self._initial_bundles()
        self._rebalance(bundles)
        self._place_spill(bundles)
        return self._finalize(bundles)

    def _initial_bundles(self) -> list[_Bundle]:
        edges = sorted(
            (edge for edge in self.world.edges if edge.type not in CONTEXT_TYPES),
            key=lambda edge: edge.id,
        )
        group_of = {e.src: e.dst for e in edges if e.type == "MEMBER_OF_GROUP"}
        parent_of = {e.src: e.dst for e in edges if e.type == "SUBSIDIARY_OF"}
        family_of = self._family_keys(edges)
        units: dict[tuple[Kind, str, str], list[Edge]] = {}
        for edge in edges:
            company = edge.src if edge.type in ("MEMBER_OF_GROUP", "SUBSIDIARY_OF") else edge.dst
            self.root[company] = parent_of.get(company, company)
            group = group_of.get(company, "~")
            if edge.type == "FAMILY_OF" or (edge.type == "FOUNDED" and edge.src in family_of):
                family = family_of[edge.id if edge.type == "FAMILY_OF" else edge.src]
                key: tuple[Kind, str, str] = ("profile", "", family)
            elif edge.type in DEAL_TYPES:
                key = ("deal", "", edge.src)
            elif edge.type == "MEMBER_OF_GROUP":
                key = ("structure", edge.dst, edge.dst)
            elif edge.until is not None or (edge.since or 0) >= CHANGE_SINCE:
                key = ("change", "", company)
            else:
                # A subsidiary's parent link keeps its board connected to the holding's report.
                key = ("report", group, company)
            self.anchor[edge.id] = key[2]
            units.setdefault(key, []).append(edge)
        bundles: list[_Bundle] = []
        for key in sorted(units):
            kind, scope, _ = key
            unit = sorted(units[key], key=lambda e: (e.type, e.id))
            bundles.extend(_Bundle(kind, scope, chunk) for chunk in self._carve(kind, unit))
        return bundles

    def _carve(self, kind: Kind, unit: list[Edge]) -> list[list[Edge]]:
        # Grow each chunk only through shared entities so every doc stays connected.
        target = -(-len(unit) // -(-len(unit) // self._cap(kind, unit)))
        remaining, chunks = list(unit), []
        while remaining:
            chunk = [remaining.pop(0)]
            nodes = {chunk[0].src, chunk[0].dst}
            grown = True
            while grown and len(chunk) < target:
                grown = False
                for edge in remaining:
                    linked = edge.src in nodes or edge.dst in nodes
                    if linked and self._valid(kind, [*chunk, edge]):
                        chunk.append(edge)
                        remaining.remove(edge)
                        nodes |= {edge.src, edge.dst}
                        grown = True
                        break
            chunks.append(chunk)
        return chunks

    def _family_keys(self, edges: list[Edge]) -> dict[str, str]:
        parent: dict[str, str] = {}

        def root(node: str) -> str:
            while parent.setdefault(node, node) != node:
                node = parent[node]
            return node

        family_edges = [edge for edge in edges if edge.type == "FAMILY_OF"]
        for edge in family_edges:
            first, second = sorted((root(edge.src), root(edge.dst)))
            # Marriages and in-law links would chain every family into one component.
            if edge.props["relation"] in BLOOD_RELATIONS:
                parent[second] = first
        keys = {node: root(node) for node in parent}
        linked: dict[str, set[str]] = {key: set() for key in keys.values()}
        for edge in family_edges:
            own, other = keys[edge.src], keys[edge.dst]
            if own != other:
                # Prefer the side already tied to that family, else the less-tied side.
                tied = own in linked[other]
                if tied or (other not in linked[own] and len(linked[other]) < len(linked[own])):
                    own, other = other, own
                linked[own].add(other)
            keys[edge.id] = own
        return keys

    def _single_root(self, edges: list[Edge]) -> bool:
        return len({self.root.get(self.anchor[e.id], "") for e in edges}) == 1

    def _cap(self, kind: Kind, edges: list[Edge]) -> int:
        return REPORT_CAP if kind == "report" and self._single_root(edges) else SMALL_CAP

    def _max_components(self, kind: Kind, edges: list[Edge]) -> int:
        if kind in ("structure", "profile"):
            return 1
        if kind == "report" and self._single_root(edges):
            return 1
        return MAX_COMPONENTS

    def _valid(self, kind: Kind, edges: list[Edge]) -> bool:
        if len(edges) > self._cap(kind, edges):
            return False
        seen: set[str] = set()
        for edge in edges:
            paths = self.paths_of.get(edge.id, set())
            # Hops of one hidden path must live in different docs.
            if paths & seen:
                return False
            seen |= paths
        nodes = {node for edge in edges for node in (edge.src, edge.dst)}
        if any(path.start in nodes and path.end in nodes for path in self.world.hidden_paths):
            return False
        if len({edge.src for edge in edges if edge.type in DEAL_TYPES}) > MAX_COMPONENTS:
            return False
        return components(edges) <= self._max_components(kind, edges)

    def _mergeable(self, left: _Bundle, right: _Bundle) -> bool:
        same = (left.kind, left.scope) == (right.kind, right.scope)
        return same and self._valid(left.kind, left.edges + right.edges)

    def _rebalance(self, bundles: list[_Bundle]) -> None:
        while True:
            small = [b for b in bundles if len(b.edges) < MIN_SIZE]
            if len(bundles) > self.n_docs or small:
                if not self._merge_best(bundles, small):
                    # No coherent merge left: scatter the smallest doc into related docs.
                    victim = min(small or bundles, key=lambda b: len(b.edges))
                    bundles.remove(victim)
                    self.spill += [(victim.kind, edge) for edge in victim.edges]
            elif len(bundles) < self.n_docs:
                self._split_largest(bundles)
            else:
                return

    def _merge_best(self, bundles: list[_Bundle], small: list[_Bundle]) -> bool:
        # Best fit: pair the smallest doc with the largest partner it still fits into.
        order = sorted(bundles, key=lambda b: len(b.edges))
        for first in small or order:
            for second in reversed(order):
                if second is first:
                    continue
                left, right = sorted((first, second), key=bundles.index)
                if self._mergeable(left, right):
                    left.edges += right.edges
                    bundles.remove(right)
                    return True
        return False

    def _split_largest(self, bundles: list[_Bundle]) -> None:
        for index in sorted(range(len(bundles)), key=lambda i: (-len(bundles[i].edges), i)):
            bundle = bundles[index]
            middle = len(bundle.edges) // 2
            for cut in sorted(
                range(MIN_SIZE, len(bundle.edges) - MIN_SIZE + 1), key=lambda c: abs(c - middle)
            ):
                left, right = bundle.edges[:cut], bundle.edges[cut:]
                if self._valid(bundle.kind, left) and self._valid(bundle.kind, right):
                    bundles[index : index + 1] = [
                        _Bundle(bundle.kind, bundle.scope, left),
                        _Bundle(bundle.kind, bundle.scope, right),
                    ]
                    return
        raise ValueError("too few edges for the requested number of docs")

    def _place_spill(self, bundles: list[_Bundle]) -> None:
        for kind, edge in self.spill:
            nodes = {edge.src, edge.dst}
            fits = [b for b in bundles if self._valid(b.kind, [*b.edges, edge])]
            if not fits:
                raise ValueError(f"no coherent doc can hold edge {edge.id}")
            best = max(
                fits,
                key=lambda b: (
                    b.kind == kind,
                    len(nodes & {n for e in b.edges for n in (e.src, e.dst)}),
                    -len(b.edges),
                ),
            )
            best.edges.append(edge)

    def _finalize(self, bundles: list[_Bundle]) -> list[DocPlan]:
        doc_types = [self._doc_type(bundle) for bundle in bundles]
        english = {index for index, doc_type in enumerate(doc_types) if doc_type == "analyst_note"}
        others = [index for index in range(len(bundles)) if index not in english]
        quota = round(EN_SHARE * len(bundles)) - len(english)
        english.update(self.rng.sample(others, max(quota, 0)))
        plans: list[DocPlan] = []
        for index, (bundle, doc_type) in enumerate(zip(bundles, doc_types, strict=True)):
            years = [y for e in bundle.edges for y in (e.since, e.until) if y is not None]
            plans.append(
                DocPlan(
                    doc_id=f"doc_{index + 1:03d}",
                    doc_type=doc_type,
                    lang="en" if index in english else "id",
                    year=max([self.rng.randint(*YEAR_RANGE), *years]),
                    edge_ids=[edge.id for edge in bundle.edges],
                    surface_forms=self._surface_forms(bundle.edges),
                )
            )
        return plans

    def _doc_type(self, bundle: _Bundle) -> DocType:
        if bundle.kind == "deal":
            types = Counter(edge.type for edge in bundle.edges)
            return "press_release" if types["PARTNERS_WITH"] >= types["INVESTED_IN"] else "news"
        if bundle.kind == "report" and self._max_components(bundle.kind, bundle.edges) > 1:
            return "news"
        return KIND_DOC_TYPE[bundle.kind]

    def _surface_forms(self, edges: list[Edge]) -> dict[str, str]:
        forms: dict[str, str] = {}
        for entity_id in sorted({node for edge in edges for node in (edge.src, edge.dst)}):
            entity = self.entities[entity_id]
            use_alias = entity.aliases and self.rng.random() < ALIAS_RATE
            forms[entity_id] = self.rng.choice(entity.aliases) if use_alias else entity.name
        return forms


def components(edges: list[Edge]) -> int:
    parent: dict[str, str] = {}

    def root(node: str) -> str:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for edge in edges:
        parent[root(edge.src)] = root(edge.dst)
    return len({root(node) for node in parent})


def plan_documents(world: World, n_docs: int = 100, seed: int = 42) -> list[DocPlan]:
    return _Planner(world, n_docs, seed).plan()
