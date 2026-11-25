from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from nexus.graph.communities import Community
from nexus.graph.neo4j_store import Evidence, GraphStore, cap_evidence
from nexus.graph.summaries import (
    SUMMARY_PROMPT_VERSION,
    CommunitySummary,
    SummarySentence,
    evidence_sha256,
    summarize_community,
    summarize_tenant,
)

TENANT = "test_graph_summ"
EVIDENCE = [
    Evidence("d:0", "Budi", "OWNS_STAKE", "BRMN", "Budi owns 12.5%"),
    Evidence("d:1", "Siti", "SERVES_AS", "BRMN", "Siti is director"),
]


def fake_llm(summary: CommunitySummary):
    def llm(messages, schema, *, temperature, timeout):
        assert (temperature, timeout) == (0.0, 300)
        return summary

    return llm


def test_summary_drops_foreign_citations():
    raw = CommunitySummary(
        title="T",
        sentences=[SummarySentence(text="A.", chunk_ids=["d:0", "zzz", "d:0"])],
    )
    summary, dropped = summarize_community(EVIDENCE, llm=fake_llm(raw))
    assert summary.sentences == [SummarySentence(text="A.", chunk_ids=["d:0"])]
    assert dropped == 2


def test_sentence_without_valid_citation_dropped():
    raw = CommunitySummary(
        title="T",
        sentences=[
            SummarySentence(text="A.", chunk_ids=["d:1"]),
            SummarySentence(text="B.", chunk_ids=["zzz"]),
            SummarySentence(text="C.", chunk_ids=[]),
        ],
    )
    summary, dropped = summarize_community(EVIDENCE, llm=fake_llm(raw))
    assert [s.text for s in summary.sentences] == ["A."]
    assert dropped == 1


def test_prompt_lists_evidence_lines():
    seen: list[str] = []

    def llm(messages, schema, *, temperature, timeout):
        seen.append(messages[1]["content"])
        return CommunitySummary(title="T", sentences=[])

    summarize_community(EVIDENCE, llm=llm)
    assert seen == [
        (
            '[d:0] Budi —OWNS_STAKE→ BRMN: "Budi owns 12.5%"\n'
            '[d:1] Siti —SERVES_AS→ BRMN: "Siti is director"'
        )
    ]


class FakeGraph:
    def __init__(self, communities: list[Community], evidence: list[Evidence]) -> None:
        self.communities = communities
        self.evidence = evidence
        self.written: dict[str, tuple[str, str, list[str]]] = {}

    def read_communities(self, tenant: str) -> list[Community]:
        return self.communities

    def community_evidence(self, tenant: str, community_id: str, limit: int = 60):
        return self.evidence

    def write_community_summary(self, tenant, community_id, title, summary, chunk_ids) -> None:
        self.written[community_id] = (title, summary, chunk_ids)


@dataclass
class FakeChunkStore:
    rows: list | None = None

    def ensure(self) -> None: ...

    def delete_doc(self, tenant: str, doc_id: str) -> None: ...

    def upsert(self, rows: list) -> None:
        self.rows = rows


class Conn:
    def rollback(self) -> None: ...

    def commit(self) -> None: ...


@pytest.fixture
def cache(monkeypatch):
    saved: dict[str, tuple[str, str, dict]] = {}
    monkeypatch.setattr(
        "nexus.graph.summaries.repo.get_summary", lambda conn, tenant, cid: saved.get(cid)
    )

    def put(conn, tenant, cid, sha, version, payload) -> None:
        saved[cid] = (sha, version, payload)

    monkeypatch.setattr("nexus.graph.summaries.repo.put_summary", put)
    return saved


def embedder(texts: list[str]) -> list[list[float]]:
    return [[0.0] for _ in texts]


def run(graph: FakeGraph, chunk_store: FakeChunkStore, calls: list, **kwargs):
    def summarizer(evidence: list[Evidence]):
        calls.append(evidence)
        sentence = SummarySentence(text="Budi owns BRMN.", chunk_ids=["d:0"])
        return CommunitySummary(title="Title", sentences=[sentence]), 1

    return summarize_tenant(
        Conn(),
        graph,
        chunk_store,
        TENANT,
        summarizer=summarizer,
        embedder=embedder,
        **kwargs,  # type: ignore[arg-type]
    )


COMMUNITIES = [
    Community("c0_0", 0, None, ["a", "b", "c"]),
    Community("c1_0", 1, "c0_0", ["a", "b", "c"]),
    Community("c1_1", 1, "c0_0", ["a", "b"]),
]


def test_cached_summary_skips_llm(cache):
    graph, chunk_store, calls = FakeGraph(COMMUNITIES, EVIDENCE), FakeChunkStore(), []
    first = run(graph, chunk_store, calls)
    second = run(graph, chunk_store, calls)
    assert first == {
        "summarized": 2,
        "cached": 0,
        "duplicate": 1,
        "no_evidence": 0,
        "failed": 0,
        "dropped_citations": 2,
    }
    assert second == {
        "summarized": 0,
        "cached": 2,
        "duplicate": 1,
        "no_evidence": 0,
        "failed": 0,
        "dropped_citations": 0,
    }
    assert len(calls) == 2
    assert graph.written["c0_0"] == ("Title", "Budi owns BRMN. [d:0]", ["d:0"])
    assert "c1_0" not in graph.written
    assert cache["c0_0"][:2] == (evidence_sha256(EVIDENCE), SUMMARY_PROMPT_VERSION)


