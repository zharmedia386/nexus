# NEXUS Plan 3 — GraphRAG Modes: Communities, graph_local, graph_global, LangGraph, Citation Verification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer questions from the knowledge graph — multi-hop relationship discovery (`graph_local`), corpus-wide themes (`graph_global`) and an `auto` router — orchestrated by LangGraph, with every answer sentence checked against its cited chunk, and measure all modes on the existing eval set.

**Architecture:** Leiden communities (igraph + leidenalg, user choice) are computed from the tenant's Neo4j graph and stored as `:Community` nodes with LLM summaries whose sentences cite chunk ids; summaries are embedded into Milvus `nexus_communities`. `graph_local` links question entities by lexicon match, traverses Neo4j (excluding context edges) and turns edge provenance into chunks; `graph_global` map-reduces over community summaries. All modes end in the same reranker cut (`RERANKER_TOP_N`) and the same answer prompt, then a shared citation verifier. A LangGraph `StateGraph` wires classify → retrieve → generate → verify.

**Tech Stack:** existing backend + **new deps: `python-igraph`, `leidenalg`, `langgraph`**.

**Spec:** `docs/superpowers/specs/2026-11-24-nexus-design.md` (§6.1 steps 6–7, §6.2, §6.3, §7 fairness rules)

**Builds on:** Plan 2 commit `f567503` (Neo4j graph: `:Entity` nodes with `name, aliases, chunk_ids, doc_ids`; relationships with `chunk_ids, doc_ids, quotes, quote_starts, quote_ends, since, until`).

## Global Constraints

- Fairness (spec §7): every mode's final answer uses the same `build_messages` prompt, `temperature=0.0`, and at most `RERANKER_TOP_N` chunks chosen by the same reranker **after** merging candidates. Extra LLM calls (map steps, classification, verification) are reported as cost, never hidden.
- Graph traversal ignores context edges `IN_SECTOR`, `HEADQUARTERED_IN` (sector hubs create meaningless shortcuts) and `IN_COMMUNITY`/`CHILD_OF`.
- Every evidence chunk id shown to the user exists in Postgres `chunks` for the tenant; community summaries are never evidence themselves (spec decision): their sentences carry chunk ids.
- Tenant on every Neo4j/Postgres/Milvus access; Milvus collections only `nexus_*`; Cypher labels/types only from allow-lists, values as parameters.
- LLM calls go through `nexus.llm` (`chat_json` / `chat_text` with explicit timeouts); cache anything that costs LLM calls and is rebuilt (community summaries) in Postgres keyed by content hash + prompt version.
- No git commits by implementers; user commits on request. `ruff check` + `ruff format --check` + `pytest` green per task. Markers `integration` / `live`.
- Cut order if time runs short (user-approved): `auto` mode → hierarchical community levels → Themes UI. Core comparison is never cut.

## Review Focus

1. **Question names an entity by ticker / alias / lowercase / without PT-Tbk** → entity linking still finds it. → Task 3 `test_links_ticker_alias_and_lowercase`.
2. **Question names no known entity** (thematic or vague) → `graph_local` falls back to entities of the hybrid hits; answer still produced or abstains — never an exception. → Task 3 `test_no_linked_entity_falls_back_to_hybrid_entities`.
3. **Sector-hub shortcut** → paths never traverse `IN_SECTOR`/`HEADQUARTERED_IN`. → Task 3 `test_paths_exclude_context_edges` (integration).
4. **Community summary cites a chunk outside its evidence** → that citation is dropped and counted, never stored. → Task 2 `test_summary_drops_foreign_citations`.
5. **Gateway failure during verification** → the answer is still returned with claims marked `supported=None`, not a 5xx. → Task 5 `test_verifier_failure_marks_unverified`.

---

### Task 1: Leiden communities

**Files:**
- Create: `backend/nexus/graph/communities.py`
- Modify: `backend/nexus/graph/neo4j_store.py` (read graph; write communities), `backend/pyproject.toml` (`python-igraph`, `leidenalg`)
- Test: `backend/tests/graph/test_communities.py`

