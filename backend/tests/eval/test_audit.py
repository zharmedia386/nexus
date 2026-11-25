import json

from nexus.eval.audit import sample_unsupported, write_audit
from nexus.retrieval.verify import CLAIM_SPLIT_VERSION


def make_run() -> dict:
    def row(qid: str, mode: str, category: str, verdicts: list[bool | None]) -> dict:
        claims = [
            {"text": f"{qid} claim {i}", "chunk_ids": [f"doc_001:000{i}"], "supported": v}
            for i, v in enumerate(verdicts)
        ]
        return {
            "question_id": qid,
            "mode": mode,
            "category": category,
            "answer": {"claims": claims},
        }

    return {
        "run_id": "abcdef12-0000-0000-0000-000000000000",
        "results": [
            row("m3_001", "graph_local", "multi_hop_3", [False, True, None, False]),
            row("m3_002", "graph_local", "multi_hop_3", [False, False, True]),
            row("m3_001", "rag", "multi_hop_3", [False]),
            row("sh_001", "graph_local", "single_hop", [False]),
            {
                "question_id": "m3_003",
                "mode": "graph_local",
                "category": "multi_hop_3",
                "answer": None,
            },
        ],
    }


def test_audit_samples_only_unsupported(tmp_path) -> None:
    sample = sample_unsupported(make_run(), "graph_local", "multi_hop_3", n=30)
    assert len(sample) == 4
    assert all(item["claim"]["supported"] is False for item in sample)
    assert {item["question_id"] for item in sample} == {"m3_001", "m3_002"}

    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(make_run()), encoding="utf-8")
    fetched: list[list[str]] = []

    def fetch(ids: list[str]) -> dict[str, str]:
        fetched.append(ids)
        return {cid: f"text of {cid}" for cid in ids if cid != "doc_001:0003"}

    path = write_audit(
        run_path, "graph_local", "multi_hop_3", 30, {"m3_001": "Siapa?"}, fetch, out_dir=tmp_path
    )
    assert path.name == "claims-abcdef12-graph_local.md"
    text = path.read_text(encoding="utf-8")
    assert fetched == [["doc_001:0000", "doc_001:0001", "doc_001:0003"]]
    assert text.count("human: [ ] supported [ ] not supported") == 4
    assert "**Question:** Siapa?" in text and "> text of doc_001:0000" in text
    assert "_(chunk not found)_" in text


def test_audit_deterministic_sample() -> None:
    run = make_run()
    first = sample_unsupported(run, "graph_local", "multi_hop_3", n=2, seed=7)
    assert first == sample_unsupported(run, "graph_local", "multi_hop_3", n=2, seed=7)
    assert len(first) == 2
    seeds = {
        tuple(
            i["claim"]["text"] for i in sample_unsupported(run, "graph_local", "multi_hop_3", 2, s)
        )
        for s in range(10)
    }
    assert len(seeds) > 1


def test_rescore_reuses_verdicts(tmp_path) -> None:
    from nexus.eval.audit import rescore_run

    text = "Langkah 1:\nBudi memegang 20% [d1:0000].\nBudi lahir 1970 [d1:0000].\nTidak ada sumber."
    stored = [
        {"text": "Langkah 1:", "chunk_ids": [], "supported": False},
        {"text": "Budi memegang 20%.", "chunk_ids": ["d1:0000"], "supported": True},
        {"text": "Tidak ada sumber.", "chunk_ids": [], "supported": False},
    ]
    answer = {"text": text, "claims": stored, "hits": [{"chunk_id": "d1:0000", "text": "t"}]}
    metrics = {"latency_ms": 1, "llm_calls": 1, "verify_calls": 1, "verify_ms": 1}
    metrics |= {"answer_match": 1.0, "answer_precision": None, "recall_at_k": 1.0}
    metrics |= {"abstain_correct": False, "unsupported_claim_rate": 2 / 3}
    run = {
        "run_id": "r1",
        "config": {},
        "summary": [],
        "results": [
            {
                "question_id": "q",
                "mode": "rag",
                "category": "single_hop",
                "metrics": metrics,
                "answer": answer,
            }
        ],
    }
    run_path = tmp_path / "r1.json"
    run_path.write_text(json.dumps(run), encoding="utf-8")
    review = tmp_path / "review.csv"
    review.write_text("id,accept\n", encoding="utf-8")
    out, pending = rescore_run(run_path, review_path=review)
    assert pending == 1
    config = json.loads(out.read_text(encoding="utf-8"))["config"]
    assert config["rescored"] is True and config["claim_split_version"] == CLAIM_SPLIT_VERSION
    row = json.loads(out.read_text(encoding="utf-8"))["results"][0]
    assert [c["supported"] for c in row["answer"]["claims"]] == [True, None, False]
    # The unverified claim counts in neither denominator.
    assert row["metrics"]["unsupported_claim_rate"] == 0.5
    assert row["metrics"]["citation_precision"] == 0.5

    def fake_verify(claims, chunk_text):
        return [c.model_copy(update={"supported": True}) for c in claims], 1

    out, pending = rescore_run(run_path, fake_verify, review)
    row = json.loads(out.read_text(encoding="utf-8"))["results"][0]
    assert pending == 0 and [c["supported"] for c in row["answer"]["claims"]] == [True, True, False]
    assert "| rag | 3 | 3 | 0 | 1 | 0 |" in (tmp_path / "r1.rescored.md").read_text()

    # A rejection added after the run drops the row from the rescored summary.
    review.write_text("id,accept\nq,n\n", encoding="utf-8")
    out, _ = rescore_run(run_path, fake_verify, review)
    rescored = json.loads(out.read_text(encoding="utf-8"))
    assert rescored["results"][0]["excluded_by_review"] is True
    assert rescored["summary"] == []
