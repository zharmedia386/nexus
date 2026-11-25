from pathlib import Path
from typing import Self
from uuid import uuid4

import pytest

from nexus.db import repo
from nexus.db.repo import ChunkRow, DocumentRow
from nexus.ingest import pipeline
from nexus.ingest.pipeline import ingest_dir, ingest_document
from nexus.llm import GatewayError
from nexus.vector.milvus_store import ChunkStore, ChunkVector


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def commit(self) -> None:
        self.calls.append("commit")

    def rollback(self) -> None:
        self.calls.append("rollback")


class FakeCtx(FakeConn):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[str, ChunkVector] = {}

    def delete_doc(self, tenant: str, doc_id: str) -> None:
        self.rows = {k: v for k, v in self.rows.items() if v.doc_id != doc_id}

    def upsert(self, rows: list[ChunkVector]) -> None:
        self.rows.update({row.chunk_id: row for row in rows})


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, DocumentRow], dict[str, list[ChunkRow]]]:
    documents: dict[str, DocumentRow] = {}
    chunks: dict[str, list[ChunkRow]] = {}

    def set_status(conn, tenant, doc_id, status, error=None) -> None:
        documents[doc_id] = DocumentRow(
            **{**documents[doc_id].__dict__, "status": status, "error": error}
        )

    monkeypatch.setattr(repo, "get_document", lambda conn, tenant, doc_id: documents.get(doc_id))
    monkeypatch.setattr(
        repo, "upsert_document", lambda conn, tenant, doc: documents.update({doc.id: doc})
    )

    def replace_chunks(conn, tenant, doc_id, rows) -> None:
        conn.calls.append(f"replace:{len(rows)}")
        chunks.update({doc_id: rows})

    monkeypatch.setattr(repo, "replace_chunks", replace_chunks)
    monkeypatch.setattr(repo, "set_status", set_status)
    return documents, chunks


def write_doc(directory: Path, body: str) -> Path:
    path = directory / "doc-1.md"
    path.write_text(
        f'---\ndoc_id: doc-1\ndoc_type: news\nlang: en\nyear: 2024\ntitle: "T"\n---\n\n{body}\n',
        encoding="utf-8",
    )
    return path


def fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * 3 for _ in texts]


def run(path: Path, store: FakeStore, embedder=fake_embed) -> str:
    return ingest_document(path, "demo", conn=FakeConn(), store=store, embedder=embedder)  # type: ignore[arg-type]


def test_reingest_same_hash_skips(tmp_path: Path, db) -> None:
    path, store = write_doc(tmp_path, "Alpha beta."), FakeStore()
    assert run(path, store) == "ingested"
    calls: list[int] = []

    def counting(texts: list[str]) -> list[list[float]]:
        calls.append(len(texts))
        return fake_embed(texts)

    assert run(path, store, counting) == "skipped"
    assert calls == []


def test_changed_content_replaces_chunks(tmp_path: Path, db) -> None:
    documents, chunks = db
    store = FakeStore()
    assert run(write_doc(tmp_path, "Alpha beta."), store) == "ingested"
    assert run(write_doc(tmp_path, "Gamma delta."), store) == "ingested"
    assert [chunk.text for chunk in chunks["doc-1"]] == ["Gamma delta."]
    assert [row.text for row in store.rows.values()] == ["Gamma delta."]
    assert documents["doc-1"].content == "Gamma delta.\n"


def test_embed_failure_leaves_no_partial_chunks(tmp_path: Path, db) -> None:
    documents, chunks = db
    store = FakeStore()
    assert run(write_doc(tmp_path, "Old text."), store) == "ingested"
    assert len(chunks["doc-1"]) == 1 and len(store.rows) == 1
    path = write_doc(tmp_path, "Alpha beta.")

    def broken(texts: list[str]) -> list[list[float]]:
        raise GatewayError("boom")

    assert run(path, store, broken) == "failed"
    assert chunks.get("doc-1", []) == [] and store.rows == {}
    assert documents["doc-1"].status == "failed" and "boom" in (documents["doc-1"].error or "")
    assert run(path, store) == "ingested"
    assert documents["doc-1"].status == "ingested" and len(store.rows) == 1


