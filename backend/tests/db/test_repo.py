import re
from dataclasses import fields

import psycopg
import pytest

from nexus.db import repo
from nexus.db.repo import ChunkRow, DocumentRow

TABLES = ["tenants", "documents", "chunks", "eval_runs", "eval_results"]


def make_doc(doc_id: str = "d1") -> DocumentRow:
    return DocumentRow(doc_id, "Title", "news", "id", 2024, "body", "abc")


def make_chunk(chunk_id: str, doc_id: str = "d1", ordinal: int = 0) -> ChunkRow:
    return ChunkRow(chunk_id, doc_id, ordinal, 0, 4, "body")


def test_migration_declares_every_table_and_seed():
    sql = repo.migration_sql()
    for table in TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} " in sql
    assert "'demo'" in sql and "ON CONFLICT DO NOTHING" in sql


def test_migrations_listed_in_order():
    names = [path.name for path in repo.migration_files()]
    assert names == [
        "001_init.sql",
        "002_extractions.sql",
        "003_adjudications.sql",
        "004_community_summaries.sql",
    ]
    for path in repo.migration_files():
        statements = [part for part in path.read_text("utf-8").split(";") if part.strip()]
        assert all(
            "IF NOT EXISTS" in statement or "ON CONFLICT" in statement for statement in statements
        )


def test_row_fields_match_sql_columns():
    sql = repo.migration_sql()
    for table, row_type in (("documents", DocumentRow), ("chunks", ChunkRow)):
        body = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", sql, re.DOTALL).group(
            1
        )
        columns = [
            line.split()[0]
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith(("PRIMARY", "FOREIGN"))
        ]
        expected = [field.name for field in fields(row_type)]
        # tenant_id is bound separately by the repo functions
        assert [name for name in columns if name != "tenant_id"] == expected


TENANT_A = "test_a"
TENANT_B = "test_b"
TEST_TENANTS = [TENANT_A, TENANT_B]


def purge_test_tenants(connection: psycopg.Connection) -> None:
    connection.execute(
        "DELETE FROM eval_results WHERE run_id IN "
        "(SELECT id FROM eval_runs WHERE tenant_id = ANY(%s))",
        (TEST_TENANTS,),
    )
    connection.execute("DELETE FROM eval_runs WHERE tenant_id = ANY(%s)", (TEST_TENANTS,))
    connection.execute("DELETE FROM community_summaries WHERE tenant_id = ANY(%s)", (TEST_TENANTS,))
    connection.execute("DELETE FROM adjudications WHERE tenant_id = ANY(%s)", (TEST_TENANTS,))
    connection.execute("DELETE FROM chunks WHERE tenant_id = ANY(%s)", (TEST_TENANTS,))
    connection.execute("DELETE FROM documents WHERE tenant_id = ANY(%s)", (TEST_TENANTS,))


