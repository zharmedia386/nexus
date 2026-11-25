from collections import Counter

import pytest

from nexus.datagen.models import Edge, World
from nexus.datagen.planner import CONTEXT_TYPES, DocPlan, plan_documents
from nexus.datagen.world import build_world


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(42)


@pytest.fixture(scope="module")
def plans(world: World) -> list[DocPlan]:
    return plan_documents(world)


def test_doc_count_and_ids(plans: list[DocPlan]) -> None:
    assert len(plans) == 100
    assert len({plan.doc_id for plan in plans}) == 100


def test_deterministic(world: World, plans: list[DocPlan]) -> None:
    assert plan_documents(world) == plans
    assert plan_documents(world, seed=7) != plans


def test_every_edge_covered(world: World, plans: list[DocPlan]) -> None:
    covered = {edge_id for plan in plans for edge_id in plan.edge_ids}
    required = {edge.id for edge in world.edges if edge.type not in CONTEXT_TYPES}
    assert required <= covered


def test_hidden_path_hops_split(world: World, plans: list[DocPlan]) -> None:
    for path in world.hidden_paths:
        for plan in plans:
            assert len(set(path.edge_ids) & set(plan.edge_ids)) <= 1, (path.id, plan.doc_id)
            assert not {path.start, path.end} <= set(plan.surface_forms), (path.id, plan.doc_id)


def components(edges: list[Edge]) -> int:
    parent: dict[str, str] = {}

    def root(node: str) -> str:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for edge in edges:
        parent[root(edge.src)] = root(edge.dst)
    return len({root(node) for node in parent})


def test_docs_are_coherent(world: World, plans: list[DocPlan]) -> None:
    edges = {edge.id: edge for edge in world.edges}
    for plan in plans:
        limit = 1 if plan.doc_type in ("analyst_note", "annual_report") else 3
        count = components([edges[edge_id] for edge_id in plan.edge_ids])
        assert count <= limit, (plan.doc_id, plan.doc_type, count)


def test_lang_ratio(plans: list[DocPlan]) -> None:
    share = sum(plan.lang == "id" for plan in plans) / len(plans)
    assert 0.65 <= share <= 0.75
    assert all(plan.lang == "en" for plan in plans if plan.doc_type == "analyst_note")


def test_doc_type_mix(plans: list[DocPlan]) -> None:
    counts = Counter(plan.doc_type for plan in plans)
    assert set(counts) == {"news", "annual_report", "disclosure", "press_release", "analyst_note"}


def test_alias_usage(world: World, plans: list[DocPlan]) -> None:
    entities = {entity.id: entity for entity in world.entities}
    aliased = {entity.id for entity in world.entities if entity.aliases}
    used_alias = {
        entity_id
        for plan in plans
        for entity_id, form in plan.surface_forms.items()
        if entity_id in aliased and form != entities[entity_id].name
    }
    assert len(used_alias) >= 0.3 * len(aliased)


def test_surface_forms_complete(world: World, plans: list[DocPlan]) -> None:
    entities = {entity.id: entity for entity in world.entities}
    edges = {edge.id: edge for edge in world.edges}
    for plan in plans:
        referenced = {node for eid in plan.edge_ids for node in (edges[eid].src, edges[eid].dst)}
        assert set(plan.surface_forms) == referenced
        for entity_id, form in plan.surface_forms.items():
            entity = entities[entity_id]
            assert form in [entity.name, *entity.aliases]
            if entity.type == "Person":
                assert form == entity.name


def test_bundle_size(plans: list[DocPlan]) -> None:
    for plan in plans:
        upper = 24 if plan.doc_type == "annual_report" else 12
        assert 3 <= len(plan.edge_ids) <= upper, (plan.doc_id, plan.doc_type, len(plan.edge_ids))


def test_temporal_year_consistent(world: World, plans: list[DocPlan]) -> None:
    edges = {edge.id: edge for edge in world.edges}
    for plan in plans:
        for edge_id in plan.edge_ids:
            edge = edges[edge_id]
            if edge.since is not None:
                assert plan.year >= edge.since, (plan.doc_id, edge_id)
            if edge.until is not None:
                current = edge.since is not None and edge.since <= plan.year < edge.until
                assert plan.year >= edge.until or current, (plan.doc_id, edge_id)


def _blood_families(world: World) -> dict[str, str]:
    parent: dict[str, str] = {}

    def root(node: str) -> str:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for edge in world.edges:
        if edge.type == "FAMILY_OF":
            for node in (edge.src, edge.dst):
                root(node)
            if edge.props["relation"] in ("parent", "child", "sibling"):
                parent[root(edge.src)] = root(edge.dst)
    return {node: root(node) for node in parent}


def test_family_docs_stay_within_two_families(world: World, plans: list[DocPlan]) -> None:
    families = _blood_families(world)
    assert len(set(families.values())) >= 6
    edges = {edge.id: edge for edge in world.edges}
    for plan in plans:
        people = {
            node
            for edge_id in plan.edge_ids
            if edges[edge_id].type == "FAMILY_OF"
            for node in (edges[edge_id].src, edges[edge_id].dst)
        }
        assert len({families[person] for person in people}) <= 2, plan.doc_id


def test_deal_issuers_capped(world: World, plans: list[DocPlan]) -> None:
    edges = {edge.id: edge for edge in world.edges}
    deals = ("PARTNERS_WITH", "INVESTED_IN")
    for plan in plans:
        issuers = {edges[i].src for i in plan.edge_ids if edges[i].type in deals}
        assert len(issuers) <= 3, (plan.doc_id, len(issuers))
