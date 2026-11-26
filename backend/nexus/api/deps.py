from collections.abc import Callable, Iterator
from functools import lru_cache

import psycopg
from fastapi import Header, HTTPException

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


@lru_cache
def get_graph() -> GraphStore:
    # Graph endpoints only read Neo4j; going through get_deps would also require Milvus to be up.
    return GraphStore()


def get_conn() -> Iterator[psycopg.Connection]:
    with repo.connect() as conn:
        yield conn


def get_checks() -> dict[str, Callable[[Settings], str]]:
    return CHECKS
