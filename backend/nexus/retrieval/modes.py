from collections.abc import Callable
from typing import Literal, get_args

from nexus.config import get_settings
from nexus.llm import embed, rerank
from nexus.vector.milvus_store import ChunkStore, Hit

Mode = Literal["rag", "hybrid", "graph_local", "graph_global", "auto"]
MODES: tuple[str, ...] = get_args(Mode)
Reranker = Callable[[str, list[str], int], list[tuple[int, float]]]
RERANK_POOL_FACTOR = 3


def retrieve(
    question: str,
    mode: Mode,
    tenant: str,
    *,
    store: ChunkStore,
    embedder: Callable[[list[str]], list[list[float]]] = embed,
    reranker: Reranker = rerank,
) -> list[Hit]:
    # "auto" is routed by the orchestrator before retrieval.
    if mode not in MODES or mode == "auto":
        raise ValueError(f"unknown mode: {mode!r}")
    if mode in ("graph_local", "graph_global"):
        raise ValueError("graph modes run via the orchestrator")
    settings = get_settings()
    vector = embedder([question])[0]
    if mode == "rag":
        hits = store.dense_search(tenant, vector, settings.RETRIEVAL_TOP_K)
        kept = [hit for hit in hits if hit.score >= settings.SIMILARITY_THRESHOLD]
        return kept[: settings.RERANKER_TOP_N]
    hits = store.hybrid_search(tenant, question, vector, settings.RETRIEVAL_TOP_K)
    return rerank_hits(question, hits, reranker)


def rerank_hits(question: str, hits: list[Hit], reranker: Reranker) -> list[Hit]:
    settings = get_settings()
    if not settings.RERANKER_ENABLED:
        # RRF scores are not on the cosine scale, so the similarity threshold is skipped.
        return hits[: settings.RERANKER_TOP_N]
    if not hits:
        return []
    ranked = reranker(question, [hit.text for hit in hits], settings.RERANKER_TOP_N)
    # Rerank scores are not on the cosine scale; abstention is left to the answer prompt.
    return [
        Hit(hits[index].chunk_id, hits[index].doc_id, hits[index].text, score)
        for index, score in ranked
        if 0 <= index < len(hits)
    ][: settings.RERANKER_TOP_N]