**Interfaces:**
- Produces:
  - `GraphStore.read_entity_graph(tenant) -> tuple[list[str], list[tuple[str, str]]]` — entity ids and undirected edge pairs, excluding `IN_SECTOR`, `HEADQUARTERED_IN`.
  - `Community(id: str, level: int, parent_id: str | None, member_ids: list[str])`; ids `f"c{level}_{index}"` with index ordered by size desc then smallest member id.
  - `detect_communities(nodes: list[str], edges: list[tuple[str, str]], *, seed: int = 42, max_size: int = 25) -> list[Community]` — level 0: `leidenalg.find_partition(graph, leidenalg.ModularityVertexPartition, seed=seed)`; level 1: re-run inside every level-0 community larger than `max_size` (members keep a level-0 parent). Isolated nodes form singleton communities only if they have degree 0 — exclude singletons from output.
  - `GraphStore.write_communities(tenant, communities) -> int` — delete the tenant's `:Community` nodes, create `(:Community {tenant_id, id, level, size})`, `(:Entity)-[:IN_COMMUNITY]->(:Community)` for level 0 and level 1, `(:Community)-[:CHILD_OF]->(:Community)`.
  - CLI `nexus graph communities [--tenant demo]` prints counts per level and size distribution.

- [ ] **Step 1: Tests:** `test_two_cliques_two_communities` (two 5-cliques joined by one edge → 2 level-0 communities), `test_deterministic_with_seed`, `test_large_community_split_into_level1` (`max_size=4` on a 10-node graph → level-1 children with parent ids), `test_singletons_excluded`; integration `test_write_communities_idempotent` (test tenant), `test_read_entity_graph_excludes_context_edges`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 2: Community summaries with chunk citations

**Files:**
- Create: `backend/nexus/graph/summaries.py`, `backend/nexus/db/migrations/004_community_summaries.sql`
- Modify: `backend/nexus/db/repo.py`, `backend/nexus/graph/neo4j_store.py`, `backend/nexus/cli.py`
- Test: `backend/tests/graph/test_summaries.py`

**Interfaces:**
- Consumes: Task 1 communities; Neo4j relationships with `quotes`, `chunk_ids`; `chat_json`; `embed`; `ChunkStore`.
- Produces:
  - `GraphStore.community_evidence(tenant, community_id, limit: int = 60) -> list[Evidence]` where `Evidence(chunk_id: str, src: str, rel: str, dst: str, quote: str)` (one per relationship provenance entry among members; deterministic order).
  - Schema `SummarySentence(text: str, chunk_ids: list[str])`, `CommunitySummary(title: str, sentences: list[SummarySentence])`.
  - `summarize_community(evidence: list[Evidence], *, llm=chat_json) -> tuple[CommunitySummary, int]` — prompt lists evidence as `[chunk_id] src —rel→ dst: "quote"`; asks for a title and 3–8 sentences on the community's theme (who controls whom, partnerships, family ties), each citing chunk ids **only from the list**; returns the summary with foreign ids removed and the count of dropped ids; sentences left with no ids are dropped. Temperature 0, timeout 300, `SUMMARY_PROMPT_VERSION = "v1"`.
  - Table `community_summaries(tenant_id, community_id, evidence_sha256, prompt_version, payload jsonb, created_at, primary key (tenant_id, community_id))`; repo `get_summary` / `put_summary`.
  - Storage: Community node gets `title`, `summary` (sentences joined with their `[chunk_id]` markers); Milvus collection `nexus_communities` via the existing `ChunkStore` (chunk_id = community id, doc_id = `"community"`, text = title + summary text, dense = embedding).
  - CLI `nexus graph summarize [--tenant demo] [--workers 4]` (cached; concurrent LLM calls with DB/Neo4j/Milvus writes on the calling thread, like `extract_tenant`); prints summarized/cached/failed and dropped-citation total.

- [ ] **Step 1: Tests (fakes):** `test_summary_drops_foreign_citations`, `test_sentence_without_valid_citation_dropped`, `test_cached_summary_skips_llm`, `test_evidence_order_deterministic` (unit over a fake store), integration `test_community_evidence_reads_provenance` (test tenant).
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 3: `graph_local` retrieval

