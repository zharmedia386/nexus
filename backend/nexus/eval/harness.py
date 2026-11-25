import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from statistics import fmean, median
from uuid import UUID, uuid4

from nexus.config import get_settings
from nexus.datagen.world import build_world
from nexus.db import repo
from nexus.eval.metrics import (
    abstain_correct,
    answer_match,
    entity_lexicon,
    extra_entities,
    recall_at_k,
)
from nexus.eval.questions import Question, load_questions
from nexus.eval.review import REVIEW_PATH, load_rejected
from nexus.eval.stats import bootstrap_ci, paired_diff_ci
from nexus.retrieval.answer import Answer, answer
from nexus.retrieval.modes import Mode
from nexus.retrieval.orchestrator import default_deps
from nexus.retrieval.verify import CLAIM_SPLIT_VERSION, Claim

EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
QUESTIONS_PATH = EVAL_DIR / "questions.jsonl"
RUNS_DIR = EVAL_DIR / "runs"

AnswerFn = Callable[[str, Mode, str], Answer]
Row = dict[str, object]

BASELINE_MODE = "hybrid"


def _default_answer_fn(verify: bool) -> AnswerFn:
    deps = default_deps()
    return lambda text, mode, tenant: answer(text, mode, tenant, deps=deps, verify=verify)


def claim_metrics(claims: list[Claim]) -> dict[str, float | None]:
    # Unverified (None) claims count in neither rate; uncited claims are judged False.
    judged = [claim.supported for claim in claims if claim.supported is not None]
    return {
        "unsupported_claim_rate": judged.count(False) / len(judged) if judged else None,
        "citation_precision": sum(judged) / len(judged) if judged else None,
    }


def score(
    question: Question, ans: Answer, lexicon: dict[str, str]
) -> dict[str, float | bool | int | str | None]:
    matched = precision = extra = None
    if question.gold_answers:
        # An abstention never earns credit, whatever names it echoes.
        matched = 0.0 if ans.abstained else answer_match(ans.text, question.gold_answers)
        if not ans.abstained:
            extra = extra_entities(
                ans.text,
                question.gold_answers,
                lexicon,
                question.text,
                question.support_entities,
            )
            found = matched * len(question.gold_answers)
            # None (nothing named) is excluded from the mean by design; answer_match already scores 0.
            precision = found / (found + extra) if found + extra else None
    return {
        "answer_match": matched,
        "answer_precision": precision,
        "extra_entities": extra,
        "recall_at_k": recall_at_k([hit.doc_id for hit in ans.hits], question.gold_doc_ids),
        "abstain_correct": abstain_correct(ans, question),
        "latency_ms": ans.latency_ms,
        **claim_metrics(ans.claims),
        "llm_calls": ans.llm_calls,
        "verify_calls": ans.verify_calls,
        "verify_ms": ans.verify_ms,
        "routed_mode": ans.routed_mode,
    }


def _mean(values: list[float]) -> float | None:
    return round(fmean(values), 4) if values else None


def _percentile(values: list[int], share: float) -> int:
    ordered = sorted(values)
    return ordered[max(math.ceil(share * len(ordered)) - 1, 0)]


def _match_by_question(rows: list[Row]) -> dict[tuple[str, str], dict[str, float]]:
    scores: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        metrics = row["metrics"]
        assert isinstance(metrics, dict)
        if row.get("excluded_by_review") or "error" in metrics or metrics["answer_match"] is None:
            continue
        for category in (str(row["category"]), "all"):
            scores[(str(row["mode"]), category)][str(row["question_id"])] = metrics["answer_match"]
    return scores


def paired_diffs(rows: list[Row]) -> list[Row]:
    scores = _match_by_question(rows)
    diffs: list[Row] = []
    for (mode, category), by_question in sorted(scores.items()):
        baseline = scores.get((BASELINE_MODE, category))
        if mode == BASELINE_MODE or baseline is None:
            continue
        shared = by_question.keys() & baseline.keys()
        if len(shared) < 2:
            continue
        mean, low, high = paired_diff_ci(by_question, baseline)
        diffs.append(
            {
                "mode": mode,
                "category": category,
                "n": len(shared),
                "mean_diff": round(mean, 4),
                "ci_low": round(low, 4),
                "ci_high": round(high, 4),
                "significant": low > 0 or high < 0,
            }
        )
    return diffs


