# NEXUS Plan 1 — Foundation: Dataset, Ingestion, RAG & Hybrid Baselines

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible fictional Indonesian corporate dataset with exact ground truth, ingested into Postgres + Milvus, answerable through `rag` and `hybrid` modes via FastAPI, with a minimal eval harness that scores both.

**Architecture:** Python package `nexus` under `backend/` (uv). Seeded generator builds the ground-truth world, LLM writes documents from planned fact bundles. Ingestion chunks → embeds (bge-m3 via LiteLLM) → Milvus `nexus_chunks` (dense + built-in BM25 sparse) and Postgres (documents, chunks with char offsets). Retrieval modes are plain functions; LangGraph arrives in Plan 3.

**Tech Stack:** Python 3.12, uv, FastAPI, pydantic-settings, openai SDK (OpenAI-compatible gateway), httpx, pymilvus 2.5, psycopg 3, Faker (`id_ID`), pytest, ruff. Podman (`podman-compose`) for Postgres 16 (Neo4j service is declared now, used in Plan 2).

**Spec:** `docs/superpowers/specs/2026-11-24-nexus-design.md`

**Roadmap (later plans, written when this one ships):** Plan 2 extraction → Neo4j + entity resolution + extraction/ER metrics · Plan 3 communities + `graph_local` / `graph_global` / `auto` via LangGraph + citation verification · Plan 4 full eval + report · Plan 5 Next.js UI per `docs/design-system.md`.

## Global Constraints

- Container runtime is **Podman** (`podman-compose -f infra/compose.yaml`), never Docker.
- LLM/embeddings/rerank only through `LLM_BASE_URL=http://<llm-gateway-host>:4000`; models `qwen3.8-27b` (never the `-abliterated` variant), `bge-m3` (dim 1024), `qwen3-reranker-4b` via `POST {LLM_BASE_URL}/rerank`.
- Milvus `<milvus-host>:19530` may be a shared instance: every collection name MUST start with `nexus_`; code refuses anything else. Tests use `nexus_test_`.
- Secrets only in gitignored `.env`; commit `.env.example` with keys and no values. `.env` is in `.gitignore` before anything else is created.
- Env names (verbatim): `LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, EMBEDDING_MODEL, RERANKER_ENABLED, RERANKER_MODEL, RERANKER_TOP_N=6, RETRIEVAL_TOP_K=10, SIMILARITY_THRESHOLD=0.4, MILVUS_HOST, MILVUS_PORT, MILVUS_SEARCH_NPROBE=128, MILVUS_COLLECTION_PREFIX=nexus_, DATABASE_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD`.
- Every Postgres row and Milvus entity carries `tenant_id`; every read filters by it. Default tenant `demo`.
- Fairness: `rag` and `hybrid` share chunker, embedder, answer prompt, and final context size (`RERANKER_TOP_N` chunks).
- Data is fictional; generated names must pass the real-entity blocklist.
- Docs language mix: ~70% `id`, ~30% `en`.
- **Git:** `git init` is allowed; do NOT commit. The user commits once, squashed, when they ask. Plan steps say "Checkpoint" instead of commit.
- Python style: type hints everywhere, no `Any` unless crossing an untyped library boundary; comments explain why, one line max.
- Test markers: `integration` (needs Podman Postgres and/or Milvus), `live` (needs gateway). Default `pytest` run excludes both.

## Review Focus

1. **Alias / casing in questions** ("sinar jaya", "SJ Group") — hybrid must still surface the right doc. → Task 8 integration test `test_bm25_matches_alias_lowercase`.
2. **Unanswerable question** — no hits above `SIMILARITY_THRESHOLD` must abstain without calling the LLM. → Task 10 `test_abstains_without_llm_when_no_hits`.
3. **Gateway failure mid-ingest** — document marked `failed`, no partial chunks left in Postgres or Milvus; re-run succeeds. → Task 9 `test_embed_failure_leaves_no_partial_chunks`.
4. **Empty / tiny / huge documents** — empty → 0 chunks, tiny → 1 chunk, offsets always slice back to the chunk text. → Task 7 tests.
5. **Cross-lingual questions** (English question, Indonesian doc) — eval set must contain them so the gap is measured. → Task 12 `test_cross_lingual_share`.

