import csv
from pathlib import Path

from nexus.eval.questions import Question

REVIEW_PATH = Path(__file__).resolve().parents[3] / "eval" / "review" / "questions.csv"
COLUMNS = ["id", "category", "lang", "question", "gold_answers", "gold_doc_ids", "accept", "note"]
REJECT_MARKS = {"n", "no", "x"}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_rows(path: Path = REVIEW_PATH) -> list[dict[str, str]]:
    return _read(path) if path.exists() else []


def write_review_sheet(questions: list[Question], path: Path = REVIEW_PATH) -> None:
    # Existing rows keep their order and human marks, even for ids no longer generated.
    rows = {row["id"]: row for row in _read(path)} if path.exists() else {}
    for question in questions:
        kept = rows.get(question.id, {})
        rows[question.id] = {
            "id": question.id,
            "category": question.category,
            "lang": question.lang,
            "question": question.text,
            "gold_answers": " | ".join(forms[0] for forms in question.gold_answers),
            "gold_doc_ids": " | ".join(question.gold_doc_ids),
            "accept": kept.get("accept", ""),
            "note": kept.get("note", ""),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, COLUMNS, quoting=csv.QUOTE_ALL, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows.values())


def load_rejected(path: Path = REVIEW_PATH) -> set[str]:
    return {
        row["id"]
        for row in load_rows(path)
        if row.get("accept", "").strip().lower() in REJECT_MARKS
    }
