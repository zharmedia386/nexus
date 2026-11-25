from collections.abc import Callable

import httpx
import psycopg
from neo4j import GraphDatabase
from pymilvus import MilvusClient

from nexus.config import Settings


def check_postgres(settings: Settings) -> str:
    with psycopg.connect(settings.pg_conninfo, connect_timeout=5) as conn:
        conn.execute("SELECT 1")
    return "SELECT 1"


def check_milvus(settings: Settings) -> str:
    client = MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}", timeout=5)
    return f"server {client.get_server_version()}"


def check_neo4j(settings: Settings) -> str:
    with GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        connection_timeout=5,
    ) as driver:
        return driver.get_server_info().agent


def check_gateway(settings: Settings) -> str:
    response = httpx.get(
        f"{settings.LLM_BASE_URL}/v1/models",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        timeout=10,
    )
    response.raise_for_status()
    available = {model["id"] for model in response.json()["data"]}
    expected = {settings.LLM_MODEL, settings.EMBEDDING_MODEL, settings.RERANKER_MODEL}
    missing = expected - available
    if missing:
        raise RuntimeError(f"missing models: {', '.join(sorted(missing))}")
    return "models ok"


CHECKS: dict[str, Callable[[Settings], str]] = {
    "postgres": check_postgres,
    "milvus": check_milvus,
    "gateway": check_gateway,
    "neo4j": check_neo4j,
}