def summarize(rows: list[Row]) -> list[Row]:
    match_scores = _match_by_question(rows)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    errors: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row.get("excluded_by_review"):
            continue
        metrics = row["metrics"]
        assert isinstance(metrics, dict)
        for key in ((str(row["mode"]), str(row["category"])), (str(row["mode"]), "all")):
            if "error" in metrics:
                errors[key] += 1
                groups[key]  # keep error-only groups in the table
            else:
                groups[key].append(metrics)
    summary: list[Row] = []
    for (mode, category), group in sorted(groups.items()):
        latencies = [metrics["latency_ms"] for metrics in group]
        matches = list(match_scores.get((mode, category), {}).values())
        ci_low, ci_high = bootstrap_ci(matches) if len(matches) >= 2 else (None, None)
        summary.append(
            {
                "mode": mode,
                "category": category,
                "answer_match": _mean(
                    [m["answer_match"] for m in group if m["answer_match"] is not None]
                ),
                "answer_match_ci_low": None if ci_low is None else round(ci_low, 4),
                "answer_match_ci_high": None if ci_high is None else round(ci_high, 4),
                "answer_precision": _mean(
                    [m["answer_precision"] for m in group if m["answer_precision"] is not None]
                ),
                "recall_at_k": _mean(
                    [m["recall_at_k"] for m in group if m["recall_at_k"] is not None]
                ),
                "citation_precision": _mean(
                    [m["citation_precision"] for m in group if m["citation_precision"] is not None]
                ),
                "unsupported_claim_rate": _mean(
                    [
                        m["unsupported_claim_rate"]
                        for m in group
                        if m["unsupported_claim_rate"] is not None
                    ]
                ),
                "abstain_accuracy": _mean([float(m["abstain_correct"]) for m in group]),
                "p50_ms": round(median(latencies)) if latencies else None,
                "p95_ms": _percentile(latencies, 0.95) if latencies else None,
                "mean_llm_calls": _mean([m["llm_calls"] for m in group]),
                "mean_verify_calls": _mean([m["verify_calls"] for m in group]),
                "mean_verify_ms": _mean([m["verify_ms"] for m in group]),
                "n": len(group),
                "n_errors": errors[(mode, category)],
            }
        )
    return summary


def scored_rows(rows: list[Row]) -> list[Row]:
    return [
        row
        for row in rows
        if not row.get("excluded_by_review") and row.get("answer") and "error" not in row["metrics"]  # type: ignore[operator]
    ]


def claim_counts(run: dict, base_run: dict | None = None) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    scored = scored_rows(run["results"])
    for row in scored:
        claims = row["answer"]["claims"]  # type: ignore[index]
        counts[str(row["mode"])].update(
            claims=len(claims),
            uncited=sum(not claim["chunk_ids"] for claim in claims),
            awaiting_verify=sum(claim["supported"] is None for claim in claims),
        )
    if base_run:
        # Only rows still scored in `run`, so late review exclusions apply to v1 as well.
        keys = {(row["question_id"], row["mode"]) for row in scored}
        for row in base_run["results"]:
            if (row["question_id"], row["mode"]) in keys:
                counts[row["mode"]]["claims_v1"] += len(row["answer"]["claims"])
        for count in counts.values():
            count["dropped"] = count["claims_v1"] - count["claims"]
    return {mode: dict(count) for mode, count in sorted(counts.items())}


def route_counts(rows: list[Row]) -> Counter[str]:
    return Counter(
        str(row["metrics"]["routed_mode"])  # type: ignore[index]
        for row in rows
        if not row.get("excluded_by_review")
        and row["mode"] == "auto"
        and row["metrics"].get("routed_mode")  # type: ignore[union-attr]
    )


