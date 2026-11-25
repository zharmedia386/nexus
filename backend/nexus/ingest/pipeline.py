import contextlib
import hashlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import psycopg

from nexus.config import get_settings
from nexus.datagen.writer import parse_front_matter
from nexus.db import repo
from nexus.db.repo import ChunkRow, DocumentRow
from nexus.ingest.chunker import chunk_id, chunk_text
from nexus.llm import embed
from nexus.vector.milvus_store import DOC_ID_PATTERN, ChunkStore, ChunkVector

Outcome = Literal["ingested", "skipped", "failed"]
Embedder = Callable[[list[str]], list[list[float]]]
MAX_ERROR_CHARS = 500


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def _safe_rollback(conn: psycopg.Connection) -> None:
    with contextlib.suppress(Exception):  # a dead connection must not abort the whole run
        conn.rollback()


def _mark_failed(
    conn: psycopg.Connection, store: ChunkStore, tenant: str, doc_id: str, error: Exception
) -> str:
    message = _describe(error)
    _safe_rollback(conn)
    # Each cleanup step is isolated so one failing backend cannot skip the status update.
    try:
        # Drop chunks of any previous version; committed together with the failed status below.
        repo.replace_chunks(conn, tenant, doc_id, [])
    except Exception as cleanup_error:  # noqa: BLE001
        message += f"; cleanup: {_describe(cleanup_error)}"
        _safe_rollback(conn)
    try:
        store.delete_doc(tenant, doc_id)
    except Exception as cleanup_error:  # noqa: BLE001
        message += f"; cleanup: {_describe(cleanup_error)}"
    try:
        repo.set_status(conn, tenant, doc_id, "failed", message[:MAX_ERROR_CHARS])
        conn.commit()
    except Exception:  # noqa: BLE001 - nothing left to record the failure in
        _safe_rollback(conn)
    return message


def _load_document(
    path: Path, tenant: str, conn: psycopg.Connection
) -> DocumentRow | Literal["skipped"]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    doc_id = str(meta["doc_id"])
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise ValueError(f"invalid doc_id: {doc_id!r}")
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        existing = repo.get_document(conn, tenant, doc_id)
    except Exception:
        _safe_rollback(conn)
        raise
    if existing and existing.status == "ingested" and existing.sha256 == sha256:
        return "skipped"
    # Stored content is the body: chunk offsets index into it for evidence highlighting.
    return DocumentRow(
        doc_id,
        str(meta["title"]),
        str(meta["doc_type"]),
        str(meta["lang"]),
        int(meta["year"]),
        body,
        sha256,
    )


def _ingest(
    path: Path,
    tenant: str,
    *,
    conn: psycopg.Connection,
    store: ChunkStore,
    embedder: Embedder = embed,
) -> tuple[Outcome, str | None]:
    # Malformed files fail here, before any write, so they never touch an existing doc's rows.
    try:
        document = _load_document(path, tenant, conn)
    except Exception as error:  # noqa: BLE001 - reported per document by the caller
        return "failed", _describe(error)
    if document == "skipped":
        return "skipped", None
    try:
        # Committed first so a later failure has a row to mark as failed.
        repo.upsert_document(conn, tenant, document)
        conn.commit()
        chunks = chunk_text(document.content)
        vectors = embedder([chunk.text for chunk in chunks])
        chunk_rows = [
            ChunkRow(
                chunk_id(document.id, c.ordinal), document.id, c.ordinal, c.start, c.end, c.text
            )
            for c in chunks
        ]
        repo.replace_chunks(conn, tenant, document.id, chunk_rows)
        repo.set_status(conn, tenant, document.id, "ingested")
        store.delete_doc(tenant, document.id)
        store.upsert(
            [
                ChunkVector(row.id, tenant, document.id, row.text, vec)
                for row, vec in zip(chunk_rows, vectors, strict=True)
            ]
        )
        conn.commit()
        return "ingested", None
    except Exception as error:  # noqa: BLE001 - any failure is recorded per document
        return "failed", _mark_failed(conn, store, tenant, document.id, error)


def ingest_document(
    path: Path,
    tenant: str,
    *,
    conn: psycopg.Connection,
    store: ChunkStore,
    embedder: Embedder = embed,
) -> Outcome:
    return _ingest(path, tenant, conn=conn, store=store, embedder=embedder)[0]


def ingest_dir(directory: Path, tenant: str, embedder: Embedder = embed) -> dict[str, int]:
    counts = {"ingested": 0, "skipped": 0, "failed": 0}
    store = ChunkStore(get_settings().collection("chunks"))
    store.ensure()
    with repo.connect() as conn:
        repo.ensure_tenant(conn, tenant)
        conn.commit()
        for path in sorted(directory.glob("*.md")):
            outcome, reason = _ingest(path, tenant, conn=conn, store=store, embedder=embedder)
            counts[outcome] += 1
            if reason:
                print(f"{path.name}: {reason}", file=sys.stderr)
    return counts
