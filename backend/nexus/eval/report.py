import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import fmean

from nexus.config import get_settings
from nexus.datagen.models import World
from nexus.datagen.planner import plan_documents
from nexus.eval.harness import (
    BASELINE_MODE,
    EVAL_DIR,
    claim_counts,
    paired_diffs,
    route_counts,
    scored_rows,
)
from nexus.eval.judge import CRITERIA, JUDGE_PROMPT_VERSION
from nexus.eval.questions import Question
from nexus.eval.review import load_rejected, load_rows
from nexus.eval.stats import BOOTSTRAP_N, BOOTSTRAP_SEED
from nexus.graph.extract import EXTRACT_PROMPT_VERSION
from nexus.graph.resolve import ADJUDICATE_PROMPT_VERSION
from nexus.graph.summaries import SUMMARY_PROMPT_VERSION
from nexus.retrieval.prompts import ABSTAIN_EN, ABSTAIN_ID

REPORT_DIR = EVAL_DIR.parent / "docs" / "report"
EXAMPLE_MODE = "graph_local"
N_EXAMPLES = 3
MAX_PATHS = 5
AUDIT_TITLE = re.compile(r"^# Claim audit: run (\S+) / (\S+) / (\S+)", re.MULTILINE)
AUDIT_CLASS = re.compile(r"^\*\*Audit class:\*\* \(([a-d])\)", re.MULTILINE)
AUDIT_MEANINGS = {
    "a": "verifier correct (claim not supported by its citations)",
    "b": "verifier too strict (citations do support the claim)",
    "c": "claim true in the world, wrong chunk attached",
    "d": "non-claim (header, scaffolding, meta, abstention, malformed citation)",
}
# Hand review of run 23b9a166 (Task 3 ruling): splitter-dropped lines that still carry a fact.
SPLITTER_REVIEW = {"run": "23b9a166", "dropped": 252, "with_fact": 6}
MODE_NOTES = {
    "rag": "dense top-k from Milvus, similarity threshold",
    "hybrid": "dense + keyword, RRF fusion, reranker top-N (baseline)",
    "graph_local": "question entities linked to graph nodes, then an LLM-guided traversal "
    "in Neo4j (up to 4 hops, beam 3); the source chunks of followed edges are placed first, "
    "the rest of the top-N comes from the reranker over neighbourhood + hybrid chunks; "
    "returns paths",
    "graph_global": "map-reduce over community summaries (MS GraphRAG style)",
    "auto": "LLM router picks a mode per question",
}

Row = dict[str, object]


def _cell(value: object) -> str:
    return "-" if value is None else str(value)


