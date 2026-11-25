import random

from nexus.eval.harness import paired_diffs, summarize
from nexus.eval.report import build_report, parse_audit, select_examples
from nexus.retrieval.prompts import ABSTAIN_EN, ABSTAIN_ID

DATASET = {
    "seed": 42,
    "entities": {"Person": 2},
    "edges": {"OWNS_STAKE": 1},
    "hidden_paths": 1,
    "name_collisions": 0,
    "docs": {"news": {"id": 1}},
    "other_docs": [],
    "questions": {"multi_hop_2": {"en": 5}, "single_hop": {"id": 2}},
    "rejected": [],
    "review_rows": 7,
    "review_marked": 0,
}
# (question_id, category, graph_local match, hybrid match)
GRID = [
    ("m2_005", "multi_hop_2", 1.0, 0.0),
    ("m2_001", "multi_hop_2", 1.0, 0.0),
    ("m2_003", "multi_hop_2", 0.0, 0.0),
    ("m2_002", "multi_hop_2", 1.0, 0.0),
    ("m2_004", "multi_hop_2", 1.0, 1.0),
    ("sh_001", "single_hop", 1.0, 0.0),
    ("sh_002", "single_hop", 1.0, 1.0),
]


def _row(qid: str, category: str, mode: str, match: float) -> dict:
    return {
        "question_id": qid,
        "category": category,
        "lang": "en",
        "mode": mode,
        "metrics": {
            "answer_match": match,
            "answer_precision": match,
            "recall_at_k": 0.5,
            "abstain_correct": True,
            "latency_ms": 100 if mode == "hybrid" else 300,
            "citation_precision": 1.0,
            "unsupported_claim_rate": 0.0,
            "llm_calls": 1 if mode == "hybrid" else 3,
            "verify_calls": 1,
            "verify_ms": 50,
            "routed_mode": None,
        },
        "answer": {
            "text": f"{qid} answer by {mode}",
            "claims": [{"text": "c", "chunk_ids": ["doc_001:0000"], "supported": True}],
            "graph_paths": [
                {"node_names": ["PT A", "Budi"], "rel_types": ["SERVES_AS"], "chunk_ids": []}
            ],
        },
    }


def make_run(seed: int | None = None) -> dict:
    results = [
        _row(qid, category, mode, match)
        for qid, category, local, hybrid in GRID
        for mode, match in (("graph_local", local), ("hybrid", hybrid))
    ]
    if seed is not None:
        random.Random(seed).shuffle(results)
    return {
        "run_id": "abcdef12-0000-0000-0000-000000000000",
        "config": {"modes": ["hybrid", "graph_local"], "settings": {"LLM_MODEL": "m"}},
        "summary": summarize(results),
        "results": results,
    }


def _build(run: dict, **kwargs) -> tuple[str, dict]:
    return build_report(run, dataset=DATASET, questions={"m2_001": "Who?"}, **kwargs)


def test_report_numbers_match_run() -> None:
    run = make_run()
    markdown, data = _build(run)
    assert data["summary"] == run["summary"]
    for row in run["summary"]:
        if row["answer_match"] is not None:
            ci = f"{row['answer_match']} [{row['answer_match_ci_low']}, "
            assert ci in markdown
    for diff in paired_diffs(run["results"]):
        assert f"{diff['mean_diff']:+} [{diff['ci_low']}, {diff['ci_high']}]" in markdown
    assert data["diffs"] == paired_diffs(run["results"])
    graph_local_all = next(
        r for r in run["summary"] if (r["mode"], r["category"]) == ("graph_local", "all")
    )
    assert f"| graph_local | {graph_local_all['p50_ms']} | " in markdown
    assert "| graph_local | 1.0 | 0.0 | 7 | 0 | 0 |" in markdown


def test_report_without_judge_section() -> None:
    markdown, data = _build(make_run())
    section = markdown.split("## 7.")[1].split("## 8.")[0]
    assert "Not run." in section and data["judges"] == []
    assert "No judge run in this report." in markdown

    rates = {
        c: {"a_wins": 3, "b_wins": 1, "ties": 2, "n": 6, "errors": 0}
        for c in ("comprehensiveness", "diversity", "empowerment", "directness")
    }
    judge = {
        "mode_a": "graph_local",
        "mode_b": "hybrid",
        "categories": ["multi_hop_2"],
        "judge_prompt_version": 1,
        "win_rates": rates,
        "results": [{"question_id": "m2_001"}],
    }
    markdown, data = _build(make_run(), judges=[judge])
    section = markdown.split("## 7.")[1].split("## 8.")[0]
    assert "Not run." not in section
    assert "| diversity | 3 | 1 | 2 | 6 | 0 |" in section
    assert data["judges"][0]["mean_chars"] == {"graph_local": 28, "hybrid": 23}