@pytest.fixture
def conn():
    connection = repo.connect()
    repo.migrate(connection)
    for tenant in TEST_TENANTS:
        connection.execute("INSERT INTO tenants (id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant,))
    purge_test_tenants(connection)
    connection.commit()
    yield connection
    connection.rollback()
    purge_test_tenants(connection)
    connection.commit()
    connection.close()


@pytest.mark.integration
def test_migrate_idempotent(conn: psycopg.Connection):
    repo.migrate(conn)
    repo.migrate(conn)
    assert conn.execute("SELECT count(*) FROM tenants WHERE id = 'demo'").fetchone() == (1,)


@pytest.mark.integration
def test_tenant_isolation(conn: psycopg.Connection):
    repo.upsert_document(conn, TENANT_A, make_doc())
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c1")])
    assert [chunk.id for chunk in repo.get_chunks(conn, TENANT_A, ["c1"])] == ["c1"]
    assert repo.get_chunks(conn, TENANT_B, ["c1"]) == []
    assert repo.get_document(conn, TENANT_B, "d1") is None


@pytest.mark.integration
def test_replace_chunks_replaces(conn: psycopg.Connection):
    repo.upsert_document(conn, TENANT_A, make_doc())
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c1"), make_chunk("c2", ordinal=1)])
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c3")])
    chunks = repo.get_chunks(conn, TENANT_A, ["c1", "c2", "c3"])
    assert [chunk.id for chunk in chunks] == ["c3"]


@pytest.mark.integration
def test_status_and_eval_roundtrip(conn: psycopg.Connection):
    repo.upsert_document(conn, TENANT_A, make_doc())
    repo.set_status(conn, TENANT_A, "d1", "failed", "boom")
    stored = repo.get_document(conn, TENANT_A, "d1")
    assert stored and (stored.status, stored.error) == ("failed", "boom")
    run_id = repo.insert_eval_run(conn, TENANT_A, {"k": 1})
    repo.insert_eval_result(conn, run_id, "q1", "rag", {"f1": 0.5}, {"text": "a"})
    assert conn.execute("SELECT config FROM eval_runs WHERE id = %s", (run_id,)).fetchone() == (
        {"k": 1},
    )
    assert conn.execute(
        "SELECT metrics, answer FROM eval_results WHERE run_id = %s AND question_id = 'q1' "
        "AND mode = 'rag'",
        (run_id,),
    ).fetchone() == ({"f1": 0.5}, {"text": "a"})


@pytest.mark.integration
def test_extraction_roundtrip(conn: psycopg.Connection):
    repo.upsert_document(conn, TENANT_A, make_doc())
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c1")])
    assert repo.get_extraction(conn, TENANT_A, "c1") is None
    repo.put_extraction(conn, TENANT_A, "c1", "sha1", "v1", {"entities": [1]})
    repo.put_extraction(conn, TENANT_A, "c1", "sha2", "v2", {"entities": []})
    assert repo.get_extraction(conn, TENANT_A, "c1") == ("sha2", "v2", {"entities": []})
    assert repo.get_extraction(conn, TENANT_B, "c1") is None


@pytest.mark.integration
def test_extraction_cascades_on_chunk_delete(conn: psycopg.Connection):
    repo.upsert_document(conn, TENANT_A, make_doc())
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c1")])
    repo.put_extraction(conn, TENANT_A, "c1", "sha1", "v1", {})
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c2")])
    assert repo.get_extraction(conn, TENANT_A, "c1") is None


@pytest.mark.integration
def test_list_chunks_tenant_scoped(conn: psycopg.Connection):
    for doc_id in ("d2", "d1"):
        repo.upsert_document(conn, TENANT_A, make_doc(doc_id))
    repo.upsert_document(conn, TENANT_B, make_doc("d1"))
    repo.replace_chunks(conn, TENANT_A, "d2", [make_chunk("c3", "d2")])
    repo.replace_chunks(conn, TENANT_A, "d1", [make_chunk("c2", ordinal=1), make_chunk("c1")])
    repo.replace_chunks(conn, TENANT_B, "d1", [make_chunk("cb")])
    assert [chunk.id for chunk in repo.list_chunks(conn, TENANT_A)] == ["c1", "c2", "c3"]


@pytest.mark.integration
def test_adjudication_roundtrip(conn: psycopg.Connection):
    assert repo.get_adjudication(conn, TENANT_A, "k1") is None
    repo.put_adjudication(conn, TENANT_A, "k1", True)
    repo.put_adjudication(conn, TENANT_A, "k1", False)
    assert repo.get_adjudication(conn, TENANT_A, "k1") is False
    assert repo.get_adjudication(conn, TENANT_B, "k1") is None


@pytest.mark.integration
def test_summary_roundtrip(conn: psycopg.Connection):
    assert repo.get_summary(conn, TENANT_A, "c0_0") is None
    repo.put_summary(conn, TENANT_A, "c0_0", "sha1", "v1", {"title": "a"})
    repo.put_summary(conn, TENANT_A, "c0_0", "sha2", "v2", {"title": "b"})
    assert repo.get_summary(conn, TENANT_A, "c0_0") == ("sha2", "v2", {"title": "b"})
    assert repo.get_summary(conn, TENANT_B, "c0_0") is None
