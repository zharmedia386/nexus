import re
from collections.abc import Iterator

import pytest

from nexus.config import get_settings
from nexus.db.repo import ChunkRow
from nexus.graph.neo4j_store import FrontierEdge, GraphPath, GraphStore
from nexus.graph.resolve import Mention, ResolvedEntity, ResolvedGraph, ResolvedRelation
from nexus.llm import GatewayError
from nexus.retrieval.graph_local import (
    Hop,
    TraversalStep,
    link_entities,
    retrieve_graph_local,
    traversal_paths,
    traverse,
)
from nexus.retrieval.modes import RERANK_POOL_FACTOR, retrieve
from nexus.vector.milvus_store import Hit

TENANT = "test_graph_local"


class FakeStore:
    def __init__(self, hits: list[Hit]) -> None:
        self.hits = hits

    def hybrid_search(self, tenant, query_text, vector, k):
        return self.hits


def edge(src: str, dst: str, chunks: list[str], rel: str = "OWNS_STAKE") -> FrontierEdge:
    return FrontierEdge(
        f"{src}-{dst}",
        rel,
        src,
        src.upper(),
        dst,
        dst.upper(),
        None,
        None,
        None,
        2019,
        None,
        chunks,
    )


class FakeGraph:
    def __init__(
        self,
        lexicon: dict[str, str],
        paths: list[GraphPath] | None = None,
        edges: list[FrontierEdge] | None = None,
    ) -> None:
        self.lexicon = lexicon
        self.paths = paths or []
        self.edges = edges or []
        self.calls: list[tuple[str, object]] = []

    def frontier_edges(self, tenant, entity_ids, limit=40, exclude=None):
        self.calls.append(("frontier_edges", list(entity_ids)))
        touching = [
            e
            for e in self.edges
            if (e.src_id in entity_ids or e.dst_id in entity_ids) and e.key not in (exclude or [])
        ]
        return touching[:limit]

    def entity_lexicon(self, tenant):
        return self.lexicon

    def entities_in_chunks(self, tenant, chunk_ids, limit=3):
        self.calls.append(("entities_in_chunks", chunk_ids))
        return ["co_9"]

    def paths_between(self, tenant, ids, max_hops=4):
        self.calls.append(("paths_between", ids))
        return self.paths

    def neighbourhood(self, tenant, ids, limit=40):
        self.calls.append(("neighbourhood", ids))
        return []


def no_llm(messages, schema, **kwargs):
    return Hop(follow=[], done=True)


def scripted_llm(targets: list[str], done_at: int | None = None):
    """Follows, at hop i, the offered edge whose far end is targets[i]."""
    calls = {"n": 0}

    def llm(messages, schema, **kwargs):
        assert kwargs == {"temperature": 0.0, "timeout": 120}
        hop = calls["n"]
        calls["n"] += 1
        target = targets[hop]
        pattern = rf"^(E\d+): (?:{target} -\[|.*-> {target}$)"
        label = re.search(pattern, messages[1]["content"], re.MULTILINE)
        follow = [label.group(1)] if label else []
        return Hop(follow=follow, done=done_at == hop + 1)

    return llm


def fake_embedder(texts):
    return [[0.0] for _ in texts]


def chunk_rows(ids: list[str]) -> list[ChunkRow]:
    return [
        ChunkRow(chunk_id, chunk_id.split(":")[0], 0, 0, 1, f"text {chunk_id}") for chunk_id in ids
    ]


@pytest.fixture
def fake_chunks(monkeypatch):
    monkeypatch.setattr(
        "nexus.retrieval.graph_local.repo.get_chunks", lambda conn, tenant, ids: chunk_rows(ids)
    )


def test_links_ticker_alias_and_lowercase():
    lexicon = {"wtoy": "co_1", "wahana teguh": "co_1", "budi santoso": "pe_1"}
    assert link_entities("Siapa pemilik WTOY dan BUDI santoso?", lexicon) == ["pe_1", "co_1"]
    assert link_entities("PT Wahana Teguh Tbk.", lexicon) == ["co_1"]
    assert link_entities("wtoyx dan budi", lexicon) == []


