import copy
import json
import random
from collections.abc import Callable
from pathlib import Path

from nexus.eval.harness import (
    EVAL_DIR,
    claim_counts,
    claim_metrics,
    paired_diffs,
    route_counts,
    summarize,
    to_markdown,
)
from nexus.eval.review import REVIEW_PATH, load_rejected
from nexus.retrieval.verify import CLAIM_SPLIT_VERSION, Claim, split_claims

AUDIT_DIR = EVAL_DIR / "audit"

ChunkFetcher = Callable[[list[str]], dict[str, str]]
Verifier = Callable[[list[Claim], dict[str, str]], tuple[list[Claim], int]]


def sample_unsupported(
    run: dict, mode: str, category: str, n: int, seed: int = 42
) -> list[dict[str, object]]:
    pool = [
        {"question_id": row["question_id"], "claim": claim}
        for row in run["results"]
        if row["mode"] == mode and row["category"] == category and row.get("answer")
        for claim in row["answer"].get("claims", [])
        # None means the verifier call failed, so there is no verdict to audit.
        if claim.get("supported") is False
    ]
    return random.Random(seed).sample(pool, min(n, len(pool)))


def write_audit(
    run_path: Path,
    mode: str,
    category: str,
    n: int,
    questions: dict[str, str],
    fetch_chunks: ChunkFetcher,
    seed: int = 42,
    out_dir: Path = AUDIT_DIR,
) -> Path:
    run = json.loads(run_path.read_text(encoding="utf-8"))
    sample = sample_unsupported(run, mode, category, n, seed)
    chunk_ids = sorted({cid for item in sample for cid in item["claim"]["chunk_ids"]})
    chunk_text = fetch_chunks(chunk_ids) if chunk_ids else {}
    lines = [
        f"# Claim audit: run {run['run_id']} / {mode} / {category}",
        "",
        f"Sampled {len(sample)} unsupported claims (seed {seed}).",
    ]
    for number, item in enumerate(sample, 1):
        claim = item["claim"]
        lines += [
            "",
            f"## {number}. {item['question_id']}",
            "",
            f"**Question:** {questions.get(item['question_id'], '?')}",
            "",
            f"**Claim:** {claim['text']}",
            "",
            f"**Verifier:** {'supported' if claim['supported'] else 'not supported'}",
            "",
        ]
        if not claim["chunk_ids"]:
            lines.append("_No citations._")
        for cid in claim["chunk_ids"]:
            text = chunk_text.get(cid, "_(chunk not found)_")
            lines += [f"**[{cid}]**", "", *(f"> {line}" for line in text.splitlines()), ""]
        lines += ["", "human: [ ] supported [ ] not supported"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"claims-{run['run_id'][:8]}-{mode}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rescore_claims(answer: dict, verify: Verifier | None) -> tuple[list[Claim], int]:
    stored = {(c["text"], tuple(c["chunk_ids"])): c["supported"] for c in answer["claims"]}
    chunk_text = {hit["chunk_id"]: hit["text"] for hit in answer["hits"]}
    claims = split_claims(answer["text"])
    pending: list[int] = []
    for index, claim in enumerate(claims):
        key = (claim.text, tuple(claim.chunk_ids))
        if key in stored:
            claim.supported = stored[key]
        elif claim.chunk_ids and all(cid in chunk_text for cid in claim.chunk_ids):
            claim.supported = None
            pending.append(index)
        # else: uncited or cites a non-hit id, unsupported as split_claims left it.
    if verify and pending:
        verified, _ = verify([claims[i] for i in pending], chunk_text)
        for index, claim in zip(pending, verified):
            claims[index] = claim
    return claims, sum(claim.supported is None for claim in claims)


def rescore_run(
    run_path: Path, verify: Verifier | None = None, review_path: Path = REVIEW_PATH
) -> tuple[Path, int]:
    run = json.loads(run_path.read_text(encoding="utf-8"))
    # The current review sheet wins, so rejections made after the run reach every aggregate.
    rejected = load_rejected(review_path)
    for row in run["results"]:
        if row["question_id"] in rejected:
            row["excluded_by_review"] = True
        else:
            row.pop("excluded_by_review", None)
    base_run = copy.deepcopy(run)
    unverified = 0
    for row in run["results"]:
        answer = row.get("answer")
        if not answer or "error" in row["metrics"]:
            continue
        claims, pending = _rescore_claims(answer, verify)
        unverified += pending
        answer["claims"] = [claim.model_dump(mode="json") for claim in claims]
        row["metrics"].update(claim_metrics(claims))
    run["summary"] = summarize(run["results"])
    run["config"] = {
        **run["config"],
        "claim_split_version": CLAIM_SPLIT_VERSION,
        "rescored": True,
    }
    stem = run_path.name.removesuffix(".json")
    out = run_path.with_name(f"{stem}.rescored.json")
    out.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    excluded = sum(bool(row.get("excluded_by_review")) for row in run["results"])
    markdown = to_markdown(
        run["run_id"],
        run["summary"],
        route_counts(run["results"]),
        excluded,
        paired_diffs(run["results"]),
    )
    lines = [
        f"## Claims (split {CLAIM_SPLIT_VERSION})",
        "",
        "| mode | claims v1 | claims v2 | skipped | uncited v2 | awaiting re-verify |",
        "|---|---|---|---|---|---|",
    ]
    for mode, c in claim_counts(run, base_run).items():
        lines.append(
            f"| {mode} | {c['claims_v1']} | {c['claims']} | {c['dropped']} | {c['uncited']} "
            f"| {c['awaiting_verify']} |"
        )
    out.with_suffix(".md").write_text(markdown + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return out, unverified