@pytest.mark.integration
def test_ingest_three_docs_end_to_end(tmp_path: Path) -> None:
    tenant = "nexus_test_ingest"
    for index in range(3):
        (tmp_path / f"d{index}.md").write_text(
            f'---\ndoc_id: d{index}\ndoc_type: news\nlang: en\nyear: 2024\ntitle: "T{index}"\n---\n\n'
            f"Document {index} about PT Contoh Tbk and its board.\n",
            encoding="utf-8",
        )
    store = ChunkStore(f"nexus_test_chunks_{uuid4().hex}")
    store.ensure()
    try:
        with repo.connect() as conn:
            repo.migrate(conn)
            repo.ensure_tenant(conn, tenant)
            conn.commit()
            try:
                outcomes = [
                    ingest_document(p, tenant, conn=conn, store=store)
                    for p in sorted(tmp_path.glob("*.md"))
                ]
                assert outcomes == ["ingested"] * 3
                assert repo.get_document(conn, tenant, "d0").status == "ingested"
                assert [
                    ingest_document(p, tenant, conn=conn, store=store)
                    for p in tmp_path.glob("*.md")
                ] == ["skipped"] * 3
            finally:
                conn.rollback()
                conn.execute("DELETE FROM chunks WHERE tenant_id = %s", (tenant,))
                conn.execute("DELETE FROM documents WHERE tenant_id = %s", (tenant,))
                conn.execute("DELETE FROM tenants WHERE id = %s", (tenant,))
                conn.commit()
    finally:
        store.drop()


def test_cleanup_error_still_marks_failed_and_next_doc_runs(
    tmp_path: Path, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents, _ = db
    store = FakeStore()

    def broken_embed(texts: list[str]) -> list[list[float]]:
        raise GatewayError("boom")

    def broken_delete(tenant: str, doc_id: str) -> None:
        raise ConnectionError("milvus down")

    monkeypatch.setattr(store, "delete_doc", broken_delete)
    assert run(write_doc(tmp_path, "Alpha."), store, broken_embed) == "failed"
    assert documents["doc-1"].status == "failed"
    assert "boom" in documents["doc-1"].error and "milvus down" in documents["doc-1"].error


def test_malformed_duplicate_leaves_healthy_doc_untouched(tmp_path: Path, db) -> None:
    documents, chunks = db
    store = FakeStore()
    assert run(write_doc(tmp_path, "Healthy text."), store) == "ingested"
    bad = tmp_path / "dup.md"
    bad.write_text("---\ndoc_id: doc-1\ndoc_type: news\nlang: en\nyear: abc\n---\n\nX\n")
    assert run(bad, store) == "failed"
    assert documents["doc-1"].status == "ingested"
    assert len(chunks["doc-1"]) == 1 and len(store.rows) == 1


def test_invalid_doc_id_fails_without_writes(tmp_path: Path, db) -> None:
    documents, _ = db
    path = tmp_path / "x.md"
    path.write_text(
        '---\ndoc_id: bad id!\ndoc_type: news\nlang: en\nyear: 2024\ntitle: "T"\n---\n\nX\n'
    )
    assert run(path, FakeStore()) == "failed"
    assert documents == {}


def test_ingest_dir_counts_mixed_outcomes(
    tmp_path: Path, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FakeStore()
    monkeypatch.setattr(pipeline, "ChunkStore", lambda name: store)
    store.ensure = lambda: None  # type: ignore[attr-defined]

    monkeypatch.setattr(repo, "connect", lambda: FakeCtx())
    tenants: list[str] = []
    monkeypatch.setattr(repo, "ensure_tenant", lambda conn, tenant: tenants.append(tenant))
    write_doc(tmp_path, "Alpha.")
    (tmp_path / "bad.md").write_text("no front matter")
    assert ingest_dir(tmp_path, "demo", fake_embed) == {"ingested": 1, "skipped": 0, "failed": 1}
    assert ingest_dir(tmp_path, "demo", fake_embed) == {"ingested": 0, "skipped": 1, "failed": 1}
    assert tenants == ["demo", "demo"]


def test_failure_commits_chunk_delete_after_rollback(tmp_path: Path, db) -> None:
    store, conn = FakeStore(), FakeConn()
    path = write_doc(tmp_path, "Alpha.")
    assert ingest_document(path, "demo", conn=conn, store=store, embedder=fake_embed) == "ingested"  # type: ignore[arg-type]
    conn.calls.clear()

    def broken(texts: list[str]) -> list[list[float]]:
        raise GatewayError("boom")

    write_doc(tmp_path, "Changed.")
    assert ingest_document(path, "demo", conn=conn, store=store, embedder=broken) == "failed"  # type: ignore[arg-type]
    failure = conn.calls[conn.calls.index("rollback") :]
    assert failure == ["rollback", "replace:0", "commit"]


def test_ingest_dir_reports_failure_reasons(
    tmp_path: Path, db, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = FakeStore()
    monkeypatch.setattr(pipeline, "ChunkStore", lambda name: store)
    store.ensure = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setattr(repo, "connect", lambda: FakeCtx())
    monkeypatch.setattr(repo, "ensure_tenant", lambda conn, tenant: None)
    (tmp_path / "bad.md").write_text("no front matter")

    def broken(texts: list[str]) -> list[list[float]]:
        raise GatewayError("boom")

    write_doc(tmp_path, "Alpha.")
    assert ingest_dir(tmp_path, "demo", broken)["failed"] == 2
    err = capsys.readouterr().err
    assert "bad.md: ValueError: missing front matter" in err
    assert "doc-1.md: GatewayError: boom" in err