def test_link_prefers_longest_match():
    lexicon = {"mega": "co_1", "mega persada": "co_2", "persada": "co_3", "nirwana": "co_4"}
    assert link_entities("saham Mega Persada dan Nirwana", lexicon) == ["co_2", "co_4"]


def test_lexicon_excludes_ambiguous_forms(monkeypatch):
    rows = [
        {"id": "co_1", "name": "PT Mega Persada Tbk", "aliases": ["MPTE", "Mega"]},
        {"id": "co_2", "name": "Mega Nirwana", "aliases": ["mega"]},
    ]
    graph = GraphStore()
    monkeypatch.setattr(graph, "_run", lambda query, **params: rows)
    assert graph.entity_lexicon(TENANT) == {
        "mega persada": "co_1",
        "mpte": "co_1",
        "mega nirwana": "co_2",
    }


def test_lexicon_cached_per_tenant_until_invalidated(monkeypatch):
    queries: list[str] = []

    def run(query, **params):
        queries.append(params["tenant"])
        return [{"id": "co_1", "name": "Mega Persada", "aliases": []}]

    graph = GraphStore()
    monkeypatch.setattr(graph, "_run", run)
    graph.entity_lexicon(TENANT)
    graph.entity_lexicon(TENANT)
    assert queries == [TENANT]
    graph.invalidate_lexicon(TENANT)
    graph.entity_lexicon(TENANT)
    assert queries == [TENANT, TENANT]


def test_no_linked_entity_falls_back_to_hybrid_entities(fake_chunks):
    graph = FakeGraph({})
    hits = [Hit("doc_a:0000", "doc_a", "a", 0.03)]
    _, _, calls = retrieve_graph_local(
        "q",
        TENANT,
        store=FakeStore(hits),
        graph=graph,
        conn=None,
        embedder=fake_embedder,
        reranker=lambda query, docs, top_n: [(0, 0.5)],
        llm=no_llm,
    )
    assert graph.calls == [
        ("entities_in_chunks", ["doc_a:0000"]),
        ("frontier_edges", ["co_9"]),
        ("neighbourhood", ["co_9"]),
    ]
    assert calls == 0


def test_final_context_capped_at_top_n(fake_chunks):
    limit = get_settings().RERANKER_TOP_N
    path = GraphPath(["a", "b"], ["A", "B"], ["OWNS_STAKE"], [f"doc_p:{i:04d}" for i in range(8)])
    hybrid = [Hit(f"doc_h:{i:04d}", "doc_h", f"h {i}", 0.03) for i in range(5)]
    # Overlap with a path chunk must not duplicate the candidate.
    hybrid.append(Hit("doc_p:0000", "doc_p", "text doc_p:0000", 0.03))
    seen: list[list[str]] = []

    def reranker(query, docs, top_n):
        seen.append(docs)
        return [(index, 1.0 - index / 100) for index in range(len(docs))][:top_n]

    hits, paths, _ = retrieve_graph_local(
        "A dan B",
        TENANT,
        store=FakeStore(hybrid),
        graph=FakeGraph({"a": "a", "b": "b"}, [path]),
        conn=None,
        embedder=fake_embedder,
        reranker=reranker,
        llm=no_llm,
    )
    assert paths == [path]
    assert len(seen[0]) == 13
    assert seen[0][:8] == [f"text doc_p:{i:04d}" for i in range(8)]
    assert len(hits) == limit


CHAIN = [
    edge("a", "b", ["doc_1:0000"]),
    edge("b", "c", ["doc_2:0000", "doc_2:0001"]),
    edge("d", "c", ["doc_3:0000"]),
    edge("a", "x", ["doc_x:0000"]),
    edge("c", "y", ["doc_y:0000"]),
]


