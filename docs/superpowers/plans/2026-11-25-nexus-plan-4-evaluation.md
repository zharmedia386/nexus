# NEXUS Plan 4 — Full Evaluation & Published Report

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 5-mode comparison into publishable research: add thematic (global) questions, a human review loop for the question set, a verifier audit, a pairwise LLM-judge for global answers, bootstrap confidence intervals, and one generated report with methodology and caveats.

**Architecture:** Everything extends `backend/nexus/eval/`. New questions are generated from ground truth (deterministic, appended with new ids so existing ids never change). Judge and audit outputs are JSON files under `eval/runs/`. `nexus eval report` assembles run JSON + graph metrics + judge results into `docs/report/eval-report.md`.

**Tech Stack:** existing backend only (no new dependencies; bootstrap in pure Python with `random.Random(seed)`).

**Spec:** `docs/superpowers/specs/2026-11-24-nexus-design.md` §7 (question categories incl. thematic, metrics table, fairness, judge-bias mitigation: deterministic metrics, randomised answer order, human-checked sample).

**Builds on:** `bf7e67a` (5 modes, eval harness with claim metrics, run `23b9a166` = 114 questions × 5 modes).

## Global Constraints

- Existing 114 question ids and their content never change (`sh_*`, `m2_*`, `m3_*`, `tp_*`, `un_*`); new categories get new id prefixes. A test pins the first 114 lines of `eval/questions.jsonl` against git HEAD content.
- Judge = `qwen3.8-27b` via `nexus.llm.chat_json`, temperature 0, both answer orders, verdict counts only when both orders agree (else tie). The same-family bias is stated in the report.
- No tuning of prompts on eval answers to raise one mode's score. Any prompt change (e.g. verifier) applies to all modes and bumps its version constant.
- Report numbers are copied from run files by code, never typed by hand.
- No git commits by implementers. `ruff check` + `ruff format --check` + `pytest` green per task. Markers `integration` / `live`.

## Review Focus

1. **User rejects a question in the review sheet** → it is excluded from every summary and the report states how many were excluded. → Task 2 `test_rejected_questions_excluded_from_summary`.
2. **Small categories (n=14)** → report shows CIs, so a 0.07 vs 0.00 difference is not presented as a win. → Task 5 `test_ci_overlaps_zero_flagged_not_significant`.
3. **Judge position bias** → inconsistent verdicts across the two orders become ties. → Task 4 `test_order_disagreement_is_tie`.
4. **Thematic question whose gold set is huge** (a 40-company group) → capped and scored as coverage, not exact match. → Task 1 `test_thematic_gold_capped`.
5. **Report run with missing inputs** (no judge file yet) → section says "not run", report still generated. → Task 6 `test_report_without_judge_section`.

---

### Task 1: Thematic questions

**Files:** Modify `backend/nexus/eval/questions.py`; Test `backend/tests/eval/test_questions.py`

**Interfaces:**
- `Category` adds `"thematic"`; id prefix `th`.
- `build_questions(...)` appends ~20 thematic questions **after** the existing ones (existing generation untouched, same RNG stream order for them — draw thematic items from a separate `random.Random(seed + 1)`).
- Templates (id + en, ~50/50):
  - group composition: "Which companies belong to {group} and how are they connected?" → gold = member companies (MEMBER_OF_GROUP, current).
  - family footprint: "Which companies are led or owned by members of the {surname} family?" → gold = companies with SERVES_AS (current) or OWNS_STAKE by persons in one ground-truth family (FAMILY_OF component).
  - sector players: "Who are the main players in the {sector} sector and how are they related?" → gold = companies IN_SECTOR (sector edges are context but fine as gold source) — only if ≤ 15 companies.