def _table(header: list[str], rows: Iterable[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]


def _nested(pairs: Counter[tuple[str, str]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for (outer, inner), count in sorted(pairs.items()):
        out[outer][inner] = count
    return dict(out)


def dataset_stats(
    world: World, docs_dir: Path, questions: list[Question], review_path: Path
) -> dict[str, object]:
    plans = [plan for plan in plan_documents(world) if (docs_dir / f"{plan.doc_id}.md").exists()]
    planned = {plan.doc_id for plan in plans}
    review_rows = load_rows(review_path)
    return {
        "seed": world.seed,
        "entities": dict(Counter(entity.type for entity in world.entities)),
        "edges": dict(Counter(edge.type for edge in world.edges)),
        "hidden_paths": len(world.hidden_paths),
        "name_collisions": len(world.collisions),
        "docs": _nested(Counter((plan.doc_type, plan.lang) for plan in plans)),
        "other_docs": sorted(p.stem for p in docs_dir.glob("*.md") if p.stem not in planned),
        "questions": _nested(Counter((q.category, q.lang) for q in questions)),
        "rejected": sorted(load_rejected(review_path)),
        "review_rows": len(review_rows),
        "review_marked": sum(bool(row.get("accept", "").strip()) for row in review_rows),
    }


def parse_audit(text: str) -> dict[str, object]:
    title = AUDIT_TITLE.search(text)
    classes = Counter(AUDIT_CLASS.findall(text))
    return {
        "run": title.group(1) if title else None,
        "mode": title.group(2) if title else None,
        "category": title.group(3) if title else None,
        "classes": {key: classes[key] for key in AUDIT_MEANINGS},
        "n": sum(classes.values()),
    }


def example_counts(run: dict) -> tuple[int, int]:
    match = {
        (row["question_id"], row["mode"]): row["metrics"].get("answer_match")
        for row in scored_rows(run["results"])
        if row["category"].startswith("multi_hop")
    }
    questions = {qid for qid, _ in match}
    forward = sum(
        match.get((q, EXAMPLE_MODE)) == 1 and match.get((q, BASELINE_MODE)) == 0 for q in questions
    )
    reverse = sum(
        match.get((q, BASELINE_MODE)) == 1 and match.get((q, EXAMPLE_MODE)) == 0 for q in questions
    )
    return forward, reverse


def select_examples(run: dict, n: int = N_EXAMPLES) -> list[str]:
    match = {
        (row["question_id"], row["mode"]): row["metrics"].get("answer_match")
        for row in scored_rows(run["results"])
    }
    # Hedged answers that name the gold entity and unverified answers make misleading showcases.
    showcase = {
        row["question_id"]
        for row in scored_rows(run["results"])
        if row["mode"] == EXAMPLE_MODE
        and row["category"].startswith("multi_hop")
        and not any(text in row["answer"]["text"] for text in (ABSTAIN_EN, ABSTAIN_ID))
        and any(claim["supported"] is True for claim in row["answer"]["claims"])
    }
    return sorted(
        qid
        for qid in showcase
        if match.get((qid, EXAMPLE_MODE)) == 1 and match.get((qid, BASELINE_MODE)) == 0
    )[:n]


def _mean_length(run: dict, mode: str, question_ids: set[str]) -> float | None:
    lengths = [
        len(row["answer"]["text"])
        for row in scored_rows(run["results"])
        if row["mode"] == mode and row["question_id"] in question_ids
    ]
    return round(fmean(lengths)) if lengths else None


def _order(values: Iterable[str], first: list[str]) -> list[str]:
    values = set(values)
    return [v for v in first if v in values] + sorted(values - set(first))


def _ci(row: Row | None) -> str:
    if row is None or row["answer_match"] is None:
        return "-"
    if row["answer_match_ci_low"] is None:
        return str(row["answer_match"])
    return f"{row['answer_match']} [{row['answer_match_ci_low']}, {row['answer_match_ci_high']}]"


def _diff(d: Row) -> str:
    return f"{d['mean_diff']:+} [{d['ci_low']}, {d['ci_high']}]"


def _path(path: dict) -> str:
    names, rels = path["node_names"], path["rel_types"]
    hops = "".join(f" -[{rel}]- {name}" for rel, name in zip(rels, names[1:]))
    return f"{names[0]}{hops}"


def build_report(
    run: dict,
    *,
    dataset: dict,
    questions: dict[str, str],
    graph: dict | None = None,
    judges: list[dict] | None = None,
    audit: dict | None = None,
    base_run: dict | None = None,
) -> tuple[str, dict]:
    summary: list[Row] = run["summary"]
    by_key = {(row["mode"], row["category"]): row for row in summary}
    modes = _order({row["mode"] for row in summary}, run["config"].get("modes", []))
    categories = _order({row["category"] for row in summary}, ["all"])
    diffs = paired_diffs(run["results"])
    diff_by = {(d["mode"], d["category"]): d for d in diffs}
    routes = route_counts(run["results"])
    claims = claim_counts(run, base_run)
    examples = select_examples(run)
    settings = run["config"].get("settings", {})
    split_version = run["config"].get("claim_split_version", "unknown")
    run_ids = {row["question_id"] for row in run["results"]}
    excluded = {row["question_id"] for row in run["results"] if row.get("excluded_by_review")}
    judges = judges or []
    n_pending = sum(count["awaiting_verify"] for count in claims.values())
    rescored = run["config"].get("rescored", False)
    # The hand-check numbers describe one audited run only.
    hand_checked = run["run_id"].startswith(SPLITTER_REVIEW["run"])
    splitter_share = SPLITTER_REVIEW["with_fact"] / SPLITTER_REVIEW["dropped"]
    significant = {
        mode: [d["category"] for d in diffs if d["mode"] == mode and d["significant"]]
        for mode in modes
        if mode != BASELINE_MODE
    }
    versions = {
        "extract_prompt": EXTRACT_PROMPT_VERSION,
        "summary_prompt": SUMMARY_PROMPT_VERSION,
        "adjudicate_prompt": ADJUDICATE_PROMPT_VERSION,
        "judge_prompt": JUDGE_PROMPT_VERSION,
        "claim_split": split_version,
        "verify_prompt": None,
    }
    models = {
        key: settings.get(key)
        for key in (
            "LLM_MODEL",
            "EMBEDDING_MODEL",
            "RERANKER_MODEL",
            "RERANKER_TOP_N",
            "RETRIEVAL_TOP_K",
            "SIMILARITY_THRESHOLD",
        )
    }

    lines = [f"# NEXUS evaluation report — run {run['run_id'][:8]}", ""]

    # 1 Summary
    gl, hy = by_key.get((EXAMPLE_MODE, "all")), by_key.get((BASELINE_MODE, "all"))
    headline = diff_by.get((EXAMPLE_MODE, "all"))
    answerable = {
        row["question_id"]
        for row in scored_rows(run["results"])
        if row["metrics"].get("answer_match") is not None
    }
    unanswerable = run_ids - excluded - answerable
    para = f"Run `{run['run_id']}` scored {len(run_ids - excluded)} questions across {len(modes)} modes"
    para += f" (claim split {split_version}{', rescored' if rescored else ''})."
    para += (
        f" answer_match covers the {len(answerable)} answerable questions; the "
        f"{len(unanswerable)} unanswerable ones are scored by abstain accuracy."
    )
    if gl and hy and headline:
        verdict = "significant" if headline["significant"] else "not significant"
        para += (
            f" {EXAMPLE_MODE} answer_match is {_ci(gl)} against {BASELINE_MODE} {_ci(hy)};"
            f" the paired difference is {_diff(headline)} ({verdict}, 95% bootstrap)."
        )
        per_cat = [d for d in diffs if d["mode"] == EXAMPLE_MODE and d["category"] != "all"]
        # The sign decides gain vs loss; significance alone says nothing about direction.
        gains = [d["category"] for d in per_cat if d["significant"] and d["mean_diff"] > 0]
        losses = [d["category"] for d in per_cat if d["significant"] and d["mean_diff"] < 0]
        flat = [d["category"] for d in per_cat if not d["significant"]]
        parts = []
        if gains:
            parts.append(f"significantly better on {', '.join(gains)}")
        if losses:
            parts.append(f"significantly worse on {', '.join(losses)}")
        if flat:
            parts.append(f"no significant difference on {', '.join(flat)}")
        if parts:
            para += f" Versus {BASELINE_MODE}, {EXAMPLE_MODE} is " + "; ".join(parts) + "."
    para += " Synthetic data and a single run: read §9 before quoting these numbers."
    lines += ["## 1. Summary", "", para, ""]
    lines += ["**answer_match [95% CI] by category × mode**", ""]
    lines += _table(
        ["category", *modes],
        ([c, *(_ci(by_key.get((m, c))) for m in modes)] for c in categories),
    )
    lines += [
        "",
        f"**Δ answer_match vs {BASELINE_MODE} (paired bootstrap, * = CI excludes 0)**",
        "",
    ]
    diff_modes = [m for m in modes if m != BASELINE_MODE]
    lines += _table(
        ["category", *diff_modes],
        (
            [
                c,
                *(
                    "-"
                    if (d := diff_by.get((m, c))) is None
                    else f"{_diff(d)}{' *' if d['significant'] else ''}"
                    for m in diff_modes
                ),
            ]
            for c in categories
        ),
    )
    for key, title in (("recall_at_k", "recall@k"), ("abstain_accuracy", "abstain accuracy")):
        lines += ["", f"**{title} by category × mode**", ""]
        lines += _table(
            ["category", *modes],
            ([c, *(by_key.get((m, c), {}).get(key) for m in modes)] for c in categories),
        )
    if routes:
        lines += [
            "",
            "**auto routing**: " + ", ".join(f"{k} {v}" for k, v in sorted(routes.items())),
        ]

    # 2 Dataset
    lines += ["", "## 2. Dataset", ""]
    lines += [
        f"Synthetic world, seed {dataset['seed']}: "
        + ", ".join(f"{n} {t}" for t, n in sorted(dataset["entities"].items()))
        + f" entities; {sum(dataset['edges'].values())} edges; "
        f"{dataset['hidden_paths']} planted multi-hop paths; "
        f"{dataset['name_collisions']} planted name collisions.",
        "",
    ]
    lines += _table(["edge type", "count"], sorted(dataset["edges"].items()))
    langs = sorted({lang for per in dataset["docs"].values() for lang in per})
    lines += ["", "**Documents by type × language**", ""]
    lines += _table(
        ["doc type", *langs, "total"],
        (
            [t, *(per.get(lang, 0) for lang in langs), sum(per.values())]
            for t, per in dataset["docs"].items()
        ),
    )
    if dataset["other_docs"]:
        lines += ["", f"Plus non-planned docs: {', '.join(dataset['other_docs'])}."]
    q_langs = sorted({lang for per in dataset["questions"].values() for lang in per})
    lines += ["", "**Questions by category × language (questions.jsonl)**", ""]
    lines += _table(
        ["category", *q_langs, "total", "in this run"],
        (
            [
                c,
                *(per.get(lang, 0) for lang in q_langs),
                sum(per.values()),
                len({r["question_id"] for r in run["results"] if r["category"] == c}),
            ]
            for c, per in dataset["questions"].items()
        ),
    )
    lines += [
        "",
        (
            f"Review exclusions: {len(excluded)} questions excluded in this run; "
            f"review sheet has {len(dataset['rejected'])} rejected, "
            f"{dataset['review_marked']} of {dataset['review_rows']} rows marked by a human."
        ),
    ]

    # 3 Method
    lines += ["", "## 3. Method", ""]
    lines += [f"- **{m}**: {MODE_NOTES.get(m, '')}" for m in modes]
    lines += [
        "",
        (
            "Fairness rules (design): every mode shares the chunker, embedder, reranker, answer "
            "prompt and top-N, except graph_global, which answers via map-reduce over community "
            "summaries (its map calls are reported as cost, not hidden)."
        ),
        "",
    ]
    lines += _table(["setting", "value"], models.items())
    lines += [
        "",
        "**Version constants** (from current code; not recorded in the run file; the verify prompt has no version constant)",
        "",
    ]
    lines += _table(["constant", "value"], versions.items())
    lines += [
        "",
        (
            f"N per mode: {by_key.get((modes[0], 'all'), {}).get('n')} questions; "
            "metrics: answer_match (gold entity mentions), recall@k (gold docs in retrieved), "
            "abstain accuracy, citation precision (verifier). "
            f"CIs: {BOOTSTRAP_N}-sample bootstrap, seed {BOOTSTRAP_SEED}."
        ),
    ]

    # 4 Cost
    lines += ["", "## 4. Cost (all categories)", ""]
    cost_keys = ["p50_ms", "p95_ms", "mean_llm_calls", "mean_verify_calls", "mean_verify_ms"]
    lines += _table(
        ["mode", *cost_keys, "total LLM calls"],
        (
            [
                m,
                *(by_key.get((m, "all"), {}).get(k) for k in cost_keys),
                sum(
                    row["metrics"]["llm_calls"]
                    for row in scored_rows(run["results"])
                    if row["mode"] == m
                ),
            ]
            for m in modes
        ),
    )

    # 5 Graph quality
    lines += ["", "## 5. Graph quality", ""]
    if graph:
        rel, er = graph["relations"], graph["er"]
        lines += [
            (
                f"Scored over {graph['docs']} docs against the world ground truth "
                f"(file timestamp {graph['timestamp']})."
            ),
            "",
        ]
        lines += _table(
            ["metric", "precision", "recall", "f1", "support"],
            (
                [name, s["precision"], s["recall"], s["f1"], s["support"]]
                for name, s in (
                    ("entities (macro)", graph["entity_macro"]),
                    ("entities (micro)", graph["entity_micro"]),
                    ("relations (macro)", rel["macro"]),
                    ("relations (micro)", rel["micro"]),
                    ("entity resolution", {**er, "support": "-"}),
                )
            ),
        )
        lines += ["", "**Relations by type**", ""]
        lines += _table(
            ["type", "precision", "recall", "f1", "support"],
            (
                [t, s["precision"], s["recall"], s["f1"], s["support"]]
                for t, s in rel["by_type"].items()
            ),
        )
        lines += [
            "",
            (
                f"Temporal accuracy {rel['temporal_accuracy']} over {rel['temporal_support']} dated "
                f"relations; {er['collision_merges']} entity-resolution collision merges; ticker links "
                f"{er['ticker_links']}/{er['ticker_total']}; {graph['dropped_unverified']} extracted "
                f"edges dropped as unverified."
            ),
        ]
    else:
        lines += ["Not provided (pass `--graph`)."]

    # 6 Evidence quality
    lines += ["", "## 6. Evidence quality", ""]
    has_v1 = base_run is not None
    lines += _table(
        [
            "mode",
            "citation_precision",
            "unsupported_claim_rate",
            "claims",
            "uncited",
            "awaiting re-verify",
            *(["dropped by splitter"] if has_v1 else []),
        ],
        (
            [
                m,
                by_key.get((m, "all"), {}).get("citation_precision"),
                by_key.get((m, "all"), {}).get("unsupported_claim_rate"),
                claims.get(m, {}).get("claims", 0),
                claims.get(m, {}).get("uncited", 0),
                claims.get(m, {}).get("awaiting_verify", 0),
                *([claims.get(m, {}).get("dropped", 0)] if has_v1 else []),
            ]
            for m in modes
        ),
    )
    lines += [
        "",
        "Uncited claims count as unsupported; claims awaiting re-verify count in neither rate.",
    ]
    if split_version not in ("v1", "unknown"):
        dropped = sum(c.get("dropped", 0) for c in claims.values()) if has_v1 else None
        lines += [
            "",
            f"Claim splitter {split_version} skips non-claim lines (headings, step labels, "
            f"abstentions)"
            + (f"; it dropped {dropped} lines in this run." if has_v1 else ".")
            + (
                f" A hand check of the {SPLITTER_REVIEW['dropped']} lines dropped in this run "
                f"found {SPLITTER_REVIEW['with_fact']} ({splitter_share:.1%}) that carry an "
                "uncited fact, so unsupported rates are slightly optimistic."
                if hand_checked
                else " The dropped lines of this run were not hand-checked."
            ),
        ]
    if audit:
        lines += [
            "",
            (
                f"**Human audit** of {audit['n']} sampled unsupported claims "
                f"({audit['mode']} / {audit['category']}, run {str(audit['run'])[:8]})"
            ),
            "",
        ]
        lines += _table(
            ["class", "meaning", "count"],
            ([k, AUDIT_MEANINGS[k], v] for k, v in audit["classes"].items()),
        )

    # 7 Global questions
    lines += ["", "## 7. Global (thematic) questions", ""]
    judge_rows = []
    for judge in judges:
        judged = {row["question_id"] for row in judge["results"]}
        length_a = _mean_length(run, judge["mode_a"], judged)
        length_b = _mean_length(run, judge["mode_b"], judged)
        judge_rows.append(
            {
                "mode_a": judge["mode_a"],
                "mode_b": judge["mode_b"],
                "categories": judge["categories"],
                "judge_prompt_version": judge["judge_prompt_version"],
                "win_rates": judge["win_rates"],
                "mean_chars": {judge["mode_a"]: length_a, judge["mode_b"]: length_b},
            }
        )
        lines += [
            (
                f"**A = {judge['mode_a']} vs B = {judge['mode_b']}** "
                f"(categories: {', '.join(judge['categories'] or ['all'])}; "
                f"judge prompt v{judge['judge_prompt_version']}; mean answer length "
                f"{length_a} vs {length_b} chars)"
            ),
            "",
        ]
        lines += _table(
            ["criterion", "A wins", "B wins", "ties", "n", "errors"],
            (
                [c, r["a_wins"], r["b_wins"], r["ties"], r["n"], r["errors"]]
                for c, r in judge["win_rates"].items()
                if c in CRITERIA
            ),
        )
        lines.append("")
    if not judges:
        thematic_total = sum(dataset["questions"].get("thematic", {}).values())
        thematic_run = len(
            {r["question_id"] for r in run["results"] if r["category"] == "thematic"}
        )
        lines += [
            (
                f"Not run. questions.jsonl has {thematic_total} thematic questions; "
                f"{thematic_run} of them are in this run."
            ),
        ]

    # 8 Examples
    lines += ["", "## 8. Examples", ""]
    rows = {(r["question_id"], r["mode"]): r for r in run["results"]}
    forward, reverse = example_counts(run)
    lines += [
        (
            f"Selection rule: the first {N_EXAMPLES} multi-hop question ids (sorted) where "
            f"{EXAMPLE_MODE} matched the gold answer and {BASELINE_MODE} did not, excluding "
            "abstaining or hedged answers and requiring at least one supported claim. "
            f"Across all multi-hop questions, {EXAMPLE_MODE} matched where {BASELINE_MODE} did not "
            f"on {forward}; the reverse ({BASELINE_MODE} matched, {EXAMPLE_MODE} did not) on "
            f"{reverse}."
        ),
    ]
    for qid in examples:
        answer = rows[(qid, EXAMPLE_MODE)]["answer"]
        lines += ["", f"### {qid} ({rows[(qid, EXAMPLE_MODE)]['category']})", ""]
        lines += [f"**Question:** {questions.get(qid, '?')}", "", f"**{EXAMPLE_MODE} answer:**", ""]
        lines += [f"> {line}" if line else ">" for line in answer["text"].splitlines()]
        lines += ["", "**Claims:**", ""]
        for claim in answer["claims"]:
            verdict = {True: "supported", False: "unsupported", None: "awaiting verify"}[
                claim["supported"]
            ]
            cites = ", ".join(claim["chunk_ids"]) or "no citation"
            lines.append(f"- [{verdict}] {claim['text']} ({cites})")
        paths = answer.get("graph_paths") or []
        lines += ["", f"**Graph paths** ({len(paths)}):", ""]
        lines += [f"- {_path(p)}" for p in paths[:MAX_PATHS]]
        if len(paths) > MAX_PATHS:
            lines.append(f"- … {len(paths) - MAX_PATHS} more")
    if not examples:
        lines += ["", "None in this run."]

    # 9 Caveats
    gl_n = {c: by_key[(EXAMPLE_MODE, c)]["n"] for c in categories if (EXAMPLE_MODE, c) in by_key}
    widths = [
        row["answer_match_ci_high"] - row["answer_match_ci_low"]
        for row in summary
        if row["answer_match_ci_low"] is not None and row["category"] != "all"
    ]
    gg_single = by_key.get(("graph_global", "single_hop"))
    hy_single = by_key.get((BASELINE_MODE, "single_hop"))
    caveats = [
        (
            f"**Synthetic data, upper bound.** Documents and questions were generated from a "
            f"planted world; the documents were generated with the project's gateway model "
            f"({get_settings().LLM_MODEL}, LLM_MODEL at report time; datagen stores no model "
            f"provenance), the same family that extracts the graph and answers "
            f"({settings.get('LLM_MODEL')} in this run). Real corpora will likely score lower."
        ),
        "**Judge = same model family** as the generator, and LLM judges favour longer answers; "
        "verdicts count only when both answer orders agree. "
        + ("Mean answer lengths are listed in §7." if judges else "No judge run in this report."),
        "**Single run, temperature 0.** No run-to-run variance is measured.",
        (
            "**answer_match is a mention check**: an answer that names the gold entity while "
            "hedging or declining to commit still scores 1. §8 examples are picked by rule, not by "
            "hand: they skip answers carrying the abstention phrase and need a supported claim, "
            "but a hedge worded another way can still get through."
        ),
        "**Small n per category** ("
        + ", ".join(f"{c} {n}" for c, n in gl_n.items() if c != "all")
        + ")"
        + (f"; widest per-category 95% CI spans {max(widths):.2f}." if widths else "."),
    ]
    if split_version not in ("v1", "unknown"):
        caveats.append(
            f"**Claim splitter {split_version}** drops non-claim lines; "
            + (
                f"about {splitter_share:.0%} of dropped lines carried an uncited fact in a hand "
                "check (§6)."
                if hand_checked
                else "this run's dropped lines were not hand-checked."
            )
        )
    if n_pending:
        caveats.append(
            f"**{n_pending} cited claims await re-verification**; they are excluded from "
            "citation rates."
        )
    if graph:
        caveats.append(
            f"**{graph['er']['collision_merges']} entity-resolution collision merges**: distinct "
            "people sharing a name were merged, which can create false graph paths."
        )
    if gg_single and hy_single:
        caveats.append(
            f"**graph_global is weak on factual questions by design**: it answers from community "
            f"summaries (single_hop answer_match {gg_single['answer_match']} vs {BASELINE_MODE} "
            f"{hy_single['answer_match']}); its target is thematic questions."
        )
    if dataset["review_marked"] == 0:
        caveats.append(
            "**Questions not yet human-reviewed**: gold answers are generated from the world "
            "graph; no review-sheet rows are marked."
        )
    lines += ["", "## 9. Caveats", "", *(f"- {c}" for c in caveats)]

    data = {
        "run_id": run["run_id"],
        "rescored": rescored,
        "claim_split_version": split_version,
        "models": models,
        "versions": versions,
        "summary": summary,
        "diffs": diffs,
        "significant_categories": significant,
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "routes": dict(routes),
        "claims": claims,
        "awaiting_verify": n_pending,
        "graph": graph,
        "judges": judge_rows,
        "audit": audit,
        "dataset": dataset,
        "examples": examples,
        "example_counts": {"graph_local_only": forward, "hybrid_only": reverse},
    }
    return "\n".join(lines) + "\n", data


def write_report(
    run_path: Path,
    *,
    world: World,
    docs_dir: Path,
    questions: list[Question],
    review_path: Path,
    graph_path: Path | None = None,
    judge_paths: list[Path] | None = None,
    audit_path: Path | None = None,
    base_run_path: Path | None = None,
    out_dir: Path = REPORT_DIR,
) -> Path:
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    markdown, data = build_report(
        load(run_path),
        dataset=dataset_stats(world, docs_dir, questions, review_path),
        questions={q.id: q.text for q in questions},
        graph=load(graph_path) if graph_path else None,
        judges=[load(path) for path in judge_paths or []],
        audit=parse_audit(audit_path.read_text(encoding="utf-8")) if audit_path else None,
        base_run=load(base_run_path) if base_run_path else None,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval-report.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    path = out_dir / "eval-report.md"
    path.write_text(markdown, encoding="utf-8")
    return path
