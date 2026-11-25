import json
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from nexus.config import get_settings

DENSE_DIM = 1024
MAX_TEXT_CHARS = 8192
RRF_K = 60
TENANT_PATTERN = re.compile(r"^[a-z0-9_]{1,32}$")
CHUNK_ID_BODY = r"[A-Za-z0-9_.:-]{1,64}"
CHUNK_ID_PATTERN = re.compile(rf"^{CHUNK_ID_BODY}$")
# 59 leaves room for the ":0000" ordinal suffix within the 64-char chunk id limit.
DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,59}$")
OUTPUT_FIELDS = ["chunk_id", "doc_id", "text"]


@dataclass(frozen=True)
class ChunkVector:
    chunk_id: str
    tenant_id: str
    doc_id: str
    text: str
    dense: list[float]


@dataclass(frozen=True)
class Hit:
    # score scale differs: cosine for dense_search, RRF for hybrid_search.
    chunk_id: str
    doc_id: str
    text: str
    score: float


def _checked(value: str, pattern: re.Pattern[str], label: str) -> str:
    # Values are interpolated into Milvus filter expressions, so reject rather than escape.
    if not pattern.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def _pk(tenant: str, chunk_id: str) -> str:
    return f"{tenant}/{chunk_id}"


def _tenant_filter(tenant: str) -> str:
    return f'tenant_id == "{_checked(tenant, TENANT_PATTERN, "tenant")}"'


def _to_hits(raw_hits: list[dict]) -> list[Hit]:
    return [
        Hit(
            chunk_id=hit["entity"]["chunk_id"],
            doc_id=hit["entity"]["doc_id"],
            text=hit["entity"]["text"],
            score=float(hit["distance"]),
        )
        for hit in raw_hits
    ]


class ChunkStore:
    def __init__(
        self, collection: str, client_factory: Callable[[], MilvusClient] | None = None
    ) -> None:
        # Shared Milvus: refuse before any connection is opened.
        if not collection.startswith("nexus_"):
            raise ValueError(f"collection must start with 'nexus_': {collection!r}")
        self.collection = collection
        self._client_factory = client_factory
        self._client: MilvusClient | None = None

    @property
    def client(self) -> MilvusClient:
        if self._client is None and self._client_factory is not None:
            self._client = self._client_factory()
        if self._client is None:
            settings = get_settings()
            self._client = MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        return self._client

    def ensure(self) -> None:
        if not self.client.has_collection(self.collection):
            self.client.create_collection(
                self.collection,
                schema=self._schema(),
                index_params=self._index_params(),
                consistency_level="Strong",
            )
        else:
            # create_collection with index_params already loads the new collection.
            self.client.load_collection(self.collection)

    def _schema(self):
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        # Tenant-namespaced PK so deletes by key can never cross tenants.
        schema.add_field("pk", DataType.VARCHAR, is_primary=True, max_length=100)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
        schema.add_field("tenant_id", DataType.VARCHAR, max_length=32, is_partition_key=True)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field(
            "text",
            DataType.VARCHAR,
            max_length=8192,
            enable_analyzer=True,
            analyzer_params={"type": "standard"},
        )
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DENSE_DIM)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="text_bm25",
                function_type=FunctionType.BM25,
                input_field_names=["text"],
                output_field_names=["sparse"],
            )
        )
        return schema

    def _index_params(self):
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="dense",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        index_params.add_index(
            field_name="sparse",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
        )
        return index_params

    def upsert(self, rows: list[ChunkVector]) -> None:
        if not rows:
            return
        seen: set[tuple[str, str]] = set()
        for row in rows:
            _checked(row.chunk_id, CHUNK_ID_PATTERN, "chunk_id")
            _checked(row.doc_id, DOC_ID_PATTERN, "doc_id")
            _checked(row.tenant_id, TENANT_PATTERN, "tenant")
            if len(row.dense) != DENSE_DIM:
                raise ValueError(f"dense must have {DENSE_DIM} dims: {row.chunk_id!r}")
            if len(row.text) > MAX_TEXT_CHARS:
                raise ValueError(f"text exceeds {MAX_TEXT_CHARS} chars: {row.chunk_id!r}")
            key = (row.tenant_id, row.chunk_id)
            if key in seen:
                raise ValueError(f"duplicate chunk_id in batch: {row.chunk_id!r}")
            seen.add(key)
        pks_by_tenant: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            pks_by_tenant[row.tenant_id].append(_pk(row.tenant_id, row.chunk_id))
        delete_filters = [f"pk in {json.dumps(pks)}" for pks in pks_by_tenant.values()]
        data = [
            {
                "pk": _pk(row.tenant_id, row.chunk_id),
                "chunk_id": row.chunk_id,
                "tenant_id": row.tenant_id,
                "doc_id": row.doc_id,
                "text": row.text,
                "dense": row.dense,
            }
            for row in rows
        ]
        # Delete+insert, not upsert: Milvus 2.5.0 may reject upsert on BM25-function collections.
        for delete_filter in delete_filters:
            self.client.delete(self.collection, filter=delete_filter)
        self.client.insert(self.collection, data)

    def delete_doc(self, tenant: str, doc_id: str) -> None:
        doc_filter = f'doc_id == "{_checked(doc_id, DOC_ID_PATTERN, "doc_id")}"'
        delete_filter = f"{_tenant_filter(tenant)} and {doc_filter}"
        self.client.delete(self.collection, filter=delete_filter)

    def _dense_params(self) -> dict:
        nprobe = get_settings().MILVUS_SEARCH_NPROBE
        return {"metric_type": "COSINE", "params": {"nprobe": nprobe}}

    def dense_search(self, tenant: str, vector: list[float], k: int) -> list[Hit]:
        tenant_filter = _tenant_filter(tenant)
        results = self.client.search(
            self.collection,
            data=[vector],
            anns_field="dense",
            filter=tenant_filter,
            limit=k,
            output_fields=OUTPUT_FIELDS,
            search_params=self._dense_params(),
        )
        return _to_hits(results[0])

    def hybrid_search(self, tenant: str, query_text: str, vector: list[float], k: int) -> list[Hit]:
        tenant_filter = _tenant_filter(tenant)
        dense_request = AnnSearchRequest(
            data=[vector],
            anns_field="dense",
            param=self._dense_params(),
            limit=k,
            expr=tenant_filter,
        )
        bm25_request = AnnSearchRequest(
            data=[query_text],
            anns_field="sparse",
            param={"metric_type": "BM25"},
            limit=k,
            expr=tenant_filter,
        )
        results = self.client.hybrid_search(
            self.collection,
            [dense_request, bm25_request],
            ranker=RRFRanker(RRF_K),
            limit=k,
            output_fields=OUTPUT_FIELDS,
        )
        return _to_hits(results[0])

    def drop(self) -> None:
        if not self.collection.startswith("nexus_test_"):
            raise ValueError(f"refusing to drop non-test collection: {self.collection!r}")
        self.client.drop_collection(self.collection)
