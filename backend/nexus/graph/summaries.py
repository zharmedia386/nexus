import hashlib
import json
import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Protocol

import psycopg
from pydantic import BaseModel

from nexus.db import repo
from nexus.graph.communities import Community
from nexus.graph.neo4j_store import Evidence, GraphStore
from nexus.llm import chat_json, embed
from nexus.vector.milvus_store import ChunkStore, ChunkVector

SUMMARY_PROMPT_VERSION = "v1"
SUMMARY_TIMEOUT = 300
COMMUNITY_DOC_ID = "community"

SUMMARY_SYSTEM_PROMPT = """\
You summarize one community of related entities (companies, people, groups) from a
knowledge graph about Indonesian companies. The user message lists evidence lines:
[chunk_id] source —RELATION→ target: "quote"
The quotes may be Indonesian or English.

Write in English. Keep entity names exactly as they appear in the evidence (do not
translate or anglicize Indonesian names such as "PT ... Tbk" or "Grup ...").

Output JSON with:
- title: a short title naming the community's main entities or theme.
- sentences: 3 to 8 sentences about the community's theme: who controls whom, ownership
  and subsidiary structure, board seats, investments, partnerships, family ties.
  Each sentence has "text" and "chunk_ids".

Rules:
- State only facts supported by the evidence lines. Never add outside knowledge,
  guesses, or numbers that are not in the evidence.
- Every sentence must cite at least one chunk id in chunk_ids, and every cited id must
  be copied exactly from the evidence lines. Never invent ids.
- Do not put chunk ids or brackets inside "text".
"""


class SummarySentence(BaseModel):
    text: str
    chunk_ids: list[str]


class CommunitySummary(BaseModel):
    title: str
    sentences: list[SummarySentence]


class SummaryLLM(Protocol):
    def __call__(
        self,
        messages: list[dict[str, str]],
        schema: type[CommunitySummary],
        *,
        temperature: float,
        timeout: float,
    ) -> CommunitySummary: ...


Summarizer = Callable[[list[Evidence]], tuple[CommunitySummary, int]]
Embedder = Callable[[list[str]], list[list[float]]]


def evidence_sha256(evidence: list[Evidence]) -> str:
    payload = json.dumps([asdict(item) for item in evidence], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _evidence_lines(evidence: list[Evidence]) -> str:
    return "\n".join(f'[{e.chunk_id}] {e.src} —{e.rel}→ {e.dst}: "{e.quote}"' for e in evidence)


def summarize_community(
    evidence: list[Evidence], *, llm: SummaryLLM = chat_json
) -> tuple[CommunitySummary, int]:
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": _evidence_lines(evidence)},
    ]
    raw = llm(messages, CommunitySummary, temperature=0.0, timeout=SUMMARY_TIMEOUT)
    allowed = {item.chunk_id for item in evidence}
    dropped = 0
    kept: list[SummarySentence] = []
    for sentence in raw.sentences:
        valid = [chunk_id for chunk_id in dict.fromkeys(sentence.chunk_ids) if chunk_id in allowed]
        dropped += len(sentence.chunk_ids) - len(valid)
        if valid:
            kept.append(SummarySentence(text=sentence.text, chunk_ids=valid))
    return CommunitySummary(title=raw.title, sentences=kept), dropped


def summary_text(summary: CommunitySummary) -> str:
    return " ".join(
        f"{sentence.text} {''.join(f'[{chunk_id}]' for chunk_id in sentence.chunk_ids)}"
        for sentence in summary.sentences
    )


def _embedded_text(summary: CommunitySummary) -> str:
    return "\n".join([summary.title, " ".join(s.text for s in summary.sentences)])


def _cited_ids(summary: CommunitySummary) -> list[str]:
    return sorted({chunk_id for sentence in summary.sentences for chunk_id in sentence.chunk_ids})


def _summarizable(communities: list[Community]) -> tuple[list[Community], int]:
    by_id = {community.id: community for community in communities}
    kept = [
        community
        for community in communities
        # A level-1 community identical to its parent would repeat the parent's summary.
        if not (
            community.parent_id and by_id[community.parent_id].member_ids == community.member_ids
        )
    ]
    return kept, len(communities) - len(kept)


def summarize_tenant(
    conn: psycopg.Connection,
    store: GraphStore,
    chunk_store: ChunkStore,
    tenant: str,
    *,
    summarizer: Summarizer = summarize_community,
    embedder: Embedder = embed,
    force: bool = False,
    workers: int = 4,
) -> dict[str, int]:
    counts = {
        "summarized": 0,
        "cached": 0,
        "duplicate": 0,
        "no_evidence": 0,
        "failed": 0,
        "dropped_citations": 0,
    }
    communities, counts["duplicate"] = _summarizable(store.read_communities(tenant))
    done: dict[str, CommunitySummary] = {}
    pending: list[tuple[str, list[Evidence], str]] = []
    # All Postgres access stays on this thread: psycopg connections are not thread-safe.
    for community in communities:
        evidence = store.community_evidence(tenant, community.id)
        if not evidence:
            counts["no_evidence"] += 1
            continue
        sha256 = evidence_sha256(evidence)
        cached = repo.get_summary(conn, tenant, community.id)
        if not force and cached and cached[:2] == (sha256, SUMMARY_PROMPT_VERSION):
            done[community.id] = CommunitySummary.model_validate(cached[2])
            counts["cached"] += 1
        else:
            pending.append((community.id, evidence, sha256))
    conn.rollback()
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures: dict[Future[tuple[CommunitySummary, int]], tuple[str, str]] = {
            pool.submit(summarizer, evidence): (community_id, sha256)
            for community_id, evidence, sha256 in pending
        }
        for future in as_completed(futures):
            community_id, sha256 = futures[future]
            try:
                summary, dropped = future.result()
                if not summary.sentences:
                    raise ValueError("no sentence kept a valid citation")
            except Exception as error:  # noqa: BLE001 - one bad community must not stop the run
                counts["failed"] += 1
                print(f"{community_id}: {type(error).__name__}", file=sys.stderr)
                continue
            repo.put_summary(
                conn,
                tenant,
                community_id,
                sha256,
                SUMMARY_PROMPT_VERSION,
                summary.model_dump(mode="json"),
            )
            conn.commit()
            done[community_id] = summary
            counts["summarized"] += 1
            counts["dropped_citations"] += dropped
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    _publish(store, chunk_store, embedder, tenant, done)
    return counts


def _publish(
    store: GraphStore,
    chunk_store: ChunkStore,
    embedder: Embedder,
    tenant: str,
    done: dict[str, CommunitySummary],
) -> None:
    # Summaries are looked up by community id (Postgres cache / Milvus), so duplicate (R24)
    # children are simply not searchable; their parent covers them.
    # Neo4j nodes are rebuilt by `graph communities`, so cached summaries are re-applied each run.
    for community_id, summary in done.items():
        store.write_community_summary(
            tenant, community_id, summary.title, summary_text(summary), _cited_ids(summary)
        )
    if not done:
        return
    ids = list(done)
    vectors = embedder([_embedded_text(done[community_id]) for community_id in ids])
    chunk_store.ensure()
    # Delete-then-insert is not atomic: a failure here leaves no community vectors until re-run.
    chunk_store.delete_doc(tenant, COMMUNITY_DOC_ID)
    chunk_store.upsert(
        [
            ChunkVector(
                community_id, tenant, COMMUNITY_DOC_ID, _embedded_text(done[community_id]), vector
            )
            for community_id, vector in zip(ids, vectors, strict=True)
        ]
    )
