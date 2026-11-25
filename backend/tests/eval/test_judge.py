import json
from pathlib import Path

from nexus.eval.judge import CRITERIA, CriterionVerdict, JudgeResponse, judge_pair, run_judge
from nexus.eval.questions import Question
from nexus.llm import GatewayError


def _response(**winners: str) -> JudgeResponse:
    fields = {c: CriterionVerdict(winner=winners.get(c, "tie"), reason="r") for c in CRITERIA}
    return JudgeResponse(**fields)


def _scripted(*responses: JudgeResponse | Exception):
    queue = list(responses)

    def llm(messages, schema, **kwargs):
        assert kwargs["temperature"] == 0.0 and kwargs["timeout"] == 120
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return llm


def test_order_disagreement_is_tie():
    # Position bias: "Answer 1" wins in both orders, so the underlying winner differs.
    llm = _scripted(_response(directness="1"), _response(directness="1"))
    assert judge_pair("q", "a", "b", llm=llm)["directness"] == "tie"


def test_consistent_verdict_counts():
    llm = _scripted(
        _response(diversity="1", empowerment="2"), _response(diversity="2", empowerment="1")
    )
    verdicts = judge_pair("q", "a", "b", llm=llm)
    assert verdicts["diversity"] == "A"
    assert verdicts["empowerment"] == "B"
    assert verdicts["comprehensiveness"] == "tie"


def test_gateway_error_is_tie_and_counted(tmp_path: Path):
    assert set(judge_pair("q", "a", "b", llm=_scripted(GatewayError("down"))).values()) == {"tie"}
    run_path = _write_run(tmp_path, {"q1": ("x", "y")})

    def failing(messages, schema, **kwargs):
        raise GatewayError("down")

    report = _report(run_judge(run_path, "a", "b", llm=failing, **_paths(tmp_path)))
    rates = report["win_rates"]["directness"]
    assert (rates["errors"], rates["n"], rates["ties"]) == (1, 0, 0)
    assert report["results"][0]["error"] is True


def test_win_rates_sum(tmp_path: Path):
    answers = {f"q{n}": (f"a{n}", f"b{n}") for n in range(5)}
    answers["q5"] = ("only-a", None)
    answers["q6"] = ("x", "")
    run_path = _write_run(tmp_path, answers, errored="q4")

    def llm(messages, schema, **kwargs):
        # Answer 1 wins when it is an "a*" answer, regardless of order.
        first = messages[1]["content"].split("Answer 1:\n")[1].startswith("a")
        return _response(**dict.fromkeys(CRITERIA, "1" if first else "2"))

    report = _report(run_judge(run_path, "a", "b", llm=llm, **_paths(tmp_path)))
    assert report["excluded_missing"] == 3
    assert report["skipped_rejected"] == 1
    assert [r["question_id"] for r in report["results"]] == ["q0", "q1", "q2", "q3"]
    for rates in report["win_rates"].values():
        assert rates["a_wins"] + rates["b_wins"] + rates["ties"] == rates["n"] == 4
        assert rates["a_wins"] == 4


def _paths(tmp_path: Path) -> dict:
    return {"questions_path": tmp_path / "q.jsonl", "review_path": tmp_path / "review.csv"}


def _report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_run(tmp_path: Path, answers: dict, errored: str | None = None) -> Path:
    questions = [
        Question(
            id=qid,
            lang="en",
            category="thematic",
            text=f"text {qid}",
            gold_answers=[],
            gold_doc_ids=[],
        )
        for qid in [*answers, "q_rej"]
    ]
    (tmp_path / "q.jsonl").write_text(
        "\n".join(q.model_dump_json() for q in questions) + "\n", encoding="utf-8"
    )
    (tmp_path / "review.csv").write_text("id,accept\nq_rej,n\n", encoding="utf-8")
    rows = []
    for qid, pair in answers.items():
        for mode, text in zip(("a", "b"), pair, strict=True):
            if text is None:
                continue
            metrics = {"error": "X"} if qid == errored and mode == "b" else {}
            rows.append(
                {
                    "question_id": qid,
                    "category": "thematic",
                    "mode": mode,
                    "metrics": metrics,
                    "answer": {"text": text},
                }
            )
    rows.append(
        {
            "question_id": "q_rej",
            "category": "thematic",
            "mode": "a",
            "metrics": {},
            "answer": {"text": "z"},
        }
    )
    run_path = tmp_path / "run1.json"
    run_path.write_text(json.dumps({"run_id": "run1", "results": rows}), encoding="utf-8")
    return run_path
