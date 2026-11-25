# NEXUS Plan 2 — Knowledge Graph: Extraction, Entity Resolution, Neo4j, Metrics

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the ingested corpus into a tenant-scoped Neo4j knowledge graph whose every edge carries verbatim evidence, and measure extraction and entity-resolution quality against ground truth.

**Architecture:** Per-chunk schema-guided extraction with `qwen3.8-27b` (`llm.chat_json`, strict JSON schema), cached in Postgres. A resolver merges mentions into entities (normalized-name blocking + extracted aliases + LLM adjudication for same-name people) and writes nodes/relationships to local Neo4j with provenance arrays. A metrics module maps extracted mentions back to ground-truth ids through each doc's plan and reports entity / relation / ER scores.

**Tech Stack:** existing backend (Python 3.12, uv, psycopg, httpx gateway client) + **new dependency `neo4j` (official Python driver, 5.x)**. Neo4j 2026.10 Community, installed via Homebrew, `bolt://localhost:7687`.

**Spec:** `docs/superpowers/specs/2026-11-24-nexus-design.md` (§5 schema, §6.1 steps 4–5, §6.4 tenancy, §7 extraction + ER metrics)

**Builds on:** Plan 1 (commits `caf6a4d`, `2bbf715`). Plan 3 (communities, graph modes, LangGraph) consumes this plan's Neo4j graph.

## Global Constraints

