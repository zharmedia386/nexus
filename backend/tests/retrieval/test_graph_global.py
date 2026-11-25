import pytest

from nexus.config import get_settings
from nexus.db.repo import ChunkRow
from nexus.graph.summaries import CommunitySummary, SummarySentence
from nexus.llm import GatewayError
from nexus.retrieval import graph_global
from nexus.retrieval.graph_global import MapPoint, MapResult, retrieve_graph_global
from nexus.retrieval.modes import retrieve
from nexus.vector.milvus_store import Hit

TENANT = "test_graph_global"


class FakeCommunityStore:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    def dense_search(self, tenant, vector, k):
        return [Hit(community_id, "community", "", 0.9) for community_id in self.ids][:k]


class FakeConn:
    def rollback(self):
        pass


def summary(*chunk_ids: str) -> dict:
    return CommunitySummary(
        title="t", sentences=[SummarySentence(text="s", chunk_ids=list(chunk_ids))]
    ).model_dump()


@pytest.fixture
def cached(monkeypatch):
    summaries: dict[str, dict] = {}
    monkeypatch.setattr(
        graph_global.repo,
        "get_summary",
        lambda conn, tenant, community_id: (
            ("sha", "v1", summaries[community_id]) if community_id in summaries else None
        ),
    )
    monkeypatch.setattr(
        graph_global.repo,
        "get_chunks",
        lambda conn, tenant, ids: [ChunkRow(i, i.split(":")[0], 0, 0, 1, f"text {i}") for i in ids],
    )
    return summaries


def embedder(texts):
    return [[0.0] for _ in texts]


def identity_reranker(query, docs, top_n):
    return [(index, 1.0 - 0.01 * index) for index in range(len(docs))][:top_n]


def run(llm, ids, reranker=identity_reranker):
    return retrieve_graph_global(
        "q",
        TENANT,
        community_store=FakeCommunityStore(ids),
        conn=FakeConn(),
        embedder=embedder,
        reranker=reranker,
        llm=llm,
    )


def test_map_drops_foreign_chunk_ids(cached):
    cached["c1"] = summary("a:0", "a:1")

    def llm(messages, schema, **kwargs):
        return MapResult(points=[MapPoint(text="x", chunk_ids=["a:0", "zz:9"], score=80)])

    hits, calls, used = run(llm, ["c1"])
    assert [hit.chunk_id for hit in hits] == ["a:0"]
    assert calls == 1
    assert used == ["c1"]


def test_zero_score_points_ignored(cached):
    cached["c1"] = summary("a:0", "a:1")

    def llm(messages, schema, **kwargs):
        return MapResult(
            points=[
                MapPoint(text="x", chunk_ids=["a:0"], score=0),
                MapPoint(text="y", chunk_ids=["a:1"], score=5),
            ]
        )

    hits, _, _ = run(llm, ["c1"])
    assert [hit.chunk_id for hit in hits] == ["a:1"]


def test_reduce_orders_by_score_then_reranks_to_top_n(cached, monkeypatch):
    top_n = get_settings().RERANKER_TOP_N
    ids = [f"d:{i:03d}" for i in range(top_n * 4)]
    cached["c1"] = summary(*ids)
    seen: list[list[str]] = []

    def llm(messages, schema, **kwargs):
        # Later ids score higher, so score order is the reverse of id order.
        return MapResult(
            points=[MapPoint(text=i, chunk_ids=[i], score=1 + n) for n, i in enumerate(ids)]
        )

    def recording_reranker(query, docs, n):
        seen.append(docs)
        return identity_reranker(query, docs, n)

    hits, _, _ = run(llm, ["c1"], recording_reranker)
    assert len(seen[0]) == top_n * 3
    assert seen[0][0] == f"text {ids[-1]}"
    assert len(hits) == top_n


def test_failed_map_call_is_skipped_but_counted(cached):
    cached["c1"] = summary("a:0")
    cached["c2"] = summary("b:0")

    def llm(messages, schema, **kwargs):
        if "a:0" in messages[1]["content"]:
            raise GatewayError("boom")
        return MapResult(points=[MapPoint(text="x", chunk_ids=["b:0"], score=50)])

    hits, calls, used = run(llm, ["c1", "c2"])
    assert [hit.chunk_id for hit in hits] == ["b:0"]
    assert calls == 2
    assert used == ["c2"]


def test_no_communities_returns_empty(cached):
    assert run(lambda *a, **k: None, ["missing"]) == ([], 0, [])


def test_retrieve_rejects_graph_modes():
    with pytest.raises(ValueError, match="orchestrator"):
        retrieve("q", "graph_global", TENANT, store=None)


def test_rollback_before_map_calls(cached):
    cached["c1"] = summary("a:0")
    events: list[str] = []

    class Conn:
        def rollback(self):
            events.append("rollback")

    def llm(messages, schema, **kwargs):
        events.append("map")
        return MapResult(points=[])

    retrieve_graph_global(
        "q",
        TENANT,
        community_store=FakeCommunityStore(["c1"]),
        conn=Conn(),
        embedder=embedder,
        reranker=identity_reranker,
        llm=llm,
    )
    assert events == ["rollback", "map"]
