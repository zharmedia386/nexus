from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import psycopg
from pydantic import BaseModel

from nexus.config import get_settings
from nexus.db import repo
from nexus.graph.summaries import CommunitySummary
from nexus.llm import GatewayError, chat_json
from nexus.retrieval.modes import RERANK_POOL_FACTOR, Reranker, rerank_hits
from nexus.vector.milvus_store import ChunkStore, Hit

MAP_TIMEOUT = 300
MAP_WORKERS = 4
MAP_SYSTEM = (
    "You answer a question using one summary of a community of related entities from a "
    "knowledge graph. The summary is a list of numbered sentences, each followed by the "
    "chunk ids that support it. Return the points of the summary that help answer the "
    "question. Each point has: text (one short statement), chunk_ids (copied exactly from "
    "the summary's chunk ids, only those supporting the point) and score (integer 0-100, "
    "how much the point helps answer the question; 0 if it does not help). Return an empty "
    "points list if the summary is irrelevant. Never invent chunk ids."
)


class MapPoint(BaseModel):
    text: str
    chunk_ids: list[str]
    score: int


class MapResult(BaseModel):
    points: list[MapPoint]


def _summary_prompt(question: str, summary: CommunitySummary) -> list[dict[str, str]]:
    lines = "\n".join(
        f"{number}. {sentence.text} [{', '.join(sentence.chunk_ids)}]"
        for number, sentence in enumerate(summary.sentences, 1)
    )
    return [
        {"role": "system", "content": MAP_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nSummary: {summary.title}\n{lines}"},
    ]


def map_community(
    question: str, summary: CommunitySummary, llm: Callable[..., MapResult]
) -> list[MapPoint] | None:
    # None marks a failed call so the caller can tell it from an irrelevant community.
    allowed = {chunk for sentence in summary.sentences for chunk in sentence.chunk_ids}
    try:
        result = llm(
            _summary_prompt(question, summary), MapResult, temperature=0.0, timeout=MAP_TIMEOUT
        )
    except GatewayError:
        return None
    return [
        MapPoint(text=point.text, chunk_ids=ids, score=point.score)
        for point in result.points
        if point.score > 0 and (ids := [c for c in dict.fromkeys(point.chunk_ids) if c in allowed])
    ]


def retrieve_graph_global(
    question: str,
    tenant: str,
    *,
    community_store: ChunkStore,
    conn: psycopg.Connection,
    embedder: Callable[[list[str]], list[list[float]]],
    reranker: Reranker,
    llm: Callable[..., MapResult] = chat_json,
    top_communities: int = 8,
) -> tuple[list[Hit], int, list[str]]:
    limit = get_settings().RERANKER_TOP_N
    vector = embedder([question])[0]
    summaries: list[CommunitySummary] = []
    community_ids: list[str] = []
    for hit in community_store.dense_search(tenant, vector, top_communities):
        cached = repo.get_summary(conn, tenant, hit.chunk_id)
        if cached:
            summaries.append(CommunitySummary.model_validate(cached[2]))
            community_ids.append(hit.chunk_id)
    # Release the read transaction before the long LLM map calls.
    conn.rollback()
    if not summaries:
        return [], 0, []
    # LLM calls run in workers; all Postgres access stays on this thread.
    with ThreadPoolExecutor(max_workers=MAP_WORKERS) as pool:
        mapped = list(pool.map(lambda summary: map_community(question, summary, llm), summaries))
    ranked = sorted(
        (
            (-point.score, rank, chunk)
            for rank, points in enumerate(mapped)
            for point in points or []
            for chunk in point.chunk_ids
        )
    )
    chunk_ids = list(dict.fromkeys(chunk for _, _, chunk in ranked))[: limit * RERANK_POOL_FACTOR]
    rows = {row.id: row for row in repo.get_chunks(conn, tenant, chunk_ids)} if chunk_ids else {}
    # Ids absent from Postgres are dropped, so every hit is real evidence.
    candidates = [
        Hit(rows[chunk].id, rows[chunk].doc_id, rows[chunk].text, 0.0)
        for chunk in chunk_ids
        if chunk in rows
    ]
    used = [community_ids[rank] for rank, points in enumerate(mapped) if points]
    return rerank_hits(question, candidates, reranker), len(summaries), used