**Files:**
- Create: `backend/nexus/retrieval/graph_local.py`
- Modify: `backend/nexus/graph/neo4j_store.py`, `backend/nexus/retrieval/modes.py` (`Mode` adds `"graph_local"`), `backend/nexus/db/repo.py` if a chunk fetch helper is missing
- Test: `backend/tests/retrieval/test_graph_local.py`

**Interfaces:**
- Produces:
  - `GraphStore.entity_lexicon(tenant) -> dict[str, str]` (normalized name/alias → entity id; ambiguous forms excluded; uses `eval.metrics.normalize`).
  - `link_entities(question: str, lexicon: dict[str, str]) -> list[str]` — whole-token match of normalized forms in the normalized question, longest match first, no overlapping spans.
  - `GraphStore.paths_between(tenant, ids: list[str], max_hops: int = 4) -> list[GraphPath]` — `shortestPath` per unordered pair, relationships restricted to the allow-list minus context edges; `GraphPath(node_ids: list[str], node_names: list[str], rel_types: list[str], chunk_ids: list[str])` (first provenance chunk of each relationship plus all others).
  - `GraphStore.neighbourhood(tenant, ids: list[str], limit: int = 40) -> list[GraphPath]` — 1-hop relationships of linked entities (same exclusions).
  - `retrieve_graph_local(question, tenant, *, store, graph, conn, embedder, reranker) -> tuple[list[Hit], list[GraphPath]]`:
    1. link entities; if none, take entities whose `chunk_ids` intersect the hybrid hits' chunk ids (top 3 by frequency).
    2. candidate chunks = provenance of `paths_between(linked)` (if ≥2 linked) + `neighbourhood(linked)` + hybrid hits (`RETRIEVAL_TOP_K`), deduped by chunk id; texts from Postgres.
    3. rerank all candidates with the shared reranker → top `RERANKER_TOP_N` (fairness).
  - `retrieve` dispatches `graph_local` and returns hits; paths are exposed via `answer()` (Task 6).

- [ ] **Step 1: Tests:** unit `test_links_ticker_alias_and_lowercase`, `test_link_prefers_longest_match`, `test_no_linked_entity_falls_back_to_hybrid_entities`, `test_final_context_capped_at_top_n` (fakes); integration (test tenant with a 3-hop chain incl. an `IN_SECTOR` shortcut) `test_paths_exclude_context_edges`, `test_path_provenance_chunks_returned`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 4: `graph_global` map-reduce

**Files:**
- Create: `backend/nexus/retrieval/graph_global.py`
- Modify: `backend/nexus/retrieval/modes.py` (`Mode` adds `"graph_global"`)
- Test: `backend/tests/retrieval/test_graph_global.py`

**Interfaces:**
- Produces:
  - `MapPoint(text: str, chunk_ids: list[str], score: int)` (score 0–100), `MapResult(points: list[MapPoint])`.
  - `retrieve_graph_global(question, tenant, *, community_store: ChunkStore, conn, embedder, reranker, llm=chat_json, top_communities: int = 8) -> tuple[list[Hit], int]`:
    1. dense search `nexus_communities` (top `top_communities`), load each community's cached `CommunitySummary`.
    2. **map** (one `chat_json` call per community, concurrent, timeout 300): given the question and that summary's sentences with ids, return points with scores; drop chunk ids not in that summary; drop score 0.
    3. **reduce to evidence:** chunk ids of points ordered by score desc → texts from Postgres → shared reranker → top `RERANKER_TOP_N`.
    4. returns hits and the number of map calls (cost).
  - The final answer is generated by the shared prompt from these hits (fairness).

- [ ] **Step 1: Tests (fakes):** `test_map_drops_foreign_chunk_ids`, `test_zero_score_points_ignored`, `test_reduce_orders_by_score_then_reranks_to_top_n`, `test_no_communities_returns_empty`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 5: Citation verifier

**Files:**
- Create: `backend/nexus/retrieval/verify.py`
- Test: `backend/tests/retrieval/test_verify.py`

