from collections.abc import Iterator

import pytest

from nexus.graph.communities import Community
from nexus.graph.neo4j_store import GraphStore, make_path
from nexus.graph.resolve import Mention, ResolvedEntity, ResolvedGraph, ResolvedRelation

TENANT_A = "test_graph_a"
TENANT_B = "test_graph_b"


class ForbiddenDriver:
    def execute_query(self, *args: object, **kwargs: object) -> None:
        pytest.fail("driver must not be used before validation")


def sample_graph(rel_type: str = "OWNS_STAKE") -> ResolvedGraph:
    return ResolvedGraph(
        entities=[
            ResolvedEntity(
                "c1",
                "Company",
                "BRMN",
                ["Bromo"],
                [Mention("d#1", "d", "BRMN", "Company"), Mention("d#0", "d", "Bromo", "Company")],
            ),
            ResolvedEntity("p1", "Person", "Budi", [], []),
        ],
        relations=[
            ResolvedRelation(
                rel_type,  # type: ignore[arg-type]
                "p1",
                "c1",
                None,
                12.5,
                None,
                None,
                2019,
                None,
                ["d#0"],
                ["d"],
                ["Budi owns 12.5%"],
                [(3, 18)],
            )
        ],
    )


def test_rejects_unknown_rel_type():
    store = GraphStore(ForbiddenDriver())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        store.write_graph(TENANT_A, sample_graph("DROP_ALL} DETACH DELETE"))


def test_rejects_bad_tenant():
    store = GraphStore(ForbiddenDriver())  # type: ignore[arg-type]
    for call in (
        store.clear_tenant,
        store.counts,
        store.stats,
        lambda t: store.write_graph(t, sample_graph()),
    ):
        with pytest.raises(ValueError):
            call("Bad Tenant")


@pytest.fixture
def store() -> Iterator[GraphStore]:
    with GraphStore() as graph_store:
        graph_store.ensure_schema()
        for tenant in (TENANT_A, TENANT_B):
            graph_store.clear_tenant(tenant)
        yield graph_store
        for tenant in (TENANT_A, TENANT_B):
            graph_store.clear_tenant(tenant)


@pytest.mark.integration
def test_write_graph_idempotent(store: GraphStore):
    first = store.write_graph(TENANT_A, sample_graph())
    assert store.write_graph(TENANT_A, sample_graph()) == first == {"nodes": 2, "relationships": 1}


