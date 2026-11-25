import json

import pytest

from nexus.eval import harness
from nexus.eval.harness import run_eval
from nexus.eval.questions import Question, write_questions
from nexus.llm import GatewayError
from nexus.retrieval.answer import Answer
from nexus.retrieval.verify import CLAIM_SPLIT_VERSION, Claim
from nexus.vector.milvus_store import Hit

LEXICON = {"budi santoso": "pe_1", "rina wijaya": "pe_2", "a": "co_1"}
QUESTIONS = [
    Question(
        id="sh_001",
        lang="id",
        category="single_hop",
        text="Siapa pendiri PT A?",
        gold_answers=[["Budi Santoso"]],
        gold_doc_ids=["doc_002"],
    ),
    Question(
        id="un_001",
        lang="en",
        category="unanswerable",
        text="Who is the Marketing Director of PT A?",
        gold_answers=[],
        gold_doc_ids=[],
    ),
]


def fake_answer(text: str, mode: str, tenant: str) -> Answer:
    hits = [Hit("doc_001:0", "doc_001", "x", 0.9), Hit("doc_002:0", "doc_002", "y", 0.8)]
    if mode == "rag":
        reply, abstained = "Informasi tidak ditemukan.", True
    else:
        reply, abstained = "Budi Santoso [doc_002:0]", False
    return Answer(
        text=reply,
        citations=[],
        invalid_citations=[],
        hits=hits,
        abstained=abstained,
        mode=mode,
        latency_ms=10 if mode == "rag" else 30,
    )


def test_run_eval_end_to_end_with_fake(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)
    run_id = run_eval(
        ["rag", "hybrid"],
        questions_path=questions_path,
        out_dir=tmp_path / "runs",
        answer_fn=fake_answer,
        persist=False,
        lexicon=LEXICON,
    )
    report = json.loads((tmp_path / "runs" / f"{run_id}.json").read_text())
    assert len(report["results"]) == 4
    assert report["config"]["claim_split_version"] == CLAIM_SPLIT_VERSION
    summary = {(row["mode"], row["category"]): row for row in report["summary"]}
    assert summary[("rag", "single_hop")]["answer_match"] == 0.0
    assert summary[("rag", "single_hop")]["abstain_accuracy"] == 0.0
    assert summary[("hybrid", "single_hop")]["answer_match"] == 1.0
    assert summary[("hybrid", "single_hop")]["recall_at_k"] == 1.0
    assert summary[("hybrid", "single_hop")]["answer_precision"] == 1.0
    assert summary[("rag", "unanswerable")]["abstain_accuracy"] == 1.0
    assert summary[("rag", "unanswerable")]["recall_at_k"] is None
    assert summary[("hybrid", "unanswerable")]["abstain_accuracy"] == 0.0
    assert summary[("hybrid", "single_hop")]["p50_ms"] == 30
    assert summary[("rag", "all")]["n"] == 2
    markdown = (tmp_path / "runs" / f"{run_id}.md").read_text()
    assert "| hybrid | single_hop |" in markdown and "answer_precision" in markdown


def test_run_eval_limit(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)
    run_id = run_eval(
        ["hybrid"],
        limit=1,
        questions_path=questions_path,
        out_dir=tmp_path,
        answer_fn=fake_answer,
        persist=False,
        lexicon=LEXICON,
    )
    report = json.loads((tmp_path / f"{run_id}.json").read_text())
    assert [row["question_id"] for row in report["results"]] == ["sh_001"]


def test_abstained_answer_naming_gold_scores_zero(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS[:1], questions_path)

    def abstain_but_name(text: str, mode: str, tenant: str) -> Answer:
        reply = "Informasi tidak ditemukan, mungkin Budi Santoso."
        return fake_answer(text, mode, tenant).model_copy(update={"text": reply, "abstained": True})

    run_id = run_eval(
        ["hybrid"],
        questions_path=questions_path,
        out_dir=tmp_path,
        answer_fn=abstain_but_name,
        persist=False,
        lexicon=LEXICON,
    )
    (row,) = json.loads((tmp_path / f"{run_id}.json").read_text())["results"]
    assert row["metrics"]["answer_match"] == 0.0
    assert row["metrics"]["abstain_correct"] is False