- Gold capped at 15 entities (pick deterministically: highest degree first); `gold_doc_ids` = docs of the supporting edges (sector questions: docs mentioning those companies' planned edges).
- Thematic is scored with existing `answer_match` (= coverage) and `answer_precision`; recall@k over gold docs.

- [ ] Tests: `test_existing_questions_unchanged` (first 114 equal HEAD's file), `test_thematic_count_and_langs` (18–24, both langs), `test_thematic_gold_capped`, `test_family_footprint_gold_matches_world`.
- [ ] FAIL → implement → PASS → `uv run nexus eval questions` (prints count per category).

### Task 2: Human review sheet

**Files:** Create `backend/nexus/eval/review.py`; Modify `backend/nexus/cli.py`, `backend/nexus/eval/harness.py`; Test `backend/tests/eval/test_review.py`

**Interfaces:**
- `write_review_sheet(questions, world, path)` → CSV `eval/review/questions.csv`: `id, category, lang, question, gold_answers (canonical names joined with " | "), gold_doc_ids, accept (blank), note (blank)`. Never overwrite an existing sheet's `accept`/`note` values (merge by id; new questions appended).
- `load_rejected(path) -> set[str]` — ids with `accept` in {`n`, `no`, `x`} (case-insensitive).
- Harness `summarize` / `to_markdown` exclude rejected ids when `eval/review/questions.csv` exists; the md header line states `excluded by review: k`.
- CLI `nexus eval review-sheet`.

- [ ] Tests: `test_sheet_merge_preserves_marks`, `test_rejected_questions_excluded_from_summary`, `test_no_sheet_excludes_nothing`.

### Task 3: Verifier audit

**Files:** Create `backend/nexus/eval/audit.py`; Modify `backend/nexus/cli.py`, possibly `backend/nexus/retrieval/verify.py`; Test `backend/tests/eval/test_audit.py`

**Why:** run `23b9a166` shows ~52% unsupported claims on 3–4-hop answers for graph_local. Decide whether answers over-reach or the verifier is too strict before publishing.

**Interfaces:**
- `nexus eval audit-claims --run <id> --mode graph_local --category multi_hop_3 --n 30 [--seed 42]` → `eval/audit/claims-<run>-<mode>.md`: for each sampled unsupported claim: question, claim text, cited chunk ids with the chunk text (from Postgres), verifier verdict, and empty `human: [ ] supported [ ] not supported` box.
- Implementer then reads the 30 and records a breakdown in the report file: verifier-correct vs verifier-too-strict (e.g. needs two chunks jointly, cross-language, paraphrase of roles) vs answer-wrong. **If verifier-too-strict ≥ 30%**: change `VERIFY_SYSTEM_PROMPT` once (e.g. "a claim citing several excerpts is supported if the excerpts together support it; role/relation names may be translated"), bump a `VERIFY_PROMPT_VERSION` constant, re-verify the same 30 claims live, report before/after. No other prompt edits.

- [ ] Tests (fakes): `test_audit_samples_only_unsupported`, `test_audit_deterministic_sample`.
- [ ] Live: run audit on `23b9a166`, write the breakdown.

### Task 4: Pairwise LLM judge

**Files:** Create `backend/nexus/eval/judge.py`; Modify `backend/nexus/cli.py`; Test `backend/tests/eval/test_judge.py`

**Interfaces:**
- `Criterion = Literal["comprehensiveness", "diversity", "empowerment", "directness"]` (GraphRAG paper protocol).
- `judge_pair(question, answer_a, answer_b, *, llm=chat_json) -> dict[Criterion, Literal["A","B","tie"]]` — one call per order (A/B then B/A, temperature 0, timeout 120); a criterion's verdict counts only if both orders pick the same underlying answer, else `"tie"`. GatewayError → all ties, counted as `errors`.
- `run_judge(run_path, mode_a, mode_b, categories, *, llm) -> Path` → `eval/runs/judge-<run>-<a>-vs-<b>.json` with per-question verdicts and win rates per criterion (`a_wins`, `b_wins`, `ties`, `n`, `errors`).
- CLI `nexus eval judge --run <id> --a graph_global --b hybrid [--categories thematic]`.

- [ ] Tests: `test_order_disagreement_is_tie`, `test_consistent_verdict_counts`, `test_gateway_error_is_tie_and_counted`, `test_win_rates_sum`.

### Task 5: Bootstrap confidence intervals

**Files:** Create `backend/nexus/eval/stats.py`; Modify `backend/nexus/eval/harness.py` (summary gains `answer_match_ci_low/high`); Test `backend/tests/eval/test_stats.py`

**Interfaces:**
- `bootstrap_ci(values: list[float], *, n: int = 2000, seed: int = 42, level: float = 0.95) -> tuple[float, float]`.
- `paired_diff_ci(a: dict[str, float], b: dict[str, float], ...) -> tuple[float, float, float]` (mean diff, low, high) over shared question ids; `significant = low > 0 or high < 0`.
- Summary rows carry CI for `answer_match`; md shows `0.69 [0.61, 0.77]`.

- [ ] Tests: `test_ci_contains_mean`, `test_ci_deterministic`, `test_ci_overlaps_zero_flagged_not_significant`, `test_paired_diff_uses_shared_ids_only`.

### Task 6: Report generator

**Files:** Create `backend/nexus/eval/report.py`; Modify `backend/nexus/cli.py`; Test `backend/tests/eval/test_report.py`

**Interfaces:**
- `nexus eval report --run <id> [--graph <graph-*.json>] [--judge <judge-*.json> ...] [--audit <claims-*.md>]` → `docs/report/eval-report.md`.
- Sections (all numbers from inputs): 1 Summary (headline table: answer_match with CI per mode × category, recall@k, abstain accuracy; paired diff vs hybrid with significance flag) · 2 Dataset (world stats, docs per type/lang, question counts per category/lang, review exclusions) · 3 Method (modes, fairness rules, N, prompts versions, models) · 4 Cost (p50/p95 latency, LLM calls, verify calls) · 5 Graph quality (from graph metrics json) · 6 Evidence quality (citation precision, unsupported rate; audit breakdown if given) · 7 Global questions (judge win rates if given, else "not run") · 8 Examples (3 questions where graph_local answered and hybrid did not: question, answer, claims with verdicts, graph path) · 9 Caveats (synthetic data written by same model family → upper bound; judge = same family; small n; single run, temperature 0).
- [ ] Tests: `test_report_numbers_match_run`, `test_report_without_judge_section`, `test_examples_selected_deterministically`.

### Task 7: Live run (controller)

- [ ] `nexus eval questions` → `nexus eval review-sheet` → **user reviews the CSV** (can run in parallel with the rest).
- [ ] `nexus eval run --modes rag,hybrid,graph_local,graph_global,auto` (full set incl. thematic).
- [ ] `nexus eval judge --a graph_global --b hybrid --categories thematic` and `--a graph_local --b hybrid --categories thematic`.
- [ ] `nexus eval report ...` → review, then publish (artifact) on request.
