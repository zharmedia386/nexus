from typing import ClassVar

from fastapi.testclient import TestClient

from nexus.api import app as app_module
from nexus.api.deps import get_checks, get_conn, get_deps, get_graph
from nexus.db.repo import ChunkRow, DocumentRow
from nexus.graph.neo4j_store import GraphPath
from nexus.llm import GatewayError
from nexus.retrieval.answer import Answer

DOC = DocumentRow("doc_a", "Judul", "news", "id", 2024, "isi dokumen", "abc123")
CHUNK = ChunkRow("doc_a:0001", "doc_a", 1, 0, 5, "isi do")


def make_client(monkeypatch, checks=None) -> TestClient:
    def fake_get_document(conn, tenant, doc_id):
        return DOC if (tenant, doc_id) == ("demo", "doc_a") else None

    def fake_get_chunks(conn, tenant, ids):
        return [CHUNK] if tenant == "demo" and ids == [CHUNK.id] else []

    monkeypatch.setattr(app_module.repo, "get_document", fake_get_document)
    monkeypatch.setattr(app_module.repo, "get_chunks", fake_get_chunks)
    app = app_module.create_app()
    app.dependency_overrides[get_deps] = lambda: object()
    app.dependency_overrides[get_conn] = lambda: object()
    app.dependency_overrides[get_checks] = lambda: checks or {}
    return TestClient(app)


PATH = GraphPath(["e1", "e2"], ["Budi", "PT Maju"], ["FOUNDED"], ["doc_a:0001"])


class FakeGraph:
    nodes: ClassVar[dict] = {("demo", "e1"): "Budi", ("demo", "e2"): "PT Maju"}

    def entity_node(self, tenant, entity_id):
        name = self.nodes.get((tenant, entity_id))
        return name and {
            "id": entity_id,
            "name": name,
            "type": "Person",
            "aliases": [],
            "chunk_ids": [],
        }

    def entity_edges(self, tenant, entity_id, limit):
        return [{"type": "FOUNDED", "outgoing": True, "other_id": "e2", "limit": limit}]

    def paths_between(self, tenant, ids, max_hops):
        return [PATH]

    def search_entities(self, tenant, text, limit):
        found = [
            {"id": eid, "name": name, "type": "Person", "aliases": [], "match": "prefix"}
            for (owner, eid), name in self.nodes.items()
            if owner == tenant and text.lower() in name.lower()
        ]
        return found[:limit]

    def stats(self, tenant):
        counts = {"demo": {"Person": 1, "Company": 1}}.get(tenant, {})
        top = [{"id": "e1", "name": "Budi", "type": "Person", "degree": 1}] if counts else []
        return {
            "nodes": sum(counts.values()),
            "relationships": len(counts) // 2,
            "by_type": counts,
            "top": top,
        }

    def list_communities(self, tenant, level):
        return [
            {
                "id": "c0",
                "level": level,
                "size": 3,
                "title": "Grup",
                "summary": "s",
                "parent_id": None,
                "member_ids": ["e1"],
                "member_names": ["Budi"],
                "summary_chunk_ids": [],
            }
        ]


def graph_client(monkeypatch) -> TestClient:
    client = make_client(monkeypatch)
    client.app.dependency_overrides[get_graph] = lambda: FakeGraph()
    return client


def fake_answer(question, mode, tenant, *, deps, verify=True):
    return Answer(
        text="Budi [doc_a:0001]",
        citations=["doc_a:0001"],
        invalid_citations=[],
        hits=[],
        abstained=False,
        mode=mode,
        latency_ms=1,
    )


def test_query_returns_answer(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "answer", fake_answer)
    response = make_client(monkeypatch).post("/query", json={"question": "Siapa?", "mode": "rag"})
    assert response.status_code == 200
    assert response.json()["citations"] == ["doc_a:0001"]


def test_query_validates_mode(monkeypatch) -> None:
    client = make_client(monkeypatch)
    assert client.post("/query", json={"question": "x", "mode": "nope"}).status_code == 422
    assert client.post("/query", json={"question": "", "mode": "rag"}).status_code == 422


