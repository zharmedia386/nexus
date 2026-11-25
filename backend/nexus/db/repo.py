from dataclasses import astuple, dataclass, fields
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from nexus.config import get_settings

Status = Literal["pending", "ingested", "failed"]


@dataclass(frozen=True)
class DocumentRow:
    id: str
    title: str
    doc_type: str
    lang: str
    year: int
    content: str
    sha256: str
    status: Status = "pending"
    error: str | None = None


@dataclass(frozen=True)
class ChunkRow:
    id: str
    doc_id: str
    ordinal: int
    start_char: int
    end_char: int
    text: str


# f-string SQL below interpolates only these dataclass field names, never values.
DOCUMENT_COLUMNS = ", ".join(field.name for field in fields(DocumentRow))
CHUNK_COLUMNS = ", ".join(field.name for field in fields(ChunkRow))


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().pg_conninfo)


def migration_files() -> list[Traversable]:
    folder = resources.files("nexus.db").joinpath("migrations")
    return sorted(
        (path for path in folder.iterdir() if path.name.endswith(".sql")),
        key=lambda path: path.name,
    )


# Migrations are idempotent (IF NOT EXISTS), so they rerun on every migrate.
def migration_sql() -> str:
    return "\n".join(path.read_text("utf-8") for path in migration_files())


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(migration_sql())
    conn.commit()


def upsert_document(conn: psycopg.Connection, tenant: str, doc: DocumentRow) -> None:
    placeholders = ", ".join(["%s"] * (len(fields(DocumentRow)) + 1))
    updates = ", ".join(
        f"{field.name} = EXCLUDED.{field.name}" for field in fields(DocumentRow)[1:]
    )
    conn.execute(
        f"INSERT INTO documents (tenant_id, {DOCUMENT_COLUMNS}) VALUES ({placeholders}) "
        f"ON CONFLICT (tenant_id, id) DO UPDATE SET {updates}",
        (tenant, *astuple(doc)),
    )


def get_document(conn: psycopg.Connection, tenant: str, doc_id: str) -> DocumentRow | None:
    row = conn.execute(
        f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE tenant_id = %s AND id = %s",
        (tenant, doc_id),
    ).fetchone()
    return DocumentRow(*row) if row else None


def replace_chunks(
    conn: psycopg.Connection, tenant: str, doc_id: str, chunks: list[ChunkRow]
) -> None:
    # Runs in the caller's transaction; the caller commits.
    conn.execute("DELETE FROM chunks WHERE tenant_id = %s AND doc_id = %s", (tenant, doc_id))
    placeholders = ", ".join(["%s"] * (len(fields(ChunkRow)) + 1))
    with conn.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO chunks (tenant_id, {CHUNK_COLUMNS}) VALUES ({placeholders})",
            [(tenant, *astuple(chunk)) for chunk in chunks],
        )


def get_chunks(conn: psycopg.Connection, tenant: str, ids: list[str]) -> list[ChunkRow]:
    rows = conn.execute(
        f"SELECT {CHUNK_COLUMNS} FROM chunks WHERE tenant_id = %s AND id = ANY(%s) "
        "ORDER BY doc_id, ordinal",
        (tenant, ids),
    ).fetchall()
    return [ChunkRow(*row) for row in rows]


def list_chunks(conn: psycopg.Connection, tenant: str) -> list[ChunkRow]:
    rows = conn.execute(
        f"SELECT {CHUNK_COLUMNS} FROM chunks WHERE tenant_id = %s ORDER BY doc_id, ordinal",
        (tenant,),
    ).fetchall()
    return [ChunkRow(*row) for row in rows]


def get_extraction(
    conn: psycopg.Connection, tenant: str, chunk_id: str
) -> tuple[str, str, dict[str, object]] | None:
    row = conn.execute(
        "SELECT content_sha256, prompt_version, payload FROM extractions "
        "WHERE tenant_id = %s AND chunk_id = %s",
        (tenant, chunk_id),
    ).fetchone()
    return (row[0], row[1], row[2]) if row else None


def put_extraction(
    conn: psycopg.Connection,
    tenant: str,
    chunk_id: str,
    content_sha256: str,
    prompt_version: str,
    payload: dict[str, object],
) -> None:
    conn.execute(
        "INSERT INTO extractions (tenant_id, chunk_id, content_sha256, prompt_version, payload) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (tenant_id, chunk_id) DO UPDATE SET "
        "content_sha256 = EXCLUDED.content_sha256, prompt_version = EXCLUDED.prompt_version, "
        "payload = EXCLUDED.payload, created_at = now()",
        (tenant, chunk_id, content_sha256, prompt_version, Jsonb(payload)),
    )


def set_status(
    conn: psycopg.Connection, tenant: str, doc_id: str, status: Status, error: str | None = None
) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, error = %s WHERE tenant_id = %s AND id = %s",
        (status, error, tenant, doc_id),
    )


def insert_eval_run(
    conn: psycopg.Connection, tenant: str, config: dict[str, object], run_id: UUID | None = None
) -> UUID:
    run_id = run_id or uuid4()
    conn.execute(
        "INSERT INTO eval_runs (id, tenant_id, config) VALUES (%s, %s, %s)",
        (run_id, tenant, Jsonb(config)),
    )
    return run_id


def insert_eval_result(
    conn: psycopg.Connection,
    run_id: UUID,
    question_id: str,
    mode: str,
    metrics: dict[str, object],
    answer: dict[str, object],
) -> None:
    conn.execute(
        "INSERT INTO eval_results (run_id, question_id, mode, metrics, answer) "
        "VALUES (%s, %s, %s, %s, %s)",
        (run_id, question_id, mode, Jsonb(metrics), Jsonb(answer)),
    )


def ensure_tenant(conn: psycopg.Connection, tenant: str) -> None:
    conn.execute("INSERT INTO tenants (id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant,))


def get_adjudication(conn: psycopg.Connection, tenant: str, key: str) -> bool | None:
    row = conn.execute(
        "SELECT same FROM adjudications WHERE tenant_id = %s AND pair_key = %s", (tenant, key)
    ).fetchone()
    return row[0] if row else None


def put_adjudication(conn: psycopg.Connection, tenant: str, key: str, same: bool) -> None:
    conn.execute(
        "INSERT INTO adjudications (tenant_id, pair_key, same) VALUES (%s, %s, %s) "
        "ON CONFLICT (tenant_id, pair_key) DO UPDATE SET same = EXCLUDED.same, created_at = now()",
        (tenant, key, same),
    )


def get_summary(
    conn: psycopg.Connection, tenant: str, community_id: str
) -> tuple[str, str, dict[str, object]] | None:
    row = conn.execute(
        "SELECT evidence_sha256, prompt_version, payload FROM community_summaries "
        "WHERE tenant_id = %s AND community_id = %s",
        (tenant, community_id),
    ).fetchone()
    return (row[0], row[1], row[2]) if row else None


def put_summary(
    conn: psycopg.Connection,
    tenant: str,
    community_id: str,
    evidence_sha256: str,
    prompt_version: str,
    payload: dict[str, object],
) -> None:
    conn.execute(
        "INSERT INTO community_summaries "
        "(tenant_id, community_id, evidence_sha256, prompt_version, payload) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (tenant_id, community_id) DO UPDATE SET "
        "evidence_sha256 = EXCLUDED.evidence_sha256, prompt_version = EXCLUDED.prompt_version, "
        "payload = EXCLUDED.payload, created_at = now()",
        (tenant, community_id, evidence_sha256, prompt_version, Jsonb(payload)),
    )
