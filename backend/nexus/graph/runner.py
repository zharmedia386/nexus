import hashlib
import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

import psycopg

from nexus.db import repo
from nexus.db.repo import ChunkRow
from nexus.graph.extract import EXTRACT_PROMPT_VERSION, extract_chunk
from nexus.graph.schema import ExtractionResult

Extractor = Callable[[str], ExtractionResult]


def _is_cached(conn: psycopg.Connection, tenant: str, chunk: ChunkRow, sha256: str) -> bool:
    cached = repo.get_extraction(conn, tenant, chunk.id)
    return cached is not None and cached[:2] == (sha256, EXTRACT_PROMPT_VERSION)


def extract_tenant(
    conn: psycopg.Connection,
    tenant: str,
    *,
    extractor: Extractor = extract_chunk,
    force: bool = False,
    workers: int = 4,
) -> dict[str, int]:
    counts = {"extracted": 0, "cached": 0, "failed": 0}
    pending: list[tuple[ChunkRow, str]] = []
    # All Postgres access stays on this thread: psycopg connections are not thread-safe.
    for chunk in repo.list_chunks(conn, tenant):
        sha256 = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
        if not force and _is_cached(conn, tenant, chunk, sha256):
            counts["cached"] += 1
        else:
            pending.append((chunk, sha256))
    # End the read transaction so the connection is not idle-in-transaction during extraction.
    conn.rollback()
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures: dict[Future[ExtractionResult], tuple[ChunkRow, str]] = {
            pool.submit(extractor, chunk.text): (chunk, sha256) for chunk, sha256 in pending
        }
        for future in as_completed(futures):
            chunk, sha256 = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - one bad chunk must not stop the run
                counts["failed"] += 1
                print(f"{chunk.id}: {type(error).__name__}", file=sys.stderr)
                continue
            repo.put_extraction(
                conn,
                tenant,
                chunk.id,
                sha256,
                EXTRACT_PROMPT_VERSION,
                result.model_dump(mode="json"),
            )
            conn.commit()
            counts["extracted"] += 1
    except BaseException:
        # Drop queued chunks (minutes each) instead of draining them on abort.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return counts


def load_extractions(conn: psycopg.Connection, tenant: str) -> dict[str, ExtractionResult]:
    # Returns stored rows regardless of sha/prompt version: stale after text changes until re-extract.
    return {
        chunk.id: ExtractionResult.model_validate(cached[2])
        for chunk in repo.list_chunks(conn, tenant)
        if (cached := repo.get_extraction(conn, tenant, chunk.id))
    }