def test_traversal_follows_chosen_edges_over_three_hops_and_pins_chunks(fake_chunks):
    graph = FakeGraph({"a": "a"}, edges=CHAIN)
    seen: list[list[str]] = []

    def reranker(query, docs, top_n):
        seen.append(docs)
        return [(index, 0.5) for index in range(len(docs))][:top_n]

    hits, paths, calls = retrieve_graph_local(
        "a ke mana?",
        TENANT,
        store=FakeStore([Hit("doc_h:0000", "doc_h", "h", 0.03)]),
        graph=graph,
        conn=None,
        embedder=fake_embedder,
        reranker=reranker,
        llm=scripted_llm(["B", "C", "D"], done_at=3),
    )
    assert calls == 3
    assert [hit.chunk_id for hit in hits[:4]] == [
        "doc_1:0000",
        "doc_2:0000",
        "doc_3:0000",
        "doc_2:0001",
    ]
    assert all(hit.score == 1.0 for hit in hits[:4])
    assert all("text doc_1:0000" != doc for doc in seen[0])
    assert [frontier for name, frontier in graph.calls if name == "frontier_edges"] == [
        ["a"],
        ["b"],
        ["c"],
    ]
    [path] = paths
    assert path.node_ids == ["a", "b", "c", "d"]
    assert path.node_names == ["A", "B", "C", "D"]


def test_pins_first_chunk_of_each_followed_edge_before_extra_chunks(fake_chunks):
    assert get_settings().RERANKER_TOP_N == 6
    edges = [edge("a", f"b{i}", [f"doc_b{i}:{j:04d}" for j in range(3)]) for i in range(3)]
    edges += [edge("b0", "c", ["doc_c:0000"]), edge("c", "d", ["doc_d:0000"])]
    answers = iter([["E1", "E2", "E3"], ["E1"], ["E1"]])

    def llm(messages, schema, **kwargs):
        return Hop(follow=next(answers), done=False)

    hits, _, calls = retrieve_graph_local(
        "a",
        TENANT,
        store=FakeStore([]),
        graph=FakeGraph({"a": "a"}, edges=edges),
        conn=None,
        embedder=fake_embedder,
        reranker=lambda query, docs, top_n: pytest.fail("no free slots"),
        llm=llm,
    )
    assert [hit.chunk_id for hit in hits] == [
        "doc_b0:0000",
        "doc_b1:0000",
        "doc_b2:0000",
        "doc_c:0000",
        "doc_d:0000",
        "doc_b0:0001",
    ]
    # Hop 4 offers no unfollowed edge, so no call is made.
    assert calls == 3


def test_traversal_ignores_unknown_edge_keys():
    def llm(messages, schema, **kwargs):
        return Hop(follow=["E99", "bogus", "E1", "E1"], done=True)

    steps, calls = traverse("q", TENANT, ["a"], FakeGraph({}, edges=CHAIN), llm=llm)
    assert [(step.from_id, step.to_id) for step in steps] == [("a", "b")]
    assert calls == 1


def test_gateway_error_mid_traversal_returns_partial():
    follow_b = scripted_llm(["B"])
    answers = iter([follow_b, None])

    def llm(messages, schema, **kwargs):
        script = next(answers)
        if script is None:
            raise GatewayError("down")
        return script(messages, schema, **kwargs)

    steps, calls = traverse("q", TENANT, ["a"], FakeGraph({}, edges=CHAIN), llm=llm)
    assert [(step.from_id, step.to_id) for step in steps] == [("a", "b")]
    assert calls == 2


