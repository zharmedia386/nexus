from dataclasses import asdict
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nexus.api.deps import get_checks, get_conn, get_deps, get_graph, get_tenant
from nexus.config import get_settings
from nexus.db import repo
from nexus.eval.report import REPORT_DIR
from nexus.graph.neo4j_store import GraphPath, GraphStore
from nexus.llm import GatewayError
from nexus.retrieval.answer import Answer, answer
from nexus.retrieval.modes import Mode
from nexus.retrieval.orchestrator import Deps

Tenant = Annotated[str, Depends(get_tenant)]
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Graph = Annotated[GraphStore, Depends(get_graph)]
NEIGHBOUR_LIMIT = 40
EVAL_REPORT = REPORT_DIR / "eval-report.json"


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Mode
    verify: bool = True


def create_app() -> FastAPI:
    app = FastAPI(title="NEXUS")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Local-first demo: the tenant header selects data but is not a security boundary.
    @app.post("/query")
    def query(
        body: QueryRequest, tenant: Tenant, deps: Annotated[Deps, Depends(get_deps)]
    ) -> Answer:
        try:
            return answer(body.question, body.mode, tenant, deps=deps, verify=body.verify)
        except GatewayError as error:
            raise HTTPException(status_code=502, detail="upstream model gateway error") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/documents/{doc_id}")
    def document(doc_id: str, tenant: Tenant, conn: Conn) -> dict[str, object]:
        row = repo.get_document(conn, tenant, doc_id)
        if row is None:
            raise HTTPException(status_code=404, detail="document not found")
        return asdict(row)

    @app.get("/chunks/{chunk_id}")
    def chunk(chunk_id: str, tenant: Tenant, conn: Conn) -> dict[str, object]:
        rows = repo.get_chunks(conn, tenant, [chunk_id])
        if not rows:
            raise HTTPException(status_code=404, detail="chunk not found")
        return asdict(rows[0])

    @app.get("/graph/entity/{entity_id}")
    def graph_entity(entity_id: str, tenant: Tenant, graph: Graph) -> dict[str, object]:
        node = graph.entity_node(tenant, entity_id)
        if node is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return {**node, "edges": graph.entity_edges(tenant, entity_id, NEIGHBOUR_LIMIT)}

    @app.get("/graph/path")
    def graph_path(
        tenant: Tenant,
        graph: Graph,
        source: Annotated[str, Query(alias="from")],
        target: Annotated[str, Query(alias="to")],
    ) -> GraphPath | None:
        if any(graph.entity_node(tenant, entity_id) is None for entity_id in (source, target)):
            raise HTTPException(status_code=404, detail="entity not found")
        paths = graph.paths_between(tenant, [source, target], max_hops=4)
        return paths[0] if paths else None

    @app.get("/graph/search")
    def graph_search(
        tenant: Tenant,
        graph: Graph,
        q: Annotated[str, Query(min_length=2, max_length=80)],
        limit: Annotated[int, Query(ge=1, le=50)] = 10,
    ) -> list[dict[str, object]]:
        return graph.search_entities(tenant, q, limit)

    @app.get("/graph/stats")
    def graph_stats(tenant: Tenant, graph: Graph) -> dict[str, object]:
        return graph.stats(tenant)

    @app.get("/eval/report")
    def eval_report() -> Response:
        if not EVAL_REPORT.is_file():
            raise HTTPException(status_code=404, detail="eval report not found")
        return Response(EVAL_REPORT.read_bytes(), media_type="application/json")

    @app.get("/communities")
    def communities(
        tenant: Tenant, graph: Graph, level: Annotated[int, Query(ge=0, le=1)] = 0
    ) -> list[dict[str, object]]:
        return graph.list_communities(tenant, level)

    @app.get("/health")
    def health(checks: Annotated[dict, Depends(get_checks)]) -> dict[str, str]:
        settings = get_settings()
        report: dict[str, str] = {}
        for name, check in checks.items():
            try:
                check(settings)
                report[name] = "ok"
            except Exception:  # noqa: BLE001 - health never raises
                report[name] = "down"
        return report

    return app