**Interfaces:**
- Produces:
  - `Claim(text: str, chunk_ids: list[str], supported: bool | None)`.
  - `split_claims(answer_text: str) -> list[Claim]` — sentence split (reuse the chunker's abbreviation-aware sentence logic if exposed; otherwise a small splitter), citations parsed with the existing `CITATION_PATTERN`; sentences with no citation get `chunk_ids=[]`, `supported=False`.
  - `verify_claims(claims: list[Claim], chunk_text: dict[str, str], *, llm=chat_json) -> list[Claim]` — one `chat_json` call per answer (schema `Verdicts(items: list[Verdict(index: int, supported: bool)])`), temperature 0, timeout 120; on `GatewayError` return claims with `supported=None`.
  - Abstained answers are not verified (empty claim list).

- [ ] **Step 1: Tests (fakes):** `test_split_claims_parses_citations`, `test_uncited_sentence_unsupported`, `test_verifier_marks_supported`, `test_verifier_failure_marks_unverified`, `test_abstain_has_no_claims`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 6: LangGraph orchestration + `auto` router

**Files:**
- Create: `backend/nexus/retrieval/orchestrator.py`
- Modify: `backend/nexus/retrieval/answer.py` (`Answer` gains `claims: list[Claim]`, `graph_paths: list[GraphPath]`, `routed_mode: Mode | None`, `llm_calls: int`), `backend/nexus/retrieval/modes.py` (`Mode` adds `"auto"`), `backend/pyproject.toml` (`langgraph`)
- Test: `backend/tests/retrieval/test_orchestrator.py`

**Interfaces:**
- Produces:
  - `QueryState` (TypedDict): `question, tenant, mode, routed_mode, hits, graph_paths, text, claims, llm_calls`.
  - `build_graph(deps: Deps) -> CompiledStateGraph` with nodes `classify → retrieve → generate → verify` (`classify` is a pass-through unless `mode == "auto"`). `Deps` bundles store, community_store, graph, conn factory, embedder, reranker, llm callables.
  - `classify(question) -> Literal["hybrid", "graph_local", "graph_global"]` via `chat_json` (schema `Route(route: ...)`), prompt: lookup of a single fact → hybrid; relationship / connection / ownership chain / "how is X linked to Y" → graph_local; themes / overview / "what patterns" → graph_global.
  - `answer(question, mode, tenant, *, deps, verify: bool = True) -> Answer` — public signature for API/eval; invokes the compiled graph. Existing `rag`/`hybrid` behaviour (prompt, abstain handling, citations) unchanged.

- [ ] **Step 1: Tests (fakes):** `test_forced_mode_skips_classify`, `test_auto_routes_relationship_question_to_graph_local`, `test_rag_and_hybrid_answers_unchanged` (same text/citations as Plan 1 path with the same fakes), `test_llm_calls_counted` (classify + map + generate + verify), `test_verify_false_skips_verifier`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 7: API, eval wiring, live comparison

**Files:**
- Modify: `backend/nexus/api/app.py`, `backend/nexus/api/deps.py`, `backend/nexus/eval/harness.py`, `backend/nexus/cli.py`
- Test: `backend/tests/api/test_app.py`, `backend/tests/eval/test_harness.py`

**Interfaces:**
- API: `POST /query {question, mode: rag|hybrid|graph_local|graph_global|auto, verify?: bool=true}` → `Answer` incl. `claims`, `graph_paths`, `routed_mode`, `llm_calls`; `GET /graph/entity/{id}` (node + 1-hop neighbourhood with provenance), `GET /graph/path?from=<id>&to=<id>` (shortest path, context edges excluded), `GET /communities?level=0` (id, title, size, summary). All tenant-scoped; 404 outside tenant.
- Eval: harness accepts all modes; per row records `unsupported_claim_rate`, `citation_precision` (= supported claims / verified claims, None if none verified), `llm_calls`; `.md` table adds those columns plus `routed_mode` counts for `auto`.
- CLI: `nexus eval run --modes rag,hybrid,graph_local,graph_global,auto [--no-verify]`.

- [ ] **Step 1: Tests:** API (dependency overrides) `test_query_graph_local_returns_paths`, `test_graph_path_endpoint_excludes_other_tenant`, `test_communities_endpoint`; eval `test_summary_reports_claim_metrics_and_llm_calls`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5 (controller, live):** `graph communities` → `graph summarize` → `eval run --modes rag,hybrid,graph_local,graph_global,auto`; relay the table unmodified.