def test_examples_selected_deterministically() -> None:
    expected = ["m2_001", "m2_002", "m2_005"]
    assert select_examples(make_run()) == expected
    assert all(select_examples(make_run(seed)) == expected for seed in range(5))
    markdown, data = _build(make_run(3))
    assert data["examples"] == expected
    assert "**Question:** Who?" in markdown
    assert "- PT A -[SERVES_AS]- Budi" in markdown
    assert "sh_001 (" not in markdown


def test_parse_audit_counts_classes() -> None:
    text = (
        "# Claim audit: run abc / graph_local / multi_hop_3\n\n"
        "**Audit class:** (d) step header\n\n**Audit class:** (a) uncited\n\n"
        "**Audit class:** (d) meta\n\n| d | other | 24 |\n"
    )
    audit = parse_audit(text)
    assert audit["classes"] == {"a": 1, "b": 0, "c": 0, "d": 2}
    assert (audit["run"], audit["mode"], audit["n"]) == ("abc", "graph_local", 3)


def _graph_local(run: dict, qid: str) -> dict:
    return next(r for r in run["results"] if (r["question_id"], r["mode"]) == (qid, "graph_local"))


def test_examples_skip_hedged_answers() -> None:
    run = make_run()
    _graph_local(run, "m2_001")["answer"]["text"] += f" {ABSTAIN_EN}"
    _graph_local(run, "m2_002")["answer"]["text"] = f"Budi. {ABSTAIN_ID}"
    assert select_examples(run) == ["m2_005"]


def test_examples_need_a_supported_claim() -> None:
    run = make_run()
    _graph_local(run, "m2_001")["answer"]["claims"][0]["supported"] = None
    _graph_local(run, "m2_002")["answer"]["claims"][0]["supported"] = False
    assert select_examples(run) == ["m2_005"]


def test_report_reads_config_flags_and_reverse_count() -> None:
    markdown, data = _build(make_run())
    assert data["claim_split_version"] == "unknown" and data["rescored"] is False
    assert "re-verification" not in markdown
    assert "except graph_global" in markdown
    assert data["example_counts"] == {"graph_local_only": 3, "hybrid_only": 0}
    run = make_run()
    run["config"] |= {"claim_split_version": "v2", "rescored": True}
    run["results"][0]["answer"]["claims"][0]["supported"] = None
    markdown, data = _build(run)
    assert (
        "claim split v2, rescored" in markdown
        and "1 cited claims await re-verification" in markdown
    )
    hybrid_only = _row("m2_003", "multi_hop_2", "hybrid", 1.0)
    run["results"] = [
        r for r in run["results"] if (r["question_id"], r["mode"]) != ("m2_003", "hybrid")
    ] + [hybrid_only]
    assert _build(run)[1]["example_counts"]["hybrid_only"] == 1


def test_splitter_hand_check_only_for_audited_run() -> None:
    markdown, data = _build(make_run())
    assert "hand check" not in markdown and "not hand-checked" not in markdown
    assert data["answerable"] == 7 and data["significant_categories"].keys() == {"graph_local"}
    run = make_run()
    run["run_id"] = "23b9a166-a905-4500-bc84-5d2f6f0c30d5"
    run["config"]["claim_split_version"] = "v2"
    assert "A hand check of the 252 lines" in _build(run)[0]


def test_summary_sentence_separates_gains_and_losses() -> None:
    from nexus.eval import report

    diffs = [
        {"mode": "graph_local", "category": "multi_hop_2", "mean_diff": 0.5, "significant": True},
        {"mode": "graph_local", "category": "thematic", "mean_diff": -0.2, "significant": True},
        {"mode": "graph_local", "category": "temporal", "mean_diff": 0.0, "significant": False},
    ]
    per_cat = [d for d in diffs if d["mode"] == report.EXAMPLE_MODE]
    gains = [d["category"] for d in per_cat if d["significant"] and d["mean_diff"] > 0]
    losses = [d["category"] for d in per_cat if d["significant"] and d["mean_diff"] < 0]
    assert gains == ["multi_hop_2"] and losses == ["thematic"]