def test_gateway_error_becomes_error_row(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)

    def flaky(text: str, mode: str, tenant: str) -> Answer:
        if text.startswith("Who"):
            raise GatewayError("down")
        return fake_answer(text, mode, tenant)

    run_id = run_eval(
        ["hybrid"],
        questions_path=questions_path,
        out_dir=tmp_path / "runs",
        answer_fn=flaky,
        persist=False,
        lexicon=LEXICON,
    )
    report = json.loads((tmp_path / "runs" / f"{run_id}.json").read_text())
    errored = [row for row in report["results"] if "error" in row["metrics"]]
    assert [row["metrics"] for row in errored] == [{"error": "GatewayError"}]
    summary = {(row["mode"], row["category"]): row for row in report["summary"]}
    assert summary[("hybrid", "unanswerable")]["n"] == 0
    assert summary[("hybrid", "unanswerable")]["n_errors"] == 1
    assert summary[("hybrid", "all")]["n"] == 1 and summary[("hybrid", "all")]["n_errors"] == 1
    assert "n_errors" in (tmp_path / "runs" / f"{run_id}.md").read_text()


def test_results_written_before_persist_failure(tmp_path, monkeypatch) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)

    def boom(*args: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(harness, "_persist", boom)
    with pytest.raises(RuntimeError):
        run_eval(
            ["rag"],
            questions_path=questions_path,
            out_dir=tmp_path / "runs",
            answer_fn=fake_answer,
            lexicon=LEXICON,
        )
    assert len(list((tmp_path / "runs").glob("*.json"))) == 1


def claim_answer(text: str, mode: str, tenant: str) -> Answer:
    claims = [
        Claim(text="a", chunk_ids=["x"], supported=True),
        Claim(text="b", chunk_ids=[], supported=False),
        # Unverified: excluded from both rates, so they stay 0.5 rather than 1/3.
        Claim(text="c", chunk_ids=["x"], supported=None),
    ]
    return fake_answer(text, mode, tenant).model_copy(
        update={
            "claims": claims if mode != "hybrid" else [],
            "llm_calls": 4,
            "verify_calls": 1,
            "verify_ms": 7,
            "routed_mode": "graph_local" if mode == "auto" else None,
        }
    )


def test_summary_reports_claim_metrics_and_llm_calls(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)
    run_id = run_eval(
        ["graph_local", "hybrid", "auto"],
        questions_path=questions_path,
        out_dir=tmp_path / "runs",
        answer_fn=claim_answer,
        persist=False,
        lexicon=LEXICON,
    )
    report = json.loads((tmp_path / "runs" / f"{run_id}.json").read_text())
    summary = {(row["mode"], row["category"]): row for row in report["summary"]}
    local = summary[("graph_local", "all")]
    assert (local["citation_precision"], local["unsupported_claim_rate"]) == (0.5, 0.5)
    assert (local["mean_llm_calls"], local["mean_verify_calls"], local["mean_verify_ms"]) == (
        4,
        1,
        7,
    )
    # No claims (verification off) means no rate, not 0.
    assert summary[("hybrid", "all")]["unsupported_claim_rate"] is None
    markdown = (tmp_path / "runs" / f"{run_id}.md").read_text()
    assert "citation_precision" in markdown and "mean_llm_calls" in markdown
    assert "| graph_local | 2 |" in markdown


def test_unexpected_exception_becomes_error_row_and_partial_file(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)

    def broken(text: str, mode: str, tenant: str) -> Answer:
        if text.startswith("Who"):
            raise KeyError("boom")
        return fake_answer(text, mode, tenant)

    run_id = run_eval(
        ["hybrid"],
        questions_path=questions_path,
        out_dir=tmp_path / "runs",
        answer_fn=broken,
        persist=False,
        lexicon=LEXICON,
    )
    runs = tmp_path / "runs"
    report = json.loads((runs / f"{run_id}.json").read_text())
    errored = [row for row in report["results"] if "error" in row["metrics"]]
    assert [row["metrics"] for row in errored] == [{"error": "KeyError"}]
    assert len(report["results"]) == 2
    partial = (runs / f"{run_id}.partial.jsonl").read_text().splitlines()
    assert [json.loads(line)["question_id"] for line in partial] == ["sh_001", "un_001"]


def test_keyboard_interrupt_keeps_finished_rows(tmp_path) -> None:
    questions_path = tmp_path / "questions.jsonl"
    write_questions(QUESTIONS, questions_path)

    def interrupted(text: str, mode: str, tenant: str) -> Answer:
        if text.startswith("Who"):
            raise KeyboardInterrupt
        return fake_answer(text, mode, tenant)

    with pytest.raises(KeyboardInterrupt):
        run_eval(
            ["hybrid"],
            questions_path=questions_path,
            out_dir=tmp_path / "runs",
            answer_fn=interrupted,
            persist=False,
            lexicon=LEXICON,
        )
    (partial_file,) = (tmp_path / "runs").glob("*.partial.jsonl")
    assert len(partial_file.read_text().splitlines()) == 1
