import pytest

from nexus.config import Settings


def test_collection_name_uses_prefix() -> None:
    assert Settings(MILVUS_COLLECTION_PREFIX="nexus_").collection("chunks") == "nexus_chunks"


def test_rejects_non_nexus_prefix() -> None:
    with pytest.raises(ValueError):
        Settings(MILVUS_COLLECTION_PREFIX="grc_local")


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.RERANKER_TOP_N == 6
    assert settings.RETRIEVAL_TOP_K == 10
    assert settings.SIMILARITY_THRESHOLD == 0.4


def test_cors_origins_parse_comma_list() -> None:
    assert Settings(_env_file=None).cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    custom = Settings(_env_file=None, CORS_ORIGINS=" https://a.example , https://b.example,")
    assert custom.cors_origins == ["https://a.example", "https://b.example"]
