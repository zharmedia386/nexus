from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated

import psycopg
from fastapi import Depends, Header, HTTPException

from nexus.checks import CHECKS
from nexus.config import Settings
from nexus.db import repo
from nexus.graph.neo4j_store import GraphStore
from nexus.retrieval.orchestrator import Deps, default_deps
from nexus.vector.milvus_store import TENANT_PATTERN


def get_tenant(x_tenant: str = Header("demo")) -> str:
    if not TENANT_PATTERN.fullmatch(x_tenant):
        raise HTTPException(status_code=400, detail="invalid X-Tenant header")
    return x_tenant


@lru_cache
def get_deps() -> Deps:
    return default_deps()


def get_graph(deps: Annotated[Deps, Depends(get_deps)]) -> GraphStore:
    if deps.graph is None:
        raise HTTPException(status_code=503, detail="graph store unavailable")
    return deps.graph


def get_conn() -> Iterator[psycopg.Connection]:
    with repo.connect() as conn:
        yield conn


def get_checks() -> dict[str, Callable[[Settings], str]]:
    return CHECKS