---

### Task 1: Repo scaffold, config, Podman infra, connectivity check

**Files:**
- Create: `.gitignore`, `.env.example`, `README.md` (short: what, fictional-data disclaimer, quickstart), `infra/compose.yaml`
- Create: `backend/pyproject.toml`, `backend/nexus/__init__.py`, `backend/nexus/config.py`, `backend/nexus/cli.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings, reads `../.env`), `get_settings() -> Settings` (lru_cached), `Settings.collection(name: str) -> str` returning `f"{prefix}{name}"`; CLI entry `nexus = nexus.cli:app` (Typer is NOT added; use `argparse` subcommands).

- [ ] **Step 1:** `git init`; write `.gitignore` first (`.env`, `.venv/`, `__pycache__/`, `node_modules/`, `.playwright-mcp/`, `eval/runs/*.json`). Write `.env.example` with every key from Global Constraints, empty secrets, defaults filled.
- [ ] **Step 2:** `infra/compose.yaml`: `postgres:16` (port 5432→**5433** on host to avoid clashing with anything local, db `nexus`, volume `pg_data`), `neo4j:5-community` with `NEO4J_PLUGINS='["graph-data-science"]'`, ports 7474/7687, heap 1G (Podman VM has 4 GiB).
- [ ] **Step 3: Write failing tests** in `test_config.py`:
  - `test_collection_name_uses_prefix`: settings with prefix `nexus_` → `collection("chunks") == "nexus_chunks"`.
  - `test_rejects_non_nexus_prefix`: constructing `Settings(MILVUS_COLLECTION_PREFIX="grc_local")` raises `ValueError`.
  - `test_defaults`: `RERANKER_TOP_N == 6`, `RETRIEVAL_TOP_K == 10`, `SIMILARITY_THRESHOLD == 0.4`.
- [ ] **Step 4:** Run `cd backend && uv run pytest tests/test_config.py -v` → FAIL (module missing).
- [ ] **Step 5:** Implement `Settings` with a validator: prefix must start with `nexus_`.
- [ ] **Step 6:** Run tests → PASS.
- [ ] **Step 7:** Implement `nexus check` CLI: pings Postgres (`SELECT 1`), Milvus (`get_server_version`), gateway (`GET /v1/models`, asserts the three model ids present). Prints one line per service, exits non-zero on any failure. Never prints the key.
- [ ] **Step 8:** `podman-compose -f infra/compose.yaml up -d && cd backend && uv run nexus check` → three `ok` lines. (If `podman compose` errors on `~/.ssh/known_hosts:40`, use `podman-compose` directly; report to user, do not edit their ssh files.)
- [ ] **Step 9: Checkpoint** — `uv run ruff check . && uv run pytest`.

### Task 2: Gateway client (chat JSON, embeddings, rerank)

**Files:**
- Create: `backend/nexus/llm.py`
- Test: `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces:
  - `chat_json(messages: list[dict[str, str]], schema: type[BaseModel], *, temperature: float = 0.0) -> BaseModel` — uses `response_format={"type":"json_schema","json_schema":{"name":schema.__name__,"strict":True,"schema":...}}`, validates with `schema.model_validate_json`; one retry on validation error.
  - `chat_text(messages, *, temperature: float = 0.2, max_tokens: int = 1024) -> str`
  - `embed(texts: list[str]) -> list[list[float]]` — batches of 32, order preserved.
  - `rerank(query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]` — `(index, relevance_score)` sorted desc.
  - `class GatewayError(Exception)` raised on transport/HTTP failures after 2 retries with backoff.
- Client objects are built from an injectable `httpx.Client` so tests use `httpx.MockTransport`.

- [ ] **Step 1: Write failing tests:**
  - `test_embed_batches_and_preserves_order`: 70 inputs → mock sees 3 requests (32/32/6); output length 70, first vector equals mock's vector for input 0.
  - `test_rerank_parses_results_sorted`: mock returns body shaped exactly like the live sample `{"results":[{"index":1,"relevance_score":0.2},{"index":0,"relevance_score":0.96}]}` → `[(0, 0.96), (1, 0.2)]`.
  - `test_chat_json_retries_once_on_invalid`: first response invalid JSON for schema, second valid → returns model; 3 invalid → raises `GatewayError`.
  - `test_http_500_raises_gateway_error`.
  - `@pytest.mark.live test_live_roundtrip`: `embed(["tes"])[0]` has length 1024.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `llm.py`.
- [ ] **Step 4:** Run unit tests → PASS; run `uv run pytest -m live tests/test_llm.py` → PASS.
- [ ] **Step 5: Checkpoint.**

### Task 3: Ground-truth world generator

**Files:**
- Create: `backend/nexus/datagen/models.py`, `backend/nexus/datagen/names.py`, `backend/nexus/datagen/world.py`, `backend/nexus/datagen/blocklist.txt`
- Test: `backend/tests/datagen/test_world.py`

**Interfaces:**
- Produces (`models.py`, Pydantic):
  - `EntityType = Literal["Company","Person","Group","Sector","Location"]`
  - `Entity(id: str, type: EntityType, name: str, aliases: list[str], attrs: dict[str, str | int | float | bool])` — ids like `co_0001`, `pe_0001`, `gr_01`, `se_tambang`, `lo_jakarta`.
  - `RelType = Literal["FOUNDED","SERVES_AS","OWNS_STAKE","SUBSIDIARY_OF","INVESTED_IN","PARTNERS_WITH","FAMILY_OF","MEMBER_OF_GROUP","IN_SECTOR","HEADQUARTERED_IN"]`
  - `Edge(id: str, type: RelType, src: str, dst: str, props: dict[str, str | int | float | None], since: int | None = None, until: int | None = None)` — `until=None` means current. `SERVES_AS.props.role ∈ {"Komisaris Utama","Komisaris","Komisaris Independen","Direktur Utama","Direktur Keuangan","Direktur Operasional","Direktur"}`; `OWNS_STAKE.props.pct`; `PARTNERS_WITH.props.kind ∈ {"JV","supply","distribution"}`; `FAMILY_OF.props.relation ∈ {"spouse","sibling","parent","child","in-law"}`.
  - `HiddenPath(id: str, edge_ids: list[str], start: str, end: str, hops: int)`
  - `World(seed: int, entities: list[Entity], edges: list[Edge], hidden_paths: list[HiddenPath], collisions: list[tuple[str, str]])` with `to_json(path)` / `from_json(path)`.
- Produces (`world.py`): `build_world(seed: int = 42) -> World`.

Rules the generator must satisfy (copied from spec §5): ~150 companies, ~250 people, ~40 `PARTNERS_WITH`, ~8 groups; listed companies named `PT <name> Tbk`, private `PT <name>`, holding vehicles with suffix `Investama|Capital|Sejahtera`; fictional state-owned companies under one fictional state holding (attr `bumn: true`); two-tier boards; sectors perbankan, tambang/nikel, sawit, properti, telekomunikasi, logistik, consumer goods, fintech, energi; Indonesian provinces/cities for HQ; ~20 hidden paths (2–4 hops), ~20 alias sets, ~20 name collisions, ~20 temporal changes.

- [ ] **Step 1: Write failing tests** (all on `build_world(42)`):
  - `test_deterministic`: two calls produce identical JSON.
  - `test_scale`: `140 <= companies <= 160`, `230 <= people <= 270`, `35 <= partnerships <= 45`, `6 <= groups <= 10`.
  - `test_every_tbk_has_current_boards`: each company whose name ends `Tbk` has exactly one current `Komisaris Utama`, one current `Direktur Utama`, and ≥1 current `Komisaris Independen`.
  - `test_temporal_changes`: ≥20 `SERVES_AS`/`OWNS_STAKE` edges with `until` set, each with a successor edge on the same company+role (or same company stake) whose `since == until`.
  - `test_aliases`: ≥20 companies with ≥2 aliases; aliases include the name with `PT`/`Tbk` stripped.
  - `test_collisions`: ≥20 pairs of distinct person ids with identical `name`.
  - `test_hidden_paths`: ≥20 paths, each `2 <= hops <= 4`, consecutive edges share an endpoint, `start` and `end` have no direct edge between them.
  - `test_blocklist`: no entity name or alias contains (case-insensitive) any line of `blocklist.txt`.
  - `test_stakes_sum`: for each company, current `OWNS_STAKE.pct` sum ≤ 100.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** `blocklist.txt`: major real Indonesian conglomerates, SOE brands and tycoon family names (e.g. Salim, Djarum, Sinar Mas, Astra, Lippo, Bakrie, Ciputra, Indofood, Telkom, Mandiri, BCA, BRI, BNI, Pertamina, Adaro, Hartono, Riady, Widjaja, Tanoto, Thohir, Soeryadjaya, Sampoerna, Wings, MNC, Gudang Garam, Danantara). `names.py`: combinatorial company stems from Indonesian word lists (e.g. Sinar, Prima, Nusantara, Sentosa, Makmur, Abadi, Bumi, Cahaya, Mitra, Karya × suffixes) + Faker `id_ID` for people; reject blocklisted output.
- [ ] **Step 4:** Implement `build_world` with one `random.Random(seed)`; plant hidden paths by construction (pick a start company, walk a chain of FAMILY_OF / SERVES_AS / OWNS_STAKE / SUBSIDIARY_OF edges to an end company in a different group, record the edge ids).
- [ ] **Step 5:** Run → PASS.
- [ ] **Step 6:** `uv run nexus datagen world --seed 42` writes `data/world/ground_truth.json`. **Checkpoint.**

### Task 4: Document planner (fact bundles)

**Files:**
- Create: `backend/nexus/datagen/planner.py`
- Test: `backend/tests/datagen/test_planner.py`

**Interfaces:**
- Consumes: `World`, `Edge`, `HiddenPath`.
- Produces:
  - `DocType = Literal["news","annual_report","disclosure","press_release","analyst_note"]`
  - `DocPlan(doc_id: str, doc_type: DocType, lang: Literal["id","en"], year: int, edge_ids: list[str], surface_forms: dict[str, str])` — `surface_forms` maps entity id → the exact name/alias the writer must use.
  - `plan_documents(world: World, n_docs: int = 80, seed: int = 42) -> list[DocPlan]`

- [ ] **Step 1: Write failing tests:**
  - `test_every_edge_covered`: every edge id (excluding `IN_SECTOR`/`HEADQUARTERED_IN`, which may be skipped) appears in ≥1 plan.
  - `test_hidden_path_hops_split`: for each hidden path, no single plan contains two of its edges.
  - `test_lang_ratio`: share of `lang=="id"` within `[0.65, 0.75]`; `analyst_note` plans are always `en`.
  - `test_alias_usage`: ≥30% of alias-bearing entities appear in some plan with a surface form ≠ canonical name.
  - `test_bundle_size`: each plan has 3–12 edges.
  - `test_temporal_year_consistent`: an edge with `until=Y` only appears in plans with `year >= Y` (reported as past) or in plans with `since <= year < until`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. **Step 5: Checkpoint.**

### Task 5: Document writer (LLM) + datagen CLI

**Files:**
- Create: `backend/nexus/datagen/writer.py`, `backend/nexus/datagen/prompts.py`
- Test: `backend/tests/datagen/test_writer.py`

**Interfaces:**
- Consumes: `DocPlan`, `World`, `chat_text`.
- Produces:
  - `render_facts(plan: DocPlan, world: World) -> list[str]` — one plain sentence per edge, using `surface_forms`, dates included for temporal edges.
  - `write_document(plan: DocPlan, world: World, llm: Callable[[list[dict[str,str]]], str] = chat_text) -> str` — prompt per `doc_type` and `lang` (Bahasa Indonesia business-press register for `id`); must state every fact and must not invent other companies/people. Validates that every surface form appears verbatim in the output; regenerates up to 2 times, then raises `DocGenError` naming the missing forms.
  - Files: `data/world/docs/{doc_id}.md` (front matter: doc_id, doc_type, lang, year, title) and `data/world/doc_facts.json` (`{doc_id: [edge_id,...]}`).
  - CLI: `nexus datagen docs` (skips docs already on disk; `--force` rewrites).

- [ ] **Step 1: Write failing tests** (fake `llm`):
  - `test_render_facts_uses_surface_forms_and_dates`.
  - `test_regenerates_when_surface_form_missing`: fake returns text missing one form, then complete → returns second text; fake called twice.
  - `test_raises_after_three_misses`.
  - `test_cli_skips_existing`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Live run `uv run nexus datagen docs` → 80 files; spot-read 3 (one `id` news, one `disclosure`, one `en` analyst note) for register and fact fidelity; report any oddities to the user. **Checkpoint.**

### Task 6: Postgres schema + repository

**Files:**
- Create: `backend/nexus/db/migrations/001_init.sql`, `backend/nexus/db/repo.py`
- Test: `backend/tests/db/test_repo.py` (`integration`)

**Interfaces:**
- Schema: `tenants(id text pk)`, seeded `demo`; `documents(id text, tenant_id text, title text, doc_type text, lang text, year int, content text, sha256 text, status text check in ('pending','ingested','failed'), error text, primary key (tenant_id, id))`; `chunks(id text, tenant_id text, doc_id text, ordinal int, start_char int, end_char int, text text, primary key (tenant_id, id))`; `eval_runs(id uuid pk, tenant_id, created_at, config jsonb)`; `eval_results(run_id uuid, question_id text, mode text, metrics jsonb, answer jsonb, primary key (run_id, question_id, mode))`.
- Produces (`repo.py`, psycopg 3, plain SQL): `connect() -> psycopg.Connection`, `migrate(conn)`, `upsert_document(conn, tenant, doc: DocumentRow)`, `get_document(conn, tenant, doc_id) -> DocumentRow | None`, `replace_chunks(conn, tenant, doc_id, chunks: list[ChunkRow])` (delete+insert in caller's transaction), `get_chunks(conn, tenant, ids: list[str]) -> list[ChunkRow]`, `set_status(conn, tenant, doc_id, status, error=None)`, `insert_eval_run(...)`, `insert_eval_result(...)`. `DocumentRow` / `ChunkRow` are dataclasses mirroring the columns.

- [ ] **Step 1: Write failing tests:** `test_migrate_idempotent`, `test_tenant_isolation` (chunk inserted for `demo` not returned for tenant `other`), `test_replace_chunks_replaces`.
- [ ] **Step 2:** Run `uv run pytest -m integration tests/db` → FAIL. **Step 3:** Implement + `nexus db migrate`. **Step 4:** → PASS. **Step 5: Checkpoint.**

### Task 7: Chunker

**Files:**
- Create: `backend/nexus/ingest/chunker.py`
- Test: `backend/tests/ingest/test_chunker.py`

**Interfaces:**
- Produces: `Chunk(ordinal: int, start: int, end: int, text: str)`; `chunk_text(text: str, max_words: int = 300, overlap_words: int = 50) -> list[Chunk]`; `chunk_id(doc_id: str, ordinal: int) -> str` = `f"{doc_id}:{ordinal:04d}"`.
- Word count is the token proxy. `# shortcut: words ≈ tokens for bge-m3 budget; switch to tokenizer counts if chunks exceed 512 tokens.`
- Splits prefer paragraph, then sentence boundaries; never mid-word.

- [ ] **Step 1: Write failing tests:**
  - `test_empty_returns_no_chunks` (`""` and whitespace-only).
  - `test_tiny_doc_single_chunk`.
  - `test_offsets_slice_back`: for a 2,000-word fixture, `text[c.start:c.end] == c.text` for all chunks.
  - `test_overlap_and_limit`: every chunk ≤ 300 words; consecutive chunks overlap by > 0 words.
  - `test_chunk_id_stable`: `chunk_id("doc_007", 3) == "doc_007:0003"`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Checkpoint.**

### Task 8: Milvus chunk store (dense + BM25)

**Files:**
- Create: `backend/nexus/vector/milvus_store.py`
- Test: `backend/tests/vector/test_milvus_store.py` (`integration`)

**Interfaces:**
- Consumes: `get_settings().collection(...)`.
- Produces: `class ChunkStore(collection: str)` — constructor raises `ValueError` if name lacks `nexus_` prefix.
  - Schema: `chunk_id VARCHAR(64) pk`, `tenant_id VARCHAR(32)` (partition key), `doc_id VARCHAR(64)`, `text VARCHAR(8192)` with `enable_analyzer=True` (standard analyzer), `dense FLOAT_VECTOR(1024)`, `sparse SPARSE_FLOAT_VECTOR` produced by a `Function(type=FunctionType.BM25, input=text, output=sparse)`.
  - Indexes: `dense` IVF_FLAT, `nlist=128`, metric `COSINE`, search `nprobe=MILVUS_SEARCH_NPROBE`; `sparse` `SPARSE_INVERTED_INDEX`, metric `BM25`.
  - Methods: `ensure()`, `upsert(rows: list[ChunkVector])`, `delete_doc(tenant: str, doc_id: str)`, `dense_search(tenant, vector, k) -> list[Hit]`, `hybrid_search(tenant, query_text, vector, k) -> list[Hit]` (Milvus `hybrid_search` with `RRFRanker(60)` over dense + BM25), `drop()` (only allowed when name starts with `nexus_test_`).
  - `ChunkVector(chunk_id, tenant_id, doc_id, text, dense)`; `Hit(chunk_id: str, doc_id: str, text: str, score: float)`.

- [ ] **Step 1: Write failing tests** (collection `nexus_test_chunks_<random>`, dropped in teardown; fake 1024-d vectors):
  - `test_rejects_foreign_prefix`: `ChunkStore("grc_local_chunks")` raises (unit, no marker).
  - `test_drop_refuses_non_test_collection` (unit).
  - `test_dense_search_tenant_filter`: rows for `demo` and `other`; search as `demo` never returns `other` rows.
  - `test_bm25_matches_alias_lowercase`: corpus contains "PT Sinar Jaya Tbk menandatangani…"; `hybrid_search("sinar jaya", random_vec)` ranks that chunk first.
  - `test_delete_doc`.
- [ ] **Step 2–4:** FAIL → implement → PASS (`uv run pytest -m integration tests/vector`). **Step 5: Checkpoint.**

### Task 9: Ingestion pipeline + CLI

**Files:**
- Create: `backend/nexus/ingest/pipeline.py`
- Test: `backend/tests/ingest/test_pipeline.py`

**Interfaces:**
- Consumes: Task 5 doc files, `repo`, `chunk_text`, `chunk_id`, `embed`, `ChunkStore`.
- Produces: `ingest_document(path: Path, tenant: str, *, conn, store: ChunkStore, embedder=embed) -> Literal["ingested","skipped","failed"]`; `ingest_dir(dir: Path, tenant: str) -> dict[str, int]` (counts per outcome); CLI `nexus ingest data/world/docs [--tenant demo]`.
- Order per doc: parse front matter → if same `sha256` already `ingested` → `skipped` → chunk → embed all chunks (before any write) → in one PG transaction `replace_chunks` + status `ingested`, and `store.delete_doc` + `store.upsert`. On any exception: PG rolled back, `store.delete_doc`, status `failed` with error text.

- [ ] **Step 1: Write failing tests** (unit with fake repo/store/embedder; one `integration` end-to-end):
  - `test_reingest_same_hash_skips`.
  - `test_changed_content_replaces_chunks`.
  - `test_embed_failure_leaves_no_partial_chunks`: embedder raises `GatewayError` → outcome `failed`, zero chunks in repo and store, status `failed`; second run with working embedder → `ingested`.
  - `integration test_ingest_three_docs_end_to_end`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** `uv run nexus ingest data/world/docs` → `{"ingested": 80, ...}`. **Checkpoint.**

### Task 10: Retrieval modes + grounded answer

**Files:**
- Create: `backend/nexus/retrieval/modes.py`, `backend/nexus/retrieval/answer.py`, `backend/nexus/retrieval/prompts.py`
- Test: `backend/tests/retrieval/test_modes.py`, `backend/tests/retrieval/test_answer.py`

**Interfaces:**
- Consumes: `embed`, `rerank`, `chat_text`, `ChunkStore`, `Hit`.
- Produces:
  - `Mode = Literal["rag","hybrid"]` (extended in Plan 3).
  - `retrieve(question: str, mode: Mode, tenant: str, *, store, embedder=embed, reranker=rerank) -> list[Hit]`
    - `rag`: `dense_search(k=RETRIEVAL_TOP_K)` → drop `score < SIMILARITY_THRESHOLD` → first `RERANKER_TOP_N`.
    - `hybrid`: `hybrid_search(k=RETRIEVAL_TOP_K)` → `rerank(top_n=RERANKER_TOP_N)` (skip rerank if `RERANKER_ENABLED=false`) → drop hits whose rerank score < `SIMILARITY_THRESHOLD`.
  - `Answer(text: str, citations: list[str], invalid_citations: list[str], hits: list[Hit], abstained: bool, mode: Mode, latency_ms: int)`
  - `answer(question: str, mode: Mode, tenant: str, **deps) -> Answer` — shared prompt (same for every mode, in `prompts.py`): answer in the question's language, cite every factual sentence as `[chunk_id]`, reply with the fixed abstain string when context is insufficient (`ABSTAIN_ID = "Informasi tidak ditemukan dalam dokumen."`, `ABSTAIN_EN = "The documents do not contain this information."`). Citations not among `hits` go to `invalid_citations`.

- [ ] **Step 1: Write failing tests:**
  - `test_rag_applies_threshold_and_top_n`.
  - `test_hybrid_reranks_to_top_n`.
  - `test_same_final_context_size_both_modes` (both ≤ `RERANKER_TOP_N`).
  - `test_abstains_without_llm_when_no_hits`: zero hits → `abstained=True`, LLM fake never called.
  - `test_parses_citations_and_flags_invalid`: LLM text cites one real and one unknown chunk id → `citations=[real]`, `invalid_citations=[unknown]`.
  - `test_detects_model_abstain_string`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Checkpoint.**

### Task 11: FastAPI service

**Files:**
- Create: `backend/nexus/api/app.py`, `backend/nexus/api/deps.py`
- Test: `backend/tests/api/test_app.py`

**Interfaces:**
- Consumes: `answer`, `repo`, `ChunkStore`, `nexus check` probes.
- Produces: `create_app() -> FastAPI`; tenant from header `X-Tenant` (default `demo`, must match `^[a-z0-9_]{1,32}$` else 400).
  - `POST /query` body `{question: str (1..1000 chars), mode: "rag"|"hybrid"}` → `Answer` JSON.
  - `GET /documents/{doc_id}` → document incl. content; 404 if not in tenant.
  - `GET /chunks/{chunk_id}` → chunk with `start_char`/`end_char` (for evidence highlighting).
  - `GET /health` → `{postgres, milvus, gateway}` each `"ok"|"down"`, 200 always.
  - CORS allow `http://localhost:3000`.
  - Run: `uv run uvicorn nexus.api.app:create_app --factory --port 8000`.

- [ ] **Step 1: Write failing tests** (dependency overrides with fakes): `test_query_returns_answer`, `test_query_validates_mode` (422), `test_bad_tenant_header_400`, `test_document_404_other_tenant`, `test_health_reports_down_service`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Live smoke: `curl -s localhost:8000/query -H 'content-type: application/json' -d '{"question":"Siapa Direktur Utama <a Tbk company from ground truth>?","mode":"hybrid"}'` → answer names the correct person with a citation. **Checkpoint.**

### Task 12: Eval questions + minimal harness

**Files:**
- Create: `backend/nexus/eval/questions.py`, `backend/nexus/eval/metrics.py`, `backend/nexus/eval/harness.py`
- Test: `backend/tests/eval/test_questions.py`, `backend/tests/eval/test_metrics.py`

**Interfaces:**
- Consumes: `World`, `doc_facts.json`, `answer`, `repo.insert_eval_*`.
- Produces:
  - `Question(id: str, lang: Literal["id","en"], category: Literal["single_hop","multi_hop_2","multi_hop_3","temporal","unanswerable"], text: str, gold_answers: list[list[str]], gold_doc_ids: list[str])` — `gold_answers` is a list of answer entities, each given as its accepted surface forms (name + aliases).
  - `build_questions(world: World, doc_facts: dict[str, list[str]], seed: int = 42) -> list[Question]` — template-based (ID and EN templates per category); writes `eval/questions.jsonl`. Multi-hop questions come from `HiddenPath`s; unanswerable ones ask about real-looking but absent relations.
  - `metrics.py`: `normalize(s: str) -> str` (lowercase, strip `PT`/`Tbk`/punctuation), `answer_match(answer_text: str, gold: list[list[str]]) -> float` (fraction of gold entities with any form present), `recall_at_k(retrieved_doc_ids: list[str], gold_doc_ids: list[str]) -> float`, `abstain_correct(ans: Answer, q: Question) -> bool`.
  - `run_eval(modes: list[Mode], tenant: str = "demo", limit: int | None = None) -> UUID` — stores per-question results, writes `eval/runs/{run_id}.json` and `eval/runs/{run_id}.md` (table: mode × category → answer_match, recall@k, abstain accuracy, p50/p95 latency). CLI `nexus eval questions` / `nexus eval run --modes rag,hybrid`.

- [ ] **Step 1: Write failing tests:**
  - `test_categories_present`: each category has ≥10 questions; total 100–140.
  - `test_cross_lingual_share`: ≥20% of answerable questions have `lang` ≠ lang of every gold doc.
  - `test_multi_hop_gold_docs_span_multiple_docs`.
  - `test_normalize_strips_pt_tbk`: `normalize("PT Sinar Jaya Tbk") == "sinar jaya"`.
  - `test_answer_match_partial`: 2 gold entities, one present → 0.5.
  - `test_recall_at_k`.
  - `test_abstain_correct_for_unanswerable`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** `uv run nexus eval questions && uv run nexus eval run --modes rag,hybrid` → prints run id and the markdown table; hybrid should beat rag on alias-heavy single-hop. Report the table to the user (no tuning to make numbers look better).
- [ ] **Step 6: Checkpoint** — full `uv run ruff check . && uv run pytest && uv run pytest -m "integration or live"` green. Tell the user Plan 1 is done and ready for their single squashed commit (`feat: nexus foundation — dataset, ingestion, rag/hybrid baselines`).
