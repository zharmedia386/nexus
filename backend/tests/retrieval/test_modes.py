import pytest

from nexus.config import get_settings
from nexus.retrieval.modes import retrieve
from nexus.vector.milvus_store import Hit


def make_hits(scores: list[float]) -> list[Hit]:
    return [Hit(f"doc_a:{i:04d}", "doc_a", f"text {i}", score) for i, score in enumerate(scores)]


class FakeStore:
    def __init__(self, hits: list[Hit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def dense_search(self, tenant, vector, k):
        self.calls.append(("dense", k))
        return self.hits

    def hybrid_search(self, tenant, query_text, vector, k):
        self.calls.append(("hybrid", k))
        return self.hits


def fake_embedder(texts):
    return [[0.0] for _ in texts]


def reverse_reranker(query, docs, top_n):
    # Highest relevance to the last doc, so order visibly changes.
    ranked = [(index, 0.9 - 0.05 * rank) for rank, index in enumerate(reversed(range(len(docs))))]
    return ranked[:top_n]


def test_rag_applies_threshold_and_top_n():
    settings = get_settings()
    scores = [0.9] * 8 + [0.1] * 2
    store = FakeStore(make_hits(scores))
    hits = retrieve("q", "rag", "demo", store=store, embedder=fake_embedder)
    assert store.calls == [("dense", settings.RETRIEVAL_TOP_K)]
    assert len(hits) == settings.RERANKER_TOP_N
    assert all(hit.score >= settings.SIMILARITY_THRESHOLD for hit in hits)
    assert (
        retrieve("q", "rag", "demo", store=FakeStore(make_hits([0.1, 0.2])), embedder=fake_embedder)
        == []
    )


def test_hybrid_reranks_to_top_n():
    settings = get_settings()
    store = FakeStore(make_hits([0.03] * 10))
    hits = retrieve(
        "q", "hybrid", "demo", store=store, embedder=fake_embedder, reranker=reverse_reranker
    )
    assert store.calls == [("hybrid", settings.RETRIEVAL_TOP_K)]
    assert len(hits) == settings.RERANKER_TOP_N
    assert hits[0].chunk_id == "doc_a:0009"
    assert hits[0].score == pytest.approx(0.9)


def test_hybrid_keeps_low_rerank_scores_in_rerank_order():
    def low_reranker(query, docs, top_n):
        return [(1, 0.8), (0, 0.2)]

    store = FakeStore(make_hits([0.03] * 3))
    hits = retrieve(
        "q", "hybrid", "demo", store=store, embedder=fake_embedder, reranker=low_reranker
    )
    assert [hit.chunk_id for hit in hits] == ["doc_a:0001", "doc_a:0000"]


def test_hybrid_without_reranker_skips_threshold(monkeypatch):
    monkeypatch.setenv("RERANKER_ENABLED", "false")
    get_settings.cache_clear()
    try:

        def boom(query, docs, top_n):
            pytest.fail("reranker must not be called")

        store = FakeStore(make_hits([0.03] * 10))
        hits = retrieve("q", "hybrid", "demo", store=store, embedder=fake_embedder, reranker=boom)
        assert [hit.chunk_id for hit in hits] == [f"doc_a:{i:04d}" for i in range(6)]
    finally:
        get_settings.cache_clear()


def test_same_final_context_size_both_modes():
    limit = get_settings().RERANKER_TOP_N
    store = FakeStore(make_hits([0.9] * 10))
    for mode in ("rag", "hybrid"):
        hits = retrieve(
            "q", mode, "demo", store=store, embedder=fake_embedder, reranker=reverse_reranker
        )
        assert len(hits) <= limit


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        retrieve("q", "graph", "demo", store=FakeStore([]), embedder=fake_embedder)


def test_hybrid_ignores_out_of_range_rerank_indices_and_empty_hits():
    def wild_reranker(query, docs, top_n):
        return [(99, 0.9), (-1, 0.9), (1, 0.8)]

    store = FakeStore(make_hits([0.03] * 3))
    hits = retrieve(
        "q", "hybrid", "demo", store=store, embedder=fake_embedder, reranker=wild_reranker
    )
    assert [hit.chunk_id for hit in hits] == ["doc_a:0001"]
    assert retrieve("q", "hybrid", "demo", store=FakeStore([]), embedder=fake_embedder) == []
