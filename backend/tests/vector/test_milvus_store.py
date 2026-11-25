import random
import uuid
from collections.abc import Iterator

import pytest
from pymilvus import MilvusClient

from nexus.vector.milvus_store import DENSE_DIM, ChunkStore, ChunkVector


def random_vector(rng: random.Random) -> list[float]:
    return [rng.uniform(-1, 1) for _ in range(DENSE_DIM)]


def test_rejects_foreign_prefix():
    with pytest.raises(ValueError):
        ChunkStore("grc_local_chunks")


def test_drop_refuses_non_test_collection():
    with pytest.raises(ValueError):
        ChunkStore("nexus_chunks").drop()


def no_connection_store() -> ChunkStore:
    def fail() -> MilvusClient:
        pytest.fail("client must not be created before validation")

    return ChunkStore("nexus_test_unit", client_factory=fail)


def test_filter_values_are_validated():
    store = no_connection_store()
    vector = [0.0] * DENSE_DIM
    bad_tenant = 'demo" or tenant_id != "'
    with pytest.raises(ValueError):
        store.delete_doc("demo", 'x" or chunk_id != "')
    with pytest.raises(ValueError):
        store.delete_doc(bad_tenant, "d1")
    with pytest.raises(ValueError):
        store.dense_search(bad_tenant, vector, 3)
    with pytest.raises(ValueError):
        store.hybrid_search(bad_tenant, "q", vector, 3)


@pytest.mark.parametrize(
    "row",
    [
        ChunkVector("c" * 65, "demo", "d1", "t", []),
        ChunkVector('c"1', "demo", "d1", "t", []),
        ChunkVector("c1", "demo", 'd"1', "t", []),
        ChunkVector("c1", "Demo", "d1", "t", [0.0] * DENSE_DIM),
        ChunkVector("c1", "demo", "d1", "t", [0.0] * (DENSE_DIM - 1)),
        ChunkVector("c1", "demo", "d1", "x" * 8193, [0.0] * DENSE_DIM),
    ],
)
def test_upsert_validates_ids(row: ChunkVector):
    with pytest.raises(ValueError):
        no_connection_store().upsert([row])


def test_upsert_rejects_duplicate_chunk_ids_in_batch():
    row = ChunkVector("c1", "demo", "d1", "t", [0.0] * DENSE_DIM)
    with pytest.raises(ValueError):
        no_connection_store().upsert([row, row])


@pytest.fixture
def store() -> Iterator[ChunkStore]:
    chunk_store = ChunkStore(f"nexus_test_chunks_{uuid.uuid4().hex[:8]}")
    chunk_store.ensure()
    yield chunk_store
    chunk_store.drop()


def make_row(rng: random.Random, chunk_id: str, tenant: str, doc_id: str, text: str):
    return ChunkVector(chunk_id, tenant, doc_id, text, random_vector(rng))


@pytest.mark.integration
def test_dense_search_tenant_filter(store: ChunkStore):
    rng = random.Random(1)
    rows = [
        make_row(rng, f"c{i}", "demo" if i % 2 else "other", "d1", f"text {i}") for i in range(10)
    ]
    store.upsert(rows)
    hits = store.dense_search("demo", random_vector(rng), 10)
    assert hits
    assert all(int(hit.chunk_id[1:]) % 2 == 1 for hit in hits)


@pytest.mark.integration
def test_bm25_matches_alias_lowercase(store: ChunkStore):
    rng = random.Random(2)
    target = "PT Sinar Jaya Tbk menandatangani perjanjian kredit sindikasi."
    store.upsert(
        [
            make_row(rng, "target", "demo", "d1", target),
            make_row(rng, "n1", "demo", "d1", "PT Maju Bersama membuka cabang baru di Surabaya."),
            make_row(rng, "n2", "demo", "d2", "Laporan tahunan menyebut pertumbuhan laba bersih."),
        ]
    )
    hits = store.hybrid_search("demo", "sinar jaya", random_vector(rng), 3)
    assert hits[0].chunk_id == "target"


@pytest.mark.integration
def test_delete_doc(store: ChunkStore):
    rng = random.Random(3)
    store.upsert(
        [
            make_row(rng, "a", "demo", "d1", "alpha"),
            make_row(rng, "b", "demo", "d2", "beta"),
        ]
    )
    store.delete_doc("demo", "d1")
    hits = store.dense_search("demo", random_vector(rng), 10)
    assert {hit.chunk_id for hit in hits} == {"b"}


def test_doc_id_pattern_leaves_room_for_chunk_suffix() -> None:
    from nexus.vector.milvus_store import DOC_ID_PATTERN

    assert DOC_ID_PATTERN.fullmatch("a" * 59)
    assert not DOC_ID_PATTERN.fullmatch("a" * 60)
