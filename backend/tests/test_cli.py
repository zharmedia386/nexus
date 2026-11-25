import sys

import pytest

from nexus.cli import main, run_checks
from nexus.config import Settings
from nexus.datagen.planner import plan_documents
from nexus.datagen.world import build_world
from nexus.graph.resolve import PersonContext, ResolvedGraph
from nexus.llm import GatewayError


def _fail(_: Settings) -> str:
    raise RuntimeError("secret-key-123")


def test_run_checks_exit_codes(capsys) -> None:
    assert run_checks(Settings(), {"a": lambda _: "fine"}) == 0
    assert run_checks(Settings(), {"a": lambda _: "fine", "b": _fail}) == 1
    assert "secret-key-123" not in capsys.readouterr().out


def test_ingest_rejects_bad_tenant(tmp_path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", str(tmp_path), "--tenant", "Bad-Tenant"])
    assert exit_info.value.code == 2


def test_ingest_rejects_missing_directory(tmp_path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", str(tmp_path / "missing")])
    assert exit_info.value.code == 2


def test_ingest_exits_nonzero_on_failures(tmp_path, monkeypatch, capsys) -> None:
    counts = {"ingested": 1, "skipped": 0, "failed": 1}
    monkeypatch.setattr("nexus.cli.ingest_dir", lambda directory, tenant: counts)
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", str(tmp_path)])
    assert exit_info.value.code == 1
    assert "'failed': 1" in capsys.readouterr().out


def _fake_docs(tmp_path, monkeypatch, keep: float = 1.0):
    docs = tmp_path / "docs"
    docs.mkdir()
    plans = plan_documents(build_world(42))
    for plan in plans[: int(len(plans) * keep)]:
        (docs / f"{plan.doc_id}.md").write_text("x")
    monkeypatch.setattr("nexus.cli.DOCS_DIR", docs)
    monkeypatch.setattr("nexus.cli.QUESTIONS_PATH", tmp_path / "questions.jsonl")
    return plans


def test_eval_questions_writes_jsonl(tmp_path, monkeypatch, capsys) -> None:
    _fake_docs(tmp_path, monkeypatch)
    main(["eval", "questions"])
    assert len((tmp_path / "questions.jsonl").read_text().splitlines()) >= 100
    out = capsys.readouterr().out
    assert "eval: wrote" in out and "skipped 0 plans" in out


def test_eval_questions_skips_plans_without_docs(tmp_path, monkeypatch, capsys) -> None:
    plans = _fake_docs(tmp_path, monkeypatch, keep=0.5)
    main(["eval", "questions"])
    assert f"skipped {len(plans) - int(len(plans) * 0.5)} plans" in capsys.readouterr().out


def test_eval_questions_errors_without_docs(tmp_path, monkeypatch) -> None:
    _fake_docs(tmp_path, monkeypatch, keep=0)
    with pytest.raises(SystemExit) as exit_info:
        main(["eval", "questions"])
    assert exit_info.value.code == 2


def test_eval_run_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["eval", "run", "--modes", "rag,graph"])
    assert exit_info.value.code == 2


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def rollback(self) -> None:
        return None

    def commit(self) -> None:
        return None


def _stub_build(monkeypatch, failed: int) -> list[str]:
    calls: list[str] = []

    class FakeStore:
        def __enter__(self):
            calls.append("store")
            return self

        def __exit__(self, *exc_info) -> None:
            return None

        def ensure_schema(self) -> None:
            return None

        def write_graph(self, tenant, graph) -> dict[str, int]:
            return {"nodes": 0, "relationships": 0}

    monkeypatch.setattr("nexus.cli.repo.connect", lambda: _FakeConn())
    monkeypatch.setattr(
        "nexus.cli.extract_tenant",
        lambda *a, **k: {"extracted": 0, "cached": 1, "failed": failed},
    )
    monkeypatch.setattr("nexus.cli.load_extractions", lambda *a: {})
    monkeypatch.setattr("nexus.cli.repo.list_chunks", lambda *a: [])
    monkeypatch.setattr("nexus.cli.GraphStore", FakeStore)
    return calls


def test_graph_build_refuses_partial(monkeypatch, capsys) -> None:
    calls = _stub_build(monkeypatch, failed=3)
    with pytest.raises(SystemExit) as exit_info:
        main(["graph", "build", "--tenant", "test_graph_a"])
    assert exit_info.value.code == 1
    assert calls == []
    assert "3 chunks failed" in capsys.readouterr().out


def test_graph_build_allow_partial_writes(monkeypatch) -> None:
    calls = _stub_build(monkeypatch, failed=3)
    main(["graph", "build", "--tenant", "test_graph_a", "--allow-partial"])
    assert calls == ["store"]


def test_graph_eval_writes_report_without_llm(tmp_path, monkeypatch, capsys) -> None:
    _stub_build(monkeypatch, failed=0)
    written: list[object] = []

    def fake_write(result):
        written.append(result)
        path = tmp_path / "graph-x.md"
        path.write_text("report")
        return path

    def refuse(a, b) -> bool:
        raise AssertionError("adjudicator must not be called")

    monkeypatch.setattr("nexus.cli.write_graph_report", fake_write)
    monkeypatch.setattr("nexus.cli.adjudicate_people", refuse)
    main(["graph", "eval", "--tenant", "test_graph_a", "--no-adjudicate"])
    assert "graph: report" in capsys.readouterr().out
    [result] = written
    assert result.config["adjudication"] == "off" and result.docs == 0


def _stub_adjudication(monkeypatch, cache: dict[str, bool], llm) -> list[int]:
    limits: list[int] = []

    def fake_resolve(extractions, chunks, *, adjudicate, max_adjudications):
        limits.append(max_adjudications)
        for facts in (["x"], ["y"]):
            adjudicate(PersonContext("Budi", ["a"]), PersonContext("Budi", facts))
        return ResolvedGraph([], [], adjudications=2)

    def put(conn, tenant, key, same) -> None:
        cache[key] = same

    monkeypatch.setattr("nexus.cli.resolve", fake_resolve)
    monkeypatch.setattr("nexus.cli.repo.get_adjudication", lambda conn, t, key: cache.get(key))
    monkeypatch.setattr("nexus.cli.repo.put_adjudication", put)
    monkeypatch.setattr("nexus.cli.adjudicate_people", llm)
    return limits


def test_graph_build_gateway_error_keeps_cached_verdicts(monkeypatch, capsys) -> None:
    calls = _stub_build(monkeypatch, failed=0)
    cache: dict[str, bool] = {}
    verdicts = iter([True])

    def flaky_llm(a, b) -> bool:
        try:
            return next(verdicts)
        except StopIteration:
            raise GatewayError("boom") from None

    _stub_adjudication(monkeypatch, cache, flaky_llm)
    with pytest.raises(SystemExit) as exit_info:
        main(["graph", "build", "--tenant", "test_graph_a"])
    assert exit_info.value.code == 1
    assert calls == []
    assert list(cache.values()) == [True]
    assert "re-run to resume" in capsys.readouterr().out


def test_graph_eval_warm_cache_makes_no_llm_calls(tmp_path, monkeypatch) -> None:
    _stub_build(monkeypatch, failed=0)
    monkeypatch.setattr("nexus.cli.write_graph_report", lambda result: tmp_path / "r.md")
    (tmp_path / "r.md").write_text("report")
    cache: dict[str, bool] = {}
    _stub_adjudication(monkeypatch, cache, lambda a, b: True)
    main(["graph", "build", "--tenant", "test_graph_a"])
    warm = dict(cache)
    assert len(warm) == 2

    def refuse(a, b) -> bool:
        raise AssertionError("LLM must not be called with a warm cache")

    monkeypatch.setattr("nexus.cli.adjudicate_people", refuse)
    main(["graph", "eval", "--tenant", "test_graph_a"])
    assert cache == warm


def test_graph_eval_no_llm_treats_uncached_as_different(tmp_path, monkeypatch) -> None:
    _stub_build(monkeypatch, failed=0)
    monkeypatch.setattr("nexus.cli.write_graph_report", lambda result: tmp_path / "r.md")
    (tmp_path / "r.md").write_text("report")
    cache: dict[str, bool] = {}

    def refuse(a, b) -> bool:
        raise AssertionError("--no-llm must not call the LLM")

    limits = _stub_adjudication(monkeypatch, cache, refuse)
    main(["graph", "eval", "--tenant", "test_graph_a", "--no-llm", "--max-adjudications", "0"])
    assert cache == {}
    assert limits == [sys.maxsize]
