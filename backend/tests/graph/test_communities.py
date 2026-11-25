from collections.abc import Iterator
from itertools import combinations

import pytest

from nexus.graph.communities import detect_communities
from nexus.graph.neo4j_store import GraphStore

TENANT = "test_graph_comm"


def clique(prefix: str, size: int = 5) -> tuple[list[str], list[tuple[str, str]]]:
    nodes = [f"{prefix}{index}" for index in range(size)]
    return nodes, list(combinations(nodes, 2))


def two_cliques() -> tuple[list[str], list[tuple[str, str]]]:
    nodes_a, edges_a = clique("a")
    nodes_b, edges_b = clique("b")
    return nodes_a + nodes_b, edges_a + edges_b + [("a0", "b0")]


def test_two_cliques_two_communities():
    nodes, edges = two_cliques()
    communities = detect_communities(nodes, edges)
    assert [c.level for c in communities] == [0, 0]
    assert [c.member_ids for c in communities] == [
        ["a0", "a1", "a2", "a3", "a4"],
        ["b0", "b1", "b2", "b3", "b4"],
    ]
    assert [c.id for c in communities] == ["c0_0", "c0_1"]


def test_deterministic_with_seed():
    nodes, edges = two_cliques()
    assert detect_communities(nodes, edges, seed=7) == detect_communities(
        list(reversed(nodes)), edges, seed=7
    )


def test_large_community_split_into_level1():
    nodes, edges = two_cliques()
    communities = detect_communities(nodes, edges, max_size=4)
    top_ids = {c.id for c in communities if c.level == 0}
    children = [c for c in communities if c.level == 1]
    assert children and all(c.parent_id in top_ids for c in children)
    assert {m for c in children for m in c.member_ids} == set(nodes)
    assert [c.id for c in children] == [f"c1_{index}" for index in range(len(children))]


def test_singletons_excluded():
    nodes, edges = two_cliques()
    communities = detect_communities(nodes + ["lonely"], edges)
    assert all("lonely" not in c.member_ids for c in communities)


@pytest.fixture
def store() -> Iterator[GraphStore]:
    with GraphStore() as graph_store:
        graph_store.ensure_schema()
        graph_store.clear_tenant(TENANT)
        yield graph_store
        graph_store.clear_tenant(TENANT)
        graph_store._run("MATCH (c:Community {tenant_id: $t}) DETACH DELETE c", t=TENANT)


def seed_graph(store: GraphStore, nodes: list[str], edges: list[tuple[str, str, str]]) -> None:
    store._run(
        "UNWIND $nodes AS id CREATE (:Entity:Company {tenant_id: $t, id: id, name: id})",
        t=TENANT,
        nodes=nodes,
    )
    for rel_type, src, dst in edges:
        store._run(
            f"MATCH (a:Entity {{tenant_id: $t, id: $src}}), (b:Entity {{tenant_id: $t, id: $dst}}) "
            f"CREATE (a)-[:{rel_type} {{tenant_id: $t}}]->(b)",
            t=TENANT,
            src=src,
            dst=dst,
        )


@pytest.mark.integration
def test_read_entity_graph_excludes_context_edges(store: GraphStore):
    seed_graph(
        store,
        ["x", "y", "z"],
        [
            ("OWNS_STAKE", "x", "y"),
            ("IN_SECTOR", "y", "z"),
            ("HEADQUARTERED_IN", "x", "z"),
            ("IN_COMMUNITY", "x", "z"),
            ("CHILD_OF", "y", "z"),
        ],
    )
    assert store.read_entity_graph(TENANT) == (["x", "y", "z"], [("x", "y")])


@pytest.mark.integration
def test_write_communities_idempotent(store: GraphStore):
    nodes, edges = two_cliques()
    seed_graph(store, nodes, [("OWNS_STAKE", src, dst) for src, dst in edges])
    communities = detect_communities(nodes, edges)
    first = store.write_communities(TENANT, communities)
    assert store.write_communities(TENANT, communities) == first == 2
    rows = store._run(
        "MATCH (e:Entity {tenant_id: $t})-[:IN_COMMUNITY]->(c:Community {tenant_id: $t}) "
        "RETURN c.id AS id, c.size AS size, count(e) AS members ORDER BY id",
        t=TENANT,
    )
    assert rows == [
        {"id": "c0_0", "size": 5, "members": 5},
        {"id": "c0_1", "size": 5, "members": 5},
    ]
    assert store.counts(TENANT)["nodes"] == 10
