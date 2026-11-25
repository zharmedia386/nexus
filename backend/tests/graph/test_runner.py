import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from pydantic import BaseModel

from nexus.cli import main
from nexus.db.repo import ChunkRow
from nexus.graph.extract import EXTRACT_PROMPT_VERSION
from nexus.graph.runner import extract_tenant, load_extractions
from nexus.graph.schema import ExtractedEntity, ExtractionResult
from nexus.llm import GatewayError

RESULT = ExtractionResult(
    entities=[ExtractedEntity(name="BRMN", type="Company", aliases=[])],
    relations=[],
    dropped_unverified=0,
    dropped_unknown_entity=0,
)


class Conn:
    commits = 0
    rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1


def make_chunk(index: int, text: str | None = None) -> ChunkRow:
    return ChunkRow(f"doc_001#{index}", "doc_001", index, 0, 1, text or f"text {index}")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def store(monkeypatch):
    chunks = [make_chunk(0), make_chunk(1), make_chunk(2)]
    saved: dict[str, tuple[str, str, dict]] = {}
    monkeypatch.setattr("nexus.graph.runner.repo.list_chunks", lambda conn, tenant: chunks)
    monkeypatch.setattr(
        "nexus.graph.runner.repo.get_extraction", lambda conn, tenant, chunk_id: saved.get(chunk_id)
    )

    def put(conn, tenant, chunk_id, content_sha256, prompt_version, payload) -> None:
        saved[chunk_id] = (content_sha256, prompt_version, payload)

    monkeypatch.setattr("nexus.graph.runner.repo.put_extraction", put)
    return chunks, saved


def counting_extractor(calls: list[str], fail_on: str | None = None):
    def extractor(text: str) -> ExtractionResult:
        calls.append(text)
        if text == fail_on:
            raise GatewayError("boom")
        return RESULT

    return extractor


def test_cached_chunk_skips_llm(store) -> None:
    calls: list[str] = []
    conn = Conn()
    first = extract_tenant(conn, "demo", extractor=counting_extractor(calls))
    second = extract_tenant(conn, "demo", extractor=counting_extractor(calls))
    assert first == {"extracted": 3, "cached": 0, "failed": 0}
    assert second == {"extracted": 0, "cached": 3, "failed": 0}
    assert len(calls) == 3
    assert conn.commits == 3


def test_changed_chunk_reextracts(store) -> None:
    chunks, saved = store
    extract_tenant(Conn(), "demo", extractor=counting_extractor([]))
    chunks[1] = replace(chunks[1], text="edited")
    calls: list[str] = []
    counts = extract_tenant(Conn(), "demo", extractor=counting_extractor(calls))
    assert counts == {"extracted": 1, "cached": 2, "failed": 0}
    assert calls == ["edited"]
    assert saved[chunks[1].id][:2] == (sha("edited"), EXTRACT_PROMPT_VERSION)


def test_force_reextracts(store) -> None:
    extract_tenant(Conn(), "demo", extractor=counting_extractor([]))
    calls: list[str] = []
    counts = extract_tenant(Conn(), "demo", extractor=counting_extractor(calls), force=True)
    assert counts == {"extracted": 3, "cached": 0, "failed": 0}
    assert len(calls) == 3


def test_failure_does_not_stop_run(store, capsys) -> None:
    chunks, saved = store
    counts = extract_tenant(Conn(), "demo", extractor=counting_extractor([], fail_on="text 1"))
    assert counts == {"extracted": 2, "cached": 0, "failed": 1}
    assert capsys.readouterr().err == "doc_001#1: GatewayError\n"
    assert set(saved) == {chunks[0].id, chunks[2].id}


def test_validation_error_counts_as_failure(store, capsys) -> None:
    class Strict(BaseModel):
        value: int

    def extractor(text: str) -> ExtractionResult:
        Strict.model_validate({"value": "x"})
        raise AssertionError("unreachable")

    counts = extract_tenant(Conn(), "demo", extractor=extractor)
    assert counts == {"extracted": 0, "cached": 0, "failed": 3}
    assert capsys.readouterr().err.count(": ValidationError") == 3


def test_load_extractions_roundtrip(store) -> None:
    chunks, _ = store
    extract_tenant(Conn(), "demo", extractor=counting_extractor([]))
    loaded = load_extractions(Conn(), "demo")
    assert set(loaded) == {chunk.id for chunk in chunks}
    assert loaded[chunks[0].id] == RESULT


def test_graph_extract_exit_codes(monkeypatch, capsys) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            return None

    monkeypatch.setattr("nexus.cli.repo.connect", lambda: Connection())
    seen: dict = {}

    def fake(conn, tenant, *, force, workers):
        seen.update(tenant=tenant, force=force, workers=workers)
        return {"extracted": 1, "cached": 0, "failed": seen.get("failed", 0)}

    monkeypatch.setattr("nexus.cli.extract_tenant", fake)
    main(["graph", "extract", "--force", "--workers", "2"])
    assert seen == {"tenant": "demo", "force": True, "workers": 2}
    seen["failed"] = 1
    with pytest.raises(SystemExit) as exit_info:
        main(["graph", "extract"])
    assert exit_info.value.code == 1
    with pytest.raises(SystemExit) as bad_tenant:
        main(["graph", "extract", "--tenant", "Bad-Tenant"])
    assert bad_tenant.value.code == 2


def test_unexpected_error_counts_as_failure(store, capsys) -> None:
    chunks, saved = store

    def extractor(text: str) -> ExtractionResult:
        if text == "text 1":
            raise RuntimeError("boom")
        return RESULT

    conn = Conn()
    counts = extract_tenant(conn, "demo", extractor=extractor)
    assert counts == {"extracted": 2, "cached": 0, "failed": 1}
    assert capsys.readouterr().err == "doc_001#1: RuntimeError\n"
    assert set(saved) == {chunks[0].id, chunks[2].id}
    assert conn.rollbacks == 1


def test_abort_cancels_queued_chunks(store, monkeypatch) -> None:
    shutdowns: list[dict] = []

    class SpyPool(ThreadPoolExecutor):
        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            shutdowns.append({"wait": wait, "cancel_futures": cancel_futures})
            super().shutdown(wait=wait, cancel_futures=cancel_futures)

    monkeypatch.setattr("nexus.graph.runner.ThreadPoolExecutor", SpyPool)

    def extractor(text: str) -> ExtractionResult:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        extract_tenant(Conn(), "demo", extractor=extractor, workers=1)
    assert shutdowns == [{"wait": False, "cancel_futures": True}]