@pytest.mark.integration
def test_tenant_isolation(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    store.write_graph(TENANT_B, sample_graph())
    store.clear_tenant(TENANT_A)
    assert store.counts(TENANT_A) == {"nodes": 0, "relationships": 0}
    assert store.counts(TENANT_B) == {"nodes": 2, "relationships": 1}


@pytest.mark.integration
def test_provenance_arrays_stored(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    row = store._run(
        "MATCH (:Person {tenant_id: $t})-[r:OWNS_STAKE]->(:Company {tenant_id: $t}) "
        "RETURN r.quotes AS quotes, r.quote_starts AS starts, r.quote_ends AS ends, "
        "r.chunk_ids AS chunk_ids, r.since AS since, r.tenant_id AS tenant",
        t=TENANT_A,
    )[0]
    assert row == {
        "quotes": ["Budi owns 12.5%"],
        "starts": [3],
        "ends": [18],
        "chunk_ids": ["d#0"],
        "since": 2019,
        "tenant": TENANT_A,
    }


@pytest.mark.integration
def test_clear_tenant_batches_and_spares_other_tenant(store: GraphStore, monkeypatch):
    many = ResolvedGraph(
        entities=[
            ResolvedEntity(f"c{index}", "Company", f"Co {index}", [], []) for index in range(5)
        ],
        relations=[],
    )
    store.write_graph(TENANT_A, many)
    store.write_graph(TENANT_B, sample_graph())
    monkeypatch.setattr("nexus.graph.neo4j_store.BATCH", 2)
    store.clear_tenant(TENANT_A)
    assert store.counts(TENANT_A) == {"nodes": 0, "relationships": 0}
    assert store.counts(TENANT_B) == {"nodes": 2, "relationships": 1}
    quotes = store._run(
        "MATCH ()-[r:OWNS_STAKE {tenant_id: $t}]->() RETURN r.quotes AS quotes", t=TENANT_B
    )
    assert quotes == [{"quotes": ["Budi owns 12.5%"]}]


@pytest.mark.integration
def test_entity_provenance_stored(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    rows = store._run(
        "MATCH (e:Entity {tenant_id: $t}) RETURN e.id AS id, e.chunk_ids AS chunk_ids, "
        "e.doc_ids AS doc_ids ORDER BY id",
        t=TENANT_A,
    )
    assert rows == [
        {"id": "c1", "chunk_ids": ["d#0", "d#1"], "doc_ids": ["d"]},
        {"id": "p1", "chunk_ids": [], "doc_ids": []},
    ]


def chain_graph() -> ResolvedGraph:
    def rel(rel_type: str, src: str, dst: str) -> ResolvedRelation:
        return ResolvedRelation(
            rel_type,  # type: ignore[arg-type]
            src, dst, None, None, None, None, None, None, ["d#0"], ["d"], ["q"], [(0, 1)],
        )  # fmt: skip

    return ResolvedGraph(
        entities=[
            ResolvedEntity("p1", "Person", "Budi", [], []),
            ResolvedEntity("c1", "Company", "BRMN", [], []),
            ResolvedEntity("c2", "Company", "Sinar", [], []),
            ResolvedEntity("s1", "Sector", "Mining", [], []),
        ],
        relations=[
            rel("OWNS_STAKE", "p1", "c1"),
            rel("IN_SECTOR", "c1", "s1"),
            rel("IN_SECTOR", "c2", "s1"),
        ],
    )


@pytest.mark.integration
def test_entity_node_and_edges_are_tenant_scoped(store: GraphStore):
    store.write_graph(TENANT_A, chain_graph())
    assert store.entity_node(TENANT_B, "p1") is None
    node = store.entity_node(TENANT_A, "c1")
    assert node is not None and (node["name"], node["type"]) == ("BRMN", "Company")
    edges = store.entity_edges(TENANT_A, "c1")
    # The IN_SECTOR context edge is excluded.
    assert [(e["type"], e["outgoing"], e["other_id"], e["other_type"]) for e in edges] == [
        ("OWNS_STAKE", False, "p1", "Person")
    ]
    assert store.entity_edges(TENANT_B, "c1") == []


@pytest.mark.integration
def test_paths_between_skips_context_edges_and_tenants(store: GraphStore):
    store.write_graph(TENANT_A, chain_graph())
    store.write_graph(TENANT_B, chain_graph())
    # c2 is only reachable from p1 through the sector hub, which is excluded.
    assert store.paths_between(TENANT_A, ["p1", "c2"]) == []
    assert store.paths_between(TENANT_A, ["p1", "c1"])[0].rel_types == ["OWNS_STAKE"]
    store.clear_tenant(TENANT_B)
    assert store.paths_between(TENANT_B, ["p1", "c1"]) == []


@pytest.mark.integration
def test_list_communities_by_level(store: GraphStore):
    store.write_graph(TENANT_A, chain_graph())
    store.write_communities(
        TENANT_A, [Community("k0", 0, None, ["p1", "c1"]), Community("k1", 1, "k0", ["p1"])]
    )
    store.write_community_summary(TENANT_A, "k0", "Grup", "ringkasan", [])
    level0 = store.list_communities(TENANT_A, 0)
    assert level0 == [
        {
            "id": "k0",
            "level": 0,
            "size": 2,
            "title": "Grup",
            "summary": "ringkasan",
            "parent_id": None,
            "member_ids": ["c1", "p1"],
            "member_names": ["BRMN", "Budi"],
            "summary_chunk_ids": [],
        }
    ]
    assert store.list_communities(TENANT_A, 1)[0]["parent_id"] == "k0"
    assert store.list_communities(TENANT_B, 0) == []


def test_make_path_aligns_hop_evidence():
    path = make_path(
        ["a", "b", "c"],
        ["A", "B", "C"],
        ["OWNS_STAKE", "FOUNDED"],
        [["d1#0", "d1#1"], ["d2#0"]],
        [["q1", "q2"], ["q3"]],
        [["d1", "d1"], ["d2"]],
    )
    first, second = path.hops
    assert (first.src_name, first.dst_name, first.rel_type) == ("A", "B", "OWNS_STAKE")
    assert (first.chunk_ids, first.quotes, first.doc_ids) == (
        ["d1#0", "d1#1"],
        ["q1", "q2"],
        ["d1", "d1"],
    )
    assert (second.src_id, second.dst_id, second.quotes) == ("b", "c", ["q3"])
    assert make_path(["a", "b"], ["A", "B"], ["X"], [["c"]]).hops[0].quotes == []


@pytest.mark.integration
def test_paths_between_fills_hops(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    (path,) = store.paths_between(TENANT_A, ["p1", "c1"])
    (hop,) = path.hops
    assert (hop.src_id, hop.dst_id, hop.quotes, hop.doc_ids) == (
        "p1",
        "c1",
        ["Budi owns 12.5%"],
        ["d"],
    )


@pytest.mark.integration
def test_stats_counts_by_type_and_tenant(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    assert store.stats(TENANT_A) == {
        "nodes": 2,
        "relationships": 1,
        "by_type": {"Company": 1, "Person": 1},
        "top": [
            {"id": "c1", "name": "BRMN", "type": "Company", "degree": 1},
            {"id": "p1", "name": "Budi", "type": "Person", "degree": 1},
        ],
    }
    assert store.stats(TENANT_B) == {"nodes": 0, "relationships": 0, "by_type": {}, "top": []}


@pytest.mark.integration
def test_search_entities_alias_ranking_and_tenant(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    assert [r["id"] for r in store.search_entities(TENANT_A, "bromo")] == ["c1"]
    assert store.search_entities(TENANT_A, "PT Bromo Tbk")[0]["match"] == "exact"
    assert store.search_entities(TENANT_A, "bud")[0]["match"] == "prefix"
    assert store.search_entities(TENANT_B, "bromo") == []


@pytest.mark.integration
def test_list_communities_includes_members(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    store.write_communities(TENANT_A, [Community("k0", 0, None, ["c1", "p1"])])
    store.write_community_summary(TENANT_A, "k0", "T", "S", ["d#0"])
    (row,) = store.list_communities(TENANT_A, 0)
    assert row["member_ids"] == ["c1", "p1"] and row["member_names"] == ["BRMN", "Budi"]
    assert row["summary_chunk_ids"] == ["d#0"]


def test_make_path_marks_reversed_edges():
    path = make_path(["a", "b", "c"], ["A", "B", "C"], ["X", "Y"], [[], []], None, None, ["a", "c"])
    assert [hop.forward for hop in path.hops] == [True, False]
    assert make_path(["a", "b"], ["A", "B"], ["X"], [[]]).hops[0].forward is True


@pytest.mark.integration
def test_paths_between_hop_direction(store: GraphStore):
    store.write_graph(TENANT_A, sample_graph())
    (forward,) = store.paths_between(TENANT_A, ["p1", "c1"])
    (backward,) = store.paths_between(TENANT_A, ["c1", "p1"])
    assert forward.hops[0].forward is True and backward.hops[0].forward is False