def to_markdown(
    run_id: UUID,
    summary: list[Row],
    routes: Counter[str] | None = None,
    excluded: int = 0,
    diffs: list[Row] | None = None,
) -> str:
    columns = [
        "mode",
        "category",
        "answer_match",
        "answer_precision",
        "recall_at_k",
        "citation_precision",
        "unsupported_claim_rate",
        "abstain_accuracy",
        "p50_ms",
        "p95_ms",
        "mean_llm_calls",
        "mean_verify_calls",
        "mean_verify_ms",
        "n",
        "n_errors",
    ]
    lines = [
        f"# Eval run {run_id}",
        "",
        f"excluded by review: {excluded}",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    for row in summary:
        cells = ["-" if row[column] is None else str(row[column]) for column in columns]
        if row["answer_match_ci_low"] is not None:
            cells[2] += f" [{row['answer_match_ci_low']}, {row['answer_match_ci_high']}]"
        lines.append("| " + " | ".join(cells) + " |")
    if diffs:
        lines += [
            "",
            f"## Δ answer_match vs {BASELINE_MODE} (paired bootstrap)",
            "",
            "| mode | category | n | mean diff [low, high] | sig |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {d['mode']} | {d['category']} | {d['n']} | "
            f"{d['mean_diff']} [{d['ci_low']}, {d['ci_high']}] | {'*' if d['significant'] else ''} |"
            for d in diffs
        ]
    if routes:
        lines += ["", "## auto routed_mode", "", "| routed_mode | n |", "|---|---|"]
        lines += [f"| {route} | {count} |" for route, count in sorted(routes.items())]
    return "\n".join(lines) + "\n"


def _persist(run_id: UUID, tenant: str, config: dict[str, object], rows: list[Row]) -> None:
    with repo.connect() as conn:
        repo.ensure_tenant(conn, tenant)
        repo.insert_eval_run(conn, tenant, config, run_id)
        for row in rows:
            metrics, payload = row["metrics"], row["answer"]
            assert isinstance(metrics, dict) and isinstance(payload, dict)
            repo.insert_eval_result(
                conn, run_id, str(row["question_id"]), str(row["mode"]), metrics, payload
            )
        conn.commit()


def run_eval(
    modes: list[Mode],
    tenant: str = "demo",
    limit: int | None = None,
    *,
    questions_path: Path = QUESTIONS_PATH,
    out_dir: Path = RUNS_DIR,
    answer_fn: AnswerFn | None = None,
    persist: bool = True,
    verify: bool = True,
    lexicon: dict[str, str] | None = None,
    review_path: Path = REVIEW_PATH,
) -> UUID:
    questions = load_questions(questions_path)[:limit]
    rejected = load_rejected(review_path)
    ask = answer_fn or _default_answer_fn(verify)
    # Seed 42 matches the committed ground_truth.json; callers with another world pass its lexicon.
    names = lexicon if lexicon is not None else entity_lexicon(build_world(42))
    rows: list[Row] = []
    run_id = uuid4()
    out_dir.mkdir(parents=True, exist_ok=True)
    partial = out_dir / f"{run_id}.partial.jsonl"
    for question in questions:
        for mode in modes:
            row: Row = {
                "question_id": question.id,
                "category": question.category,
                "lang": question.lang,
                "mode": mode,
            }
            if question.id in rejected:
                row["excluded_by_review"] = True
            try:
                ans = ask(question.text, mode, tenant)
                row = {
                    **row,
                    "metrics": score(question, ans, names),
                    "answer": ans.model_dump(mode="json"),
                }
            except Exception as exc:  # noqa: BLE001 - one bad question must not discard a long run
                row = {**row, "metrics": {"error": type(exc).__name__}, "answer": {}}
            rows.append(row)
            with partial.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
    config: dict[str, object] = {
        "modes": list(modes),
        "limit": limit,
        "verify": verify,
        "claim_split_version": CLAIM_SPLIT_VERSION,
        "questions": str(questions_path),
        "settings": get_settings().model_dump(
            exclude={"LLM_API_KEY", "NEO4J_PASSWORD", "POSTGRES_PASSWORD"}
        ),
    }
    summary = summarize(rows)
    report = {
        "run_id": str(run_id),
        "tenant": tenant,
        "config": config,
        "summary": summary,
        "results": rows,
    }
    (out_dir / f"{run_id}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"{run_id}.md").write_text(
        to_markdown(
            run_id,
            summary,
            route_counts(rows),
            len(rejected & {question.id for question in questions}),
            paired_diffs(rows),
        ),
        encoding="utf-8",
    )
    # Files first so a DB failure never loses results.
    if persist:
        _persist(run_id, tenant, config, rows)
    return run_id
