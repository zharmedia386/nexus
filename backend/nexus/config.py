from functools import lru_cache
from pathlib import Path

from psycopg.conninfo import make_conninfo
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore", env_ignore_empty=True
    )

    LLM_BASE_URL: str = "http://localhost:4000"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    EMBEDDING_MODEL: str = ""
    RERANKER_ENABLED: bool = True
    RERANKER_MODEL: str = ""
    RERANKER_TEMPLATE: str = ""
    RERANKER_TOP_N: int = 6
    RETRIEVAL_TOP_K: int = 10
    SIMILARITY_THRESHOLD: float = 0.4
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_SEARCH_NPROBE: int = 128
    MILVUS_COLLECTION_PREFIX: str = "nexus_"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "nexus"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str | None = None
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("MILVUS_COLLECTION_PREFIX")
    @classmethod
    def _require_nexus_prefix(cls, value: str) -> str:
        # Milvus may be a shared instance; never touch non-nexus collections.
        if not value.startswith("nexus_"):
            raise ValueError("MILVUS_COLLECTION_PREFIX must start with 'nexus_'")
        return value

    @property
    def pg_conninfo(self) -> str:
        return make_conninfo(
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            dbname=self.POSTGRES_DB,
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def collection(self, name: str) -> str:
        return f"{self.MILVUS_COLLECTION_PREFIX}{name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