def test_total_hits_never_exceed_top_n(fake_chunks):
    limit = get_settings().RERANKER_TOP_N
    wide = [edge("a", "b", [f"doc_w:{i:04d}" for i in range(limit + 3)])]

    def boom(query, docs, top_n):
        pytest.fail("no free slots, so the reranker must not be called")

    hybrid = [Hit(f"doc_h:{i:04d}", "doc_h", "h", 0.03) for i in range(10)]
    hits, _, _ = retrieve_graph_local(
        "a",
        TENANT,
        store=FakeStore(hybrid),
        graph=FakeGraph({"a": "a"}, edges=wide),
        conn=None,
        embedder=fake_embedder,
        reranker=boom,
        llm=scripted_llm(["B"], done_at=1),
    )
    assert len(hits) == limit
    hits, _, _ = retrieve_graph_local(
        "a",
        TENANT,
        store=FakeStore(hybrid),
        graph=FakeGraph({"a": "a"}, edges=CHAIN),
        conn=None,
        embedder=fake_embedder,
        reranker=lambda query, docs, top_n: [(i, 0.5) for i in range(len(docs))][:top_n],
        llm=scripted_llm(["B"], done_at=1),
    )
    assert len(hits) == limit
    assert hits[0].chunk_id == "doc_1:0000"


def test_retrieve_rejects_graph_modes():
    with pytest.raises(ValueError, match="orchestrator"):
        retrieve("q", "graph_local", TENANT, store=FakeStore([]), embedder=fake_embedder)


def test_rerank_pool_capped(fake_chunks):
    limit = get_settings().RERANKER_TOP_N
    path = GraphPath(["a", "b"], ["A", "B"], ["OWNS_STAKE"], [f"doc_p:{i:04d}" for i in range(40)])
    hybrid = [Hit(f"doc_h:{i:04d}", "doc_h", f"h {i}", 0.03) for i in range(5)]
    seen: list[list[str]] = []

    def reranker(query, docs, top_n):
        seen.append(docs)
        return [(index, 1.0 - index / 100) for index in range(len(docs))][:top_n]

    retrieve_graph_local(
        "A dan B",
        TENANT,
        store=FakeStore(hybrid),
        graph=FakeGraph({"a": "a", "b": "b"}, [path]),
        conn=None,
        embedder=fake_embedder,
        reranker=reranker,
        llm=no_llm,
    )
    assert len(seen[0]) == limit * RERANK_POOL_FACTOR
    # Graph-derived candidates come first, so the hybrid tail is what gets dropped.
    assert seen[0][0] == "text doc_p:0000"


def chain_graph() -> ResolvedGraph:
    def company(index: int) -> ResolvedEntity:
        chunk = f"doc_{index}:0000"
        return ResolvedEntity(
            f"co_{index}",
            "Company",
            f"Alpha {['Satu', 'Dua', 'Tiga', 'Empat'][index - 1]}",
            [],
            [Mention(chunk, f"doc_{index}", "x", "Company")],
        )

    def rel(rel_type: str, src: str, dst: str, chunks: list[str]) -> ResolvedRelation:
        return ResolvedRelation(
            rel_type,  # type: ignore[arg-type]
            src,
            dst,
            None,
            None,
            None,
            None,
            None,
            None,
            chunks,
            [chunk.split(":")[0] for chunk in chunks],
            ["q"] * len(chunks),
            [(0, 1)] * len(chunks),
        )

    return ResolvedGraph(
        entities=[company(index) for index in range(1, 5)]
        + [ResolvedEntity("se_1", "Sector", "Tambang", [], [])],
        relations=[
            rel("SUBSIDIARY_OF", "co_1", "co_2", ["doc_12:0000", "doc_12:0001"]),
            rel("SUBSIDIARY_OF", "co_2", "co_3", ["doc_23:0000"]),
            rel("SUBSIDIARY_OF", "co_3", "co_4", ["doc_34:0000", "doc_34:0001"]),
            # Sector hub would give a 2-hop shortcut co_1 -> co_4.
            rel("IN_SECTOR", "co_1", "se_1", ["doc_s:0000"]),
            rel("IN_SECTOR", "co_4", "se_1", ["doc_s:0001"]),
        ],
    )


@pytest.fixture
def graph() -> Iterator[GraphStore]:
    with GraphStore() as store:
        store.ensure_schema()
        store.write_graph(TENANT, chain_graph())
        yield store
        store.clear_tenant(TENANT)