def test_query_gateway_error_is_generic_502(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise GatewayError("http://secret-host key-123")

    monkeypatch.setattr(app_module, "answer", boom)
    response = make_client(monkeypatch).post("/query", json={"question": "x", "mode": "rag"})
    assert response.status_code == 502
    assert "secret" not in response.text


def test_bad_tenant_header_400(monkeypatch) -> None:
    client = make_client(monkeypatch)
    assert client.get("/documents/doc_a", headers={"X-Tenant": "Bad-Tenant"}).status_code == 400


def test_document_and_chunk_lookup(monkeypatch) -> None:
    client = make_client(monkeypatch)
    assert client.get("/documents/doc_a").json()["content"] == "isi dokumen"
    body = client.get("/chunks/doc_a:0001").json()
    assert (body["start_char"], body["end_char"]) == (0, 5)


def test_document_404_other_tenant(monkeypatch) -> None:
    client = make_client(monkeypatch)
    assert client.get("/documents/doc_a", headers={"X-Tenant": "other"}).status_code == 404
    assert client.get("/chunks/doc_a:0001", headers={"X-Tenant": "other"}).status_code == 404


def test_health_reports_down_service(monkeypatch) -> None:
    def down(_):
        raise RuntimeError("secret")

    client = make_client(monkeypatch, {"postgres": lambda _: "ok", "milvus": down})
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"postgres": "ok", "milvus": "down"}


def test_cors_allows_only_frontend_origin(monkeypatch) -> None:
    client = make_client(monkeypatch)
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    other = client.get("/health", headers={"Origin": "http://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in other.headers


def test_query_graph_local_returns_paths(monkeypatch) -> None:
    seen = {}

    def graph_answer(question, mode, tenant, *, deps, verify):
        seen.update(mode=mode, verify=verify)
        return fake_answer(question, mode, tenant, deps=deps).model_copy(
            update={"graph_paths": [PATH], "routed_mode": "graph_local", "llm_calls": 3}
        )

    monkeypatch.setattr(app_module, "answer", graph_answer)
    body = (
        make_client(monkeypatch)
        .post("/query", json={"question": "Siapa?", "mode": "auto", "verify": False})
        .json()
    )
    assert seen == {"mode": "auto", "verify": False}
    assert body["graph_paths"][0]["rel_types"] == ["FOUNDED"]
    assert (body["routed_mode"], body["llm_calls"]) == ("graph_local", 3)


def test_graph_entity_endpoint(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    body = client.get("/graph/entity/e1").json()
    assert body["name"] == "Budi" and body["edges"][0]["limit"] == 40
    assert client.get("/graph/entity/e1", headers={"X-Tenant": "other"}).status_code == 404


def test_graph_path_endpoint_excludes_other_tenant(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    found = client.get("/graph/path", params={"from": "e1", "to": "e2"})
    assert found.json()["node_ids"] == ["e1", "e2"]
    other = client.get(
        "/graph/path", params={"from": "e1", "to": "e2"}, headers={"X-Tenant": "other"}
    )
    assert other.status_code == 404
    assert client.get("/graph/path", params={"from": "e1", "to": "zz"}).status_code == 404


def test_graph_path_none_when_unconnected(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    monkeypatch.setattr(FakeGraph, "paths_between", lambda *args, **kwargs: [])
    response = client.get("/graph/path", params={"from": "e1", "to": "e2"})
    assert response.status_code == 200 and response.json() is None


def test_communities_endpoint(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    rows = client.get("/communities", params={"level": 1}).json()
    assert rows[0]["member_ids"] == ["e1"] and rows[0]["level"] == 1
    assert client.get("/communities", params={"level": 2}).status_code == 422


def test_graph_stats_scoped_by_tenant(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    stats = client.get("/graph/stats").json()
    assert stats == {
        "nodes": 2,
        "relationships": 1,
        "by_type": {"Person": 1, "Company": 1},
        "top": [{"id": "e1", "name": "Budi", "type": "Person", "degree": 1}],
    }
    other = client.get("/graph/stats", headers={"X-Tenant": "other"}).json()
    assert other == {"nodes": 0, "relationships": 0, "by_type": {}, "top": []}


def test_graph_search_validates_and_scopes_tenant(monkeypatch) -> None:
    client = graph_client(monkeypatch)
    assert [row["id"] for row in client.get("/graph/search", params={"q": "bud"}).json()] == ["e1"]
    other = client.get("/graph/search", params={"q": "bud"}, headers={"X-Tenant": "other"})
    assert other.json() == []
    for bad in ("b", "x" * 81):
        assert client.get("/graph/search", params={"q": bad}).status_code == 422


def test_eval_report_served_or_404(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch)
    monkeypatch.setattr(app_module, "EVAL_REPORT", tmp_path / "eval-report.json")
    assert client.get("/eval/report").status_code == 404
    (tmp_path / "eval-report.json").write_text('{"ok": 1}')
    response = client.get("/eval/report")
    assert response.status_code == 200 and response.json() == {"ok": 1}


def test_answer_communities_default_empty(monkeypatch) -> None:
    assert fake_answer("q", "rag", "demo", deps=None).communities == []
