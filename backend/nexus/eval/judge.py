import json
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

from nexus.eval.harness import QUESTIONS_PATH
from nexus.eval.questions import load_questions
from nexus.eval.review import REVIEW_PATH, load_rejected
from nexus.llm import GatewayError, chat_json

Criterion = Literal["comprehensiveness", "diversity", "empowerment", "directness"]
Verdict = Literal["A", "B", "tie"]
CRITERIA: tuple[Criterion, ...] = get_args(Criterion)
# Bump when the judge prompt or schema changes; applies to all modes.
JUDGE_PROMPT_VERSION = 1
JUDGE_TIMEOUT = 120

JUDGE_SYSTEM = (
    "You are an impartial judge comparing two answers to the same question. "
    "For each criterion, pick the better answer or say tie.\n"
    "Criteria:\n"
    "- comprehensiveness: how much detail does the answer provide to cover all aspects "
    "and details of the question?\n"
    "- diversity: how varied and rich is the answer in providing different perspectives "
    "and insights on the question?\n"
    "- empowerment: how well does the answer help the reader understand the topic "
    "and make informed judgements?\n"
    "- directness: how specifically and clearly does the answer address the question, "
    "concisely?\n"
    "Judge each criterion independently. Do not favor an answer for its position or length "
    "alone. Reply with the winner per criterion as "
    '"1", "2" or "tie" plus a short reason.'
)
JUDGE_USER = "Question: {question}\n\nAnswer 1:\n{first}\n\nAnswer 2:\n{second}"


class CriterionVerdict(BaseModel):
    winner: Literal["1", "2", "tie"]
    reason: str


class JudgeResponse(BaseModel):
    comprehensiveness: CriterionVerdict
    diversity: CriterionVerdict
    empowerment: CriterionVerdict
    directness: CriterionVerdict


JudgeFn = Callable[..., JudgeResponse]


def _ask(question: str, first: str, second: str, llm: JudgeFn) -> JudgeResponse:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": JUDGE_USER.format(question=question, first=first, second=second),
        },
    ]
    return llm(messages, JudgeResponse, temperature=0.0, timeout=JUDGE_TIMEOUT)


def _judge(
    question: str, answer_a: str, answer_b: str, llm: JudgeFn
) -> tuple[dict[Criterion, Verdict], dict[str, dict[str, str]]]:
    forward = _ask(question, answer_a, answer_b, llm)
    swapped = _ask(question, answer_b, answer_a, llm)
    to_ab: dict[Literal["1", "2", "tie"], Verdict] = {"1": "A", "2": "B", "tie": "tie"}
    to_ba: dict[Literal["1", "2", "tie"], Verdict] = {"1": "B", "2": "A", "tie": "tie"}
    verdicts: dict[Criterion, Verdict] = {}
    reasons: dict[str, dict[str, str]] = {}
    for criterion in CRITERIA:
        first, second = getattr(forward, criterion), getattr(swapped, criterion)
        pick_first, pick_second = to_ab[first.winner], to_ba[second.winner]
        # A verdict counts only when both orders pick the same underlying answer.
        verdicts[criterion] = pick_first if pick_first == pick_second else "tie"
        reasons[criterion] = {"a_then_b": first.reason, "b_then_a": second.reason}
    return verdicts, reasons


def judge_pair(
    question: str, answer_a: str, answer_b: str, *, llm: JudgeFn = chat_json
) -> dict[Criterion, Verdict]:
    try:
        return _judge(question, answer_a, answer_b, llm)[0]
    except GatewayError:
        return dict.fromkeys(CRITERIA, "tie")


def _answer_text(row: dict) -> str | None:
    if "error" in row.get("metrics", {}):
        return None
    return row.get("answer", {}).get("text") or None


def _judge_row(job: tuple[str, str, str, str], llm: JudgeFn) -> dict:
    question_id, question, answer_a, answer_b = job
    try:
        verdicts, reasons = _judge(question, answer_a, answer_b, llm)
        return {"question_id": question_id, "verdicts": verdicts, "reasons": reasons}
    except GatewayError:
        return {
            "question_id": question_id,
            "verdicts": dict.fromkeys(CRITERIA, "tie"),
            "error": True,
        }


def win_rates(rows: list[dict]) -> dict[str, dict[str, float | int]]:
    rates: dict[str, dict[str, float | int]] = {}
    judged = [row for row in rows if not row.get("error")]
    for criterion in CRITERIA:
        counts = Counter(row["verdicts"][criterion] for row in judged)
        total = len(judged)
        rates[criterion] = {
            "a_wins": counts["A"],
            "b_wins": counts["B"],
            "ties": counts["tie"],
            "n": total,
            "errors": len(rows) - total,
            "a_win_rate": round(counts["A"] / total, 4) if total else 0.0,
            "b_win_rate": round(counts["B"] / total, 4) if total else 0.0,
        }
    return rates


def run_judge(
    run_path: Path,
    mode_a: str,
    mode_b: str,
    categories: list[str] | None = None,
    *,
    llm: JudgeFn = chat_json,
    workers: int = 4,
    questions_path: Path = QUESTIONS_PATH,
    review_path: Path = REVIEW_PATH,
    out_dir: Path | None = None,
) -> Path:
    run = json.loads(run_path.read_text(encoding="utf-8"))
    questions = {q.id: q for q in load_questions(questions_path)}
    rejected = load_rejected(review_path)
    by_key = {(row["question_id"], row["mode"]): row for row in run["results"]}
    jobs: list[tuple[str, str, str, str]] = []
    skipped_rejected = excluded_missing = 0
    for question_id in sorted({row["question_id"] for row in run["results"]}):
        question = questions.get(question_id)
        if question is None or (categories and question.category not in categories):
            continue
        if question_id in rejected:
            skipped_rejected += 1
            continue
        pair = [by_key.get((question_id, mode)) for mode in (mode_a, mode_b)]
        texts = [_answer_text(row) if row else None for row in pair]
        if texts[0] is None or texts[1] is None:
            excluded_missing += 1
            continue
        jobs.append((question_id, question.text, texts[0], texts[1]))
    # The LLM runs only in workers; map keeps rows ordered by question id.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda job: _judge_row(job, llm), jobs))
    report = {
        "run_id": run["run_id"],
        "mode_a": mode_a,
        "mode_b": mode_b,
        "categories": categories,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "skipped_rejected": skipped_rejected,
        "excluded_missing": excluded_missing,
        "win_rates": win_rates(rows),
        "results": rows,
    }
    out_path = (out_dir or run_path.parent) / f"judge-{run_path.stem}-{mode_a}-vs-{mode_b}.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out_path