@pytest.mark.integration
def test_paths_exclude_context_edges(graph: GraphStore):
    [path] = graph.paths_between(TENANT, ["co_1", "co_4"])
    assert path.node_ids == ["co_1", "co_2", "co_3", "co_4"]
    assert path.rel_types == ["SUBSIDIARY_OF"] * 3
    assert graph.paths_between(TENANT, ["co_1", "co_4"], max_hops=2) == []
    neighbours = graph.neighbourhood(TENANT, ["co_1"])
    assert [(n.node_ids, n.rel_types) for n in neighbours] == [
        (["co_1", "co_2"], ["SUBSIDIARY_OF"])
    ]
    offered = graph.frontier_edges(TENANT, ["co_1", "co_4"])
    assert {e.type for e in offered} == {"SUBSIDIARY_OF"}
    assert {(e.src_id, e.dst_id) for e in offered} == {("co_1", "co_2"), ("co_3", "co_4")}
    assert graph.entity_lexicon(TENANT)["alpha satu"] == "co_1"
    assert "tambang" not in graph.entity_lexicon(TENANT)


@pytest.fixture
def hub_graph() -> Iterator[GraphStore]:
    people = [ResolvedEntity(f"pe_{i}", "Person", f"Orang {i}", [], []) for i in range(63)]
    companies = [ResolvedEntity(name, "Company", name, [], []) for name in ("busy", "quiet")]

    def serves(person: str, company: str) -> ResolvedRelation:
        return ResolvedRelation(
            "SERVES_AS", person, company, "Direktur", None, None, None, 2020, None, ["d:0000"]
        )

    relations = [serves(f"pe_{i}", "busy") for i in range(60)]
    relations += [serves(f"pe_{i}", "quiet") for i in range(60, 63)]
    with GraphStore() as store:
        store.ensure_schema()
        store.write_graph(TENANT, ResolvedGraph(people + companies, relations))
        yield store
        store.clear_tenant(TENANT)


@pytest.mark.integration
def test_frontier_round_robins_entities_and_excludes_followed(hub_graph: GraphStore):
    offered = hub_graph.frontier_edges(TENANT, ["busy", "quiet"])
    assert len(offered) == 40
    quiet = [edge for edge in offered if edge.dst_id == "quiet"]
    assert len(quiet) == 3
    again = hub_graph.frontier_edges(TENANT, ["busy", "quiet"], exclude=[quiet[0].key])
    assert quiet[0].key not in {edge.key for edge in again}
    assert len([edge for edge in again if edge.dst_id == "quiet"]) == 2


@pytest.mark.integration
def test_path_provenance_chunks_returned(graph: GraphStore, fake_chunks):
    seen: list[list[str]] = []

    def reranker(query, docs, top_n):
        seen.append(docs)
        return [(index, 1.0) for index in range(len(docs))][:top_n]

    hits, [path], calls = retrieve_graph_local(
        "Apa hubungan Alpha Satu dengan Alpha Empat?",
        TENANT,
        store=FakeStore([]),
        graph=graph,
        conn=None,
        embedder=fake_embedder,
        reranker=reranker,
        llm=no_llm,
    )
    assert calls == 1
    assert path.chunk_ids == [
        "doc_12:0000",
        "doc_23:0000",
        "doc_34:0000",
        "doc_12:0001",
        "doc_34:0001",
    ]
    assert [hit.chunk_id for hit in hits][:3] == ["doc_12:0000", "doc_23:0000", "doc_34:0000"]
    assert all("doc_s" not in doc for doc in seen[0])


def test_traversal_paths_hop_direction():
    steps = [
        TraversalStep(1, "a", "b", edge("a", "b", ["c1"])),
        TraversalStep(2, "b", "c", edge("c", "b", ["c2"])),
    ]
    (path,) = traversal_paths(steps)
    assert [hop.forward for hop in path.hops] == [True, False]