- Gateway only via `nexus.llm`; model `qwen3.8-27b`; extraction uses `chat_json` (strict schema — nested objects allowed, **no `dict[str, X]` fields** in schemas).
- Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` from `Settings`. Every node and relationship has `tenant_id`; every query filters by it; `clear_tenant` deletes only that tenant's data.
- Neo4j Community edition: no NODE KEY constraints (Enterprise). Use a composite `IS UNIQUE` constraint on `(tenant_id, id)`.
- Node labels: `Entity` plus exactly one type label from `Company | Person | Group | Sector | Location`. Relationship types: the spec's `RelType` values (`FOUNDED, SERVES_AS, OWNS_STAKE, SUBSIDIARY_OF, INVESTED_IN, PARTNERS_WITH, FAMILY_OF, MEMBER_OF_GROUP, IN_SECTOR, HEADQUARTERED_IN`), never user-supplied strings interpolated into Cypher without an allow-list check.
- Every relationship carries provenance arrays `chunk_ids`, `doc_ids`, `quotes` (same length) — evidence must be a verbatim substring of its chunk.
- Temporal props `since` / `until` (int years, null = unknown/current) per spec §5.
- Real-entity names: none are introduced (reference doc is generated from the fictional world only).
- No git commits by implementers; the user commits once when asked. `ruff check` + `ruff format --check` + `pytest` green per task.
- Test markers: `integration` (needs local Postgres/Neo4j), `live` (needs gateway); default run excludes both.

## Review Focus

1. **Mention spelled differently from the planned surface form** (LLM drops "PT"/"Tbk", changes case) — gold mapping must still find the entity. → Task 7 `test_gold_mapping_tolerates_legal_affixes`.
2. **Quote not verbatim in chunk** (LLM paraphrases evidence) — relation is dropped and counted as `dropped_unverified`, never stored. → Task 3 `test_paraphrased_quote_is_dropped`.
3. **Same-name different people** (20 planted collisions) — not merged when their affiliations differ; collision merges are reported. → Task 5 `test_same_name_different_affiliation_not_merged`, Task 7 `test_er_reports_collision_merges`.
4. **Re-running** `graph extract` / `graph build` — cached chunks make no LLM calls; Neo4j ends with identical counts (no duplicates). → Task 4 `test_cached_chunk_skips_llm`, Task 6 `test_write_graph_idempotent` (integration).
5. **Gateway failure mid-extract** — failed chunks listed, others cached, rerun resumes. → Task 4 `test_failure_does_not_stop_run`.

---

### Task 1: Migrations runner + extraction cache table

**Files:**
- Modify: `backend/nexus/db/repo.py` (`migration_sql` → run every `migrations/*.sql` in name order)
- Create: `backend/nexus/db/migrations/002_extractions.sql`
- Test: `backend/tests/db/test_repo.py`

**Interfaces:**
- Produces: table `extractions(tenant_id text, chunk_id text, content_sha256 text, prompt_version text, payload jsonb, created_at timestamptz default now(), primary key (tenant_id, chunk_id), foreign key (tenant_id, chunk_id) references chunks on delete cascade)`.
- `get_extraction(conn, tenant, chunk_id) -> tuple[str, str, dict[str, object]] | None` returns `(content_sha256, prompt_version, payload)`.
- `put_extraction(conn, tenant, chunk_id, content_sha256, prompt_version, payload: dict[str, object]) -> None` (upsert; caller commits).
- `list_chunks(conn, tenant) -> list[ChunkRow]` ordered by `doc_id, ordinal`.

- [ ] **Step 1:** Unit test `test_migrations_listed_in_order` (files `001_init.sql`, `002_extractions.sql` returned sorted; every statement idempotent: contains `IF NOT EXISTS`). Integration tests `test_extraction_roundtrip`, `test_extraction_cascades_on_chunk_delete`, `test_list_chunks_tenant_scoped` (dedicated test tenants, as existing repo tests do).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; remove the old `shortcut:` comment. **Step 4:** Unit PASS; integration PASS (`uv run pytest -m integration tests/db`). **Step 5:** `uv run nexus db migrate` twice → `db: migrated`.

### Task 2: Ticker reference document

**Files:**
- Create: `backend/nexus/datagen/reference.py`
- Modify: `backend/nexus/cli.py` (`datagen reference`)
- Test: `backend/tests/datagen/test_reference.py`

**Why:** 28 tickers appear in the corpus but never next to their company's name, so ticker aliases are unlinkable from text. A fictional exchange listing table (“Daftar Kode Emiten”) is a realistic source that links them.

**Interfaces:**
- Consumes: `World`, `writer.render_markdown`-compatible front matter (reuse `writer.parse_front_matter` in tests).
- Produces: `REFERENCE_DOC_ID = "ref_001"`; `render_reference(world: World) -> str` — front matter (`doc_id: ref_001`, `doc_type: reference`, `lang: id`, `year: 2025`, JSON title `"Daftar Kode Emiten"`) + Markdown table `| Kode | Nama Perusahaan | Sektor |`, one row per company that has a 4-letter ticker alias, sorted by ticker; sector from the company's `IN_SECTOR` edge (blank if none). Deterministic, no LLM.
- CLI `nexus datagen reference` writes `data/world/docs/ref_001.md`.

- [ ] **Step 1: Tests:** `test_reference_lists_every_ticker` (row count == companies with a ticker; each row contains ticker and canonical name), `test_reference_front_matter_parses` (via `parse_front_matter`, `doc_id == "ref_001"`), `test_reference_deterministic`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** `uv run nexus datagen reference && uv run nexus ingest` → `ingested: 1, skipped: 100`. `uv run nexus eval questions` output unchanged (reference doc has no plan).

### Task 3: Chunk extractor

**Files:**
- Create: `backend/nexus/graph/__init__.py`, `backend/nexus/graph/schema.py`, `backend/nexus/graph/extract.py`, `backend/nexus/graph/prompts.py`
- Test: `backend/tests/graph/test_extract.py`

**Interfaces:**
- Consumes: `llm.chat_json`, `datagen.models.EntityType`, `RelType`.
- Produces (`schema.py`, Pydantic, strict-schema friendly):
  - `ExtractedEntity(name: str, type: EntityType, aliases: list[str])` — `aliases` = other names the chunk explicitly gives for the same entity (e.g. ticker in the same table row).
  - `ExtractedRelation(type: RelType, src: str, dst: str, role: str | None, pct: float | None, relation: str | None, kind: str | None, since: int | None, until: int | None, quote: str)` — `src`/`dst` are entity names exactly as in `entities`; `relation` uses the FAMILY_OF vocabulary (`spouse, sibling, parent, child, in-law`) with direction "src is <relation> of dst".
  - `ChunkExtraction(entities: list[ExtractedEntity], relations: list[ExtractedRelation])`
  - `VerifiedRelation(relation: ExtractedRelation, quote_start: int, quote_end: int)` — offsets within the chunk text.
  - `ExtractionResult(entities: list[ExtractedEntity], relations: list[VerifiedRelation], dropped_unverified: int, dropped_unknown_entity: int)`
- `extract.py`: `EXTRACT_PROMPT_VERSION = "v1"`; `extract_chunk(text: str, *, llm=chat_json) -> ExtractionResult`. Verification: keep a relation only if `quote` occurs verbatim in `text` (exact `str.find`; on miss retry once with whitespace-collapsed matching) **and** `src`/`dst` name an extracted entity; otherwise count it in the matching `dropped_*` field.
- `prompts.py`: bilingual-safe system prompt listing entity types, relation types with one-line meanings (Indonesian board roles: Komisaris Utama, Komisaris, Komisaris Independen, Direktur Utama, Direktur Keuangan, Direktur Operasional, Direktur), direction rules, "quote must be copied verbatim from the text, ≤ 300 chars", "do not infer facts not stated", `since`/`until` only when stated. Temperature 0.0.

- [ ] **Step 1: Tests (fake llm):** `test_keeps_verified_relation_with_offsets` (offsets slice back to quote), `test_paraphrased_quote_is_dropped` (`dropped_unverified == 1`), `test_unknown_entity_relation_dropped`, `test_whitespace_tolerant_quote_match`, `test_schema_is_strict_compatible` (no `dict` fields: `ChunkExtraction.model_json_schema()` has no `additionalProperties` object maps), `@pytest.mark.live test_live_extracts_board_role` on a 2-sentence Indonesian fixture → a `SERVES_AS` with role `Direktur Utama`.
- [ ] **Step 2–4:** FAIL → implement → PASS (unit; live once).

### Task 4: Extraction runner + CLI

**Files:**
- Create: `backend/nexus/graph/runner.py`
- Modify: `backend/nexus/cli.py` (`graph extract [--tenant demo] [--force]`)
- Test: `backend/tests/graph/test_runner.py`

**Interfaces:**
- Consumes: Task 1 repo functions, `extract_chunk`, `EXTRACT_PROMPT_VERSION`.
- Produces: `extract_tenant(conn, tenant: str, *, extractor=extract_chunk, force: bool = False) -> dict[str, int]` with keys `extracted, cached, failed`; cache hit = same `content_sha256` (of chunk text) and `prompt_version`. Each chunk is committed on success; a `GatewayError` (or validation error) is printed to stderr as `<chunk_id>: <ExcType>` and counted, never aborts the run. CLI exits 1 if `failed > 0`.
- `load_extractions(conn, tenant) -> dict[str, ExtractionResult]` keyed by chunk_id (payload → `ExtractionResult.model_validate`).

- [ ] **Step 1: Tests (fake conn/extractor):** `test_cached_chunk_skips_llm`, `test_changed_chunk_reextracts`, `test_force_reextracts`, `test_failure_does_not_stop_run` (second of three chunks raises → `{extracted: 2, failed: 1}`, stderr names chunk).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Live: `uv run nexus graph extract` → `failed: 0`; rerun → all `cached`.

### Task 5: Entity resolver

**Files:**
- Create: `backend/nexus/graph/resolve.py`
- Test: `backend/tests/graph/test_resolve.py`

**Interfaces:**
- Consumes: `ExtractionResult` per chunk, `ChunkRow` (for doc_id and `start_char` → doc offsets), `eval.metrics.normalize`.
- Produces:
  - `Mention(chunk_id: str, doc_id: str, name: str, type: EntityType)`
  - `ResolvedEntity(id: str, type: EntityType, name: str, aliases: list[str], mentions: list[Mention])` — `id = f"{type.lower()}_{sha1(type + '|' + canonical_key)[:10]}"`, `name` = most frequent surface name (ties → longest).
  - `ResolvedRelation(type: RelType, src_id: str, dst_id: str, role: str | None, pct: float | None, relation: str | None, kind: str | None, since: int | None, until: int | None, chunk_ids: list[str], doc_ids: list[str], quotes: list[str], quote_spans: list[tuple[int, int]])` — `quote_spans` are **document** offsets (`chunk.start_char + quote_start`); merged across chunks on key `(type, src_id, dst_id, role, relation, kind, since, until)`.
  - `ResolvedGraph(entities: list[ResolvedEntity], relations: list[ResolvedRelation])`
  - `resolve(extractions: dict[str, ExtractionResult], chunks: list[ChunkRow], *, adjudicate=adjudicate_people) -> ResolvedGraph`
  - `adjudicate_people(a: PersonContext, b: PersonContext) -> bool` (`chat_json` yes/no, temperature 0) where `PersonContext(name: str, facts: list[str])` lists that cluster's relation quotes (≤ 8).
- Algorithm (in order):
  1. Block by `(type, key)`; `key = normalize(name)`, additionally stripping `grup`/`group` tokens for `Group`.
  2. Union-find over blocks: union a block with every block of the same type reached through an entity's `aliases` (same chunk).
  3. Companies/Groups/Sectors/Locations: same block ⇒ same entity.
  4. Persons: mentions with the same key start as **one candidate per document**; candidates sharing at least one co-mentioned company (via any relation) merge directly; remaining same-key candidate pairs go to `adjudicate`; merge only on `True`. Cap: ≤ 200 adjudication calls (raise `RuntimeError` if exceeded — fail loudly, not silently).

- [ ] **Step 1: Tests (fake adjudicator):** `test_legal_affix_variants_merge` ("PT Mega Persada Tbk" / "Mega Persada"), `test_ticker_alias_merges_via_reference_row`, `test_group_name_forms_merge` ("Grup Bumi Sentosa" / "Bumi Sentosa Group"), `test_same_name_shared_company_merges_without_llm`, `test_same_name_different_affiliation_not_merged` (adjudicator returns False → 2 persons), `test_relation_provenance_merged_and_doc_offsets`, `test_entity_ids_deterministic`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

### Task 6: Neo4j store + `graph build`

**Files:**
- Create: `backend/nexus/graph/neo4j_store.py`
- Modify: `backend/pyproject.toml` (add `neo4j>=5,<6`), `backend/nexus/checks.py` (add `neo4j` probe → `nexus check` and `/health` show it), `backend/nexus/cli.py` (`graph build [--tenant demo]` = extract (cached) → resolve → write; prints node/relationship counts)
- Test: `backend/tests/graph/test_neo4j_store.py`

**Interfaces:**
- Consumes: `ResolvedGraph`, Settings `NEO4J_*`.
- Produces: `GraphStore(driver: neo4j.Driver | None = None)` (lazy driver from settings) with
  - `ensure_schema()` — `CREATE CONSTRAINT entity_tenant_id IF NOT EXISTS FOR (e:Entity) REQUIRE (e.tenant_id, e.id) IS UNIQUE`; index on `:Entity(tenant_id, name)`.
  - `clear_tenant(tenant: str) -> None` — `MATCH (e:Entity {tenant_id: $tenant}) DETACH DELETE e` in batches of 1,000.
  - `write_graph(tenant: str, graph: ResolvedGraph) -> dict[str, int]` — clear tenant then `UNWIND` batches: nodes `MERGE (e:Entity {tenant_id, id})` + `SET` name, aliases, type label (label from an allow-list, never raw input); relationships grouped by type, Cypher text built only from the `RelType` allow-list, props: role, pct, relation, kind, since, until, chunk_ids, doc_ids, quotes, quote_starts, quote_ends, tenant_id. Returns `{"nodes": n, "relationships": m}`.
  - `counts(tenant: str) -> dict[str, int]`.
- Validates tenant with the existing `TENANT_PATTERN`.

- [ ] **Step 1: Tests:** unit `test_rejects_unknown_rel_type` and `test_rejects_bad_tenant` (no driver call — inject a driver that fails the test if used); integration (`nexus_test_` style tenants `test_graph_a`, `test_graph_b`): `test_write_graph_idempotent` (write twice → same counts), `test_tenant_isolation` (clear one tenant leaves the other), `test_provenance_arrays_stored`.
- [ ] **Step 2–4:** FAIL → implement → PASS (`uv run pytest -m integration tests/graph`).
- [ ] **Step 5:** Live: `uv run nexus check` shows `neo4j: ok`; `uv run nexus graph build` prints counts.

### Task 7: Extraction + ER metrics and report

**Files:**
- Create: `backend/nexus/graph/metrics.py`
- Modify: `backend/nexus/cli.py` (`graph eval [--tenant demo]`)
- Test: `backend/tests/graph/test_metrics.py`

**Interfaces:**
- Consumes: `World`, `plan_documents`, `REFERENCE_DOC_ID`, `ResolvedGraph`, extractions + chunks, `eval.metrics.normalize`.
- Produces:
  - `gold_id(mention: Mention, world: World, plans: dict[str, DocPlan]) -> str | None` — for plan docs: match `normalize(mention.name)` against `normalize` of that doc's `surface_forms` values plus each referenced entity's canonical name and aliases; for `ref_001`: match against every Company's name/aliases. `None` = unmapped (counts as a false positive).
  - `entity_scores(...) -> PRF` per doc: gold = entity ids in the plan's `surface_forms`; predicted = mapped mention ids.
  - `relation_scores(...) -> PRF` — match on `(type, gold_src, gold_dst)` plus `role` for `SERVES_AS` and `relation` for `FAMILY_OF`; gold = the plan's `edge_ids`; also `temporal_accuracy` = share of matched relations whose `since`/`until` equal gold.
  - `er_scores(graph: ResolvedGraph, ...) -> ERReport(precision, recall, f1, collision_merges: int, ticker_links: int, ticker_total: int)` — pairwise over mapped mentions (same gold id vs same resolved entity); `collision_merges` = resolved entities containing mentions of two different gold persons from `World.collisions`; ticker links = tickers whose mentions resolved into the same entity as their company's name.
  - `PRF(precision: float, recall: float, f1: float, support: int)`.
  - `write_graph_report(...) -> Path` → `eval/runs/graph-<UTC timestamp>.md` and `.json` (macro over docs + micro totals, by relation type, dropped counts from extraction).

- [ ] **Step 1: Tests (hand-built world/plan fixtures):** `test_gold_mapping_tolerates_legal_affixes`, `test_unmapped_mention_is_false_positive`, `test_relation_match_requires_role_for_serves_as`, `test_temporal_accuracy`, `test_er_pairwise_perfect_and_split`, `test_er_reports_collision_merges`, `test_ticker_link_counted`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Live: `uv run nexus graph eval` → report path; controller relays the summary table to the user unmodified.