def test_changed_evidence_resummarizes(cache):
    graph, chunk_store, calls = FakeGraph(COMMUNITIES[:1], EVIDENCE), FakeChunkStore(), []
    run(graph, chunk_store, calls)
    graph.evidence = EVIDENCE[:1]
    assert run(graph, chunk_store, calls)["summarized"] == 1


def test_milvus_row_uses_community_ids_and_plain_text(cache):
    graph, chunk_store = FakeGraph(COMMUNITIES[:1], EVIDENCE), FakeChunkStore()
    run(graph, chunk_store, [])
    (row,) = chunk_store.rows
    assert (row.chunk_id, row.doc_id, row.tenant_id) == ("c0_0", "community", TENANT)
    assert row.text == "Title\nBudi owns BRMN."


def test_failure_counted_and_empty_evidence_skipped(cache, capsys):
    graph = FakeGraph(COMMUNITIES[:1], EVIDENCE)

    def failing(evidence):
        raise RuntimeError("boom")

    counts = summarize_tenant(
        Conn(),
        graph,
        FakeChunkStore(),
        TENANT,
        summarizer=failing,
        embedder=embedder,  # type: ignore[arg-type]
    )
    assert counts["failed"] == 1 and not graph.written
    assert capsys.readouterr().err == "c0_0: RuntimeError\n"
    graph.evidence = []
    assert run(graph, FakeChunkStore(), [])["no_evidence"] == 1


@pytest.fixture
def store() -> Iterator[GraphStore]:
    with GraphStore() as graph_store:
        graph_store.ensure_schema()
        graph_store.clear_tenant(TENANT)
        yield graph_store
        graph_store.clear_tenant(TENANT)
        graph_store._run("MATCH (c:Community {tenant_id: $t}) DETACH DELETE c", t=TENANT)


def seed(store: GraphStore) -> None:
    store._run(
        "UNWIND ['a','b','c','z'] AS id CREATE (:Entity:Company {tenant_id: $t, id: id, name: id})",
        t=TENANT,
    )
    for rel, src, dst, chunk_ids, quotes in (
        ("SUBSIDIARY_OF", "b", "a", ["d:2", "d:1"], ["q2", "q1"]),
        ("OWNS_STAKE", "a", "b", ["d:0"], ["q0"]),
        ("IN_SECTOR", "a", "b", ["d:9"], ["ctx"]),
        ("OWNS_STAKE", "a", "z", ["d:7"], ["outside"]),
    ):
        store._run(
            f"MATCH (x:Entity {{tenant_id: $t, id: $s}}), (y:Entity {{tenant_id: $t, id: $d}}) "
            f"CREATE (x)-[:{rel} {{tenant_id: $t, chunk_ids: $c, quotes: $q}}]->(y)",
            t=TENANT, s=src, d=dst, c=chunk_ids, q=quotes,
        )  # fmt: skip


@pytest.mark.integration
def test_community_evidence_reads_provenance(store: GraphStore):
    seed(store)
    store.write_communities(TENANT, [Community("c0_0", 0, None, ["a", "b", "c"])])
    assert store.read_communities(TENANT) == [Community("c0_0", 0, None, ["a", "b", "c"])]
    expected = [
        Evidence("d:0", "a", "OWNS_STAKE", "b", "q0"),
        Evidence("d:1", "b", "SUBSIDIARY_OF", "a", "q1"),
        Evidence("d:2", "b", "SUBSIDIARY_OF", "a", "q2"),
    ]
    assert store.community_evidence(TENANT, "c0_0") == expected
    assert store.community_evidence(TENANT, "c0_0", limit=2) == expected[:2]
    store.write_community_summary(TENANT, "c0_0", "T", "S [d:0]", ["d:0"])
    row = store._run(
        "MATCH (c:Community {tenant_id: $t, id: 'c0_0'}) "
        "RETURN c.title AS title, c.summary AS summary, c.summary_chunk_ids AS ids",
        t=TENANT,
    )
    assert row == [{"title": "T", "summary": "S [d:0]", "ids": ["d:0"]}]


def test_evidence_order_deterministic():
    shuffled = list(reversed(EVIDENCE))
    assert evidence_sha256(EVIDENCE) == evidence_sha256(list(EVIDENCE))
    assert evidence_sha256(shuffled) != evidence_sha256(EVIDENCE)


def test_cap_keeps_every_rel_type_deterministically():
    sizes = {"INVESTED_IN": 5, "OWNS_STAKE": 45, "SERVES_AS": 16, "SUBSIDIARY_OF": 10}
    found = [
        Evidence(f"d:{rel}:{n}", f"s{n}", rel, f"t{n}", "q")
        for rel, k in sizes.items()
        for n in range(k)
    ]
    capped = cap_evidence(found, 60)
    assert len(capped) == 60
    assert {e.rel for e in capped} == set(sizes)
    assert capped == cap_evidence(list(reversed(found)), 60)
    assert sum(e.rel == "SUBSIDIARY_OF" for e in capped) == 10
