import csv
import json

from nexus.eval.harness import route_counts, run_eval, summarize, to_markdown
from nexus.eval.questions import Question, write_questions
from nexus.eval.review import load_rejected, write_review_sheet
from nexus.retrieval.answer import Answer


def make_question(question_id: str) -> Question:
    return Question(
        id=question_id,
        lang="id",
        category="single_hop",
        text=f"Siapa {question_id}?",
        gold_answers=[["Budi Santoso", "Pak Budi"], ["Rina"]],
        gold_doc_ids=["doc_001", "doc_002"],
    )


def fake_answer(text: str, mode: str, tenant: str) -> Answer:
    return Answer(
        text="Budi Santoso",
        citations=[],
        invalid_citations=[],
        hits=[],
        abstained=False,
        mode=mode,
        latency_ms=10,
    )


def test_sheet_merge_preserves_marks(tmp_path) -> None:
    path = tmp_path / "review" / "questions.csv"
    write_review_sheet([make_question("sh_001")], path)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["gold_answers"] == "Budi Santoso | Rina"
    assert rows[0]["gold_doc_ids"] == "doc_001 | doc_002"
    rows[0].update(accept="X", note="ambiguous")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    write_review_sheet([make_question("sh_001"), make_question("sh_002")], path)
    merged = {row["id"]: row for row in csv.DictReader(path.open(encoding="utf-8"))}
    assert merged["sh_001"]["accept"] == "X" and merged["sh_001"]["note"] == "ambiguous"
    assert merged["sh_002"]["accept"] == ""
    assert load_rejected(path) == {"sh_001"}


def test_rejected_questions_excluded_from_summary(tmp_path) -> None:
    questions_path = tmp_path / "q.jsonl"
    write_questions([make_question("sh_001"), make_question("sh_002")], questions_path)
    sheet = tmp_path / "sheet.csv"
    write_review_sheet([make_question("sh_001"), make_question("sh_002")], sheet)
    sheet.write_text(sheet.read_text(encoding="utf-8").replace('"",""', '"no",""', 1))
    assert load_rejected(sheet) == {"sh_001"}
    run_id = run_eval(
        ["rag"],
        questions_path=questions_path,
        out_dir=tmp_path,
        answer_fn=fake_answer,
        persist=False,
        lexicon={},
        review_path=sheet,
    )
    report = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    assert len(report["results"]) == 2
    flags = {row["question_id"]: row.get("excluded_by_review") for row in report["results"]}
    assert flags == {"sh_001": True, "sh_002": None}
    assert next(r for r in report["summary"] if r["category"] == "all")["n"] == 1
    assert "excluded by review: 1" in (tmp_path / f"{run_id}.md").read_text(encoding="utf-8")


def test_no_sheet_excludes_nothing(tmp_path) -> None:
    questions_path = tmp_path / "q.jsonl"
    write_questions([make_question("sh_001")], questions_path)
    run_id = run_eval(
        ["rag"],
        questions_path=questions_path,
        out_dir=tmp_path,
        answer_fn=fake_answer,
        persist=False,
        lexicon={},
        review_path=tmp_path / "missing.csv",
    )
    report = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    assert "excluded_by_review" not in report["results"][0]
    assert report["summary"][0]["n"] == 1
    assert "excluded by review: 0" in to_markdown(run_id, summarize(report["results"]))


def _write_marks(path, marks: dict[str, tuple[str, str]]) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    for row in rows:
        row["accept"], row["note"] = marks.get(row["id"], (row["accept"], row["note"]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def test_merge_keeps_order_removed_ids_and_appends_new(tmp_path) -> None:
    path = tmp_path / "s.csv"
    write_review_sheet([make_question("sh_002"), make_question("sh_001")], path)
    note = 'a, "quoted"\nsecond line'
    _write_marks(path, {"sh_002": ("n", note), "sh_001": ("y", "ok")})
    changed = make_question("sh_001").model_copy(update={"text": "Baru?"})
    write_review_sheet([changed, make_question("sh_003")], path)
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    assert [row["id"] for row in rows] == ["sh_002", "sh_001", "sh_003"]
    assert rows[0]["accept"] == "n" and rows[0]["note"] == note
    assert rows[1]["question"] == "Baru?" and rows[1]["accept"] == "y"
    assert rows[2]["accept"] == ""


def test_load_rejected_tolerates_case_and_whitespace(tmp_path) -> None:
    path = tmp_path / "s.csv"
    ids = ["sh_001", "sh_002", "sh_003", "sh_004"]
    write_review_sheet([make_question(question_id) for question_id in ids], path)
    _write_marks(
        path,
        {"sh_001": (" N ", ""), "sh_002": ("No", ""), "sh_003": ("yes", ""), "sh_004": ("", "")},
    )
    assert load_rejected(path) == {"sh_001", "sh_002"}


def test_route_counts_skip_excluded_rows() -> None:
    def row(excluded: bool) -> dict:
        base = {"mode": "auto", "metrics": {"routed_mode": "graph"}}
        return {**base, "excluded_by_review": True} if excluded else base

    assert route_counts([row(True), row(False)]) == {"graph": 1}
