# NEXUS — Hybrid GraphRAG Intelligence Engine (Design)

Date: 2026-11-24 · Status: draft for approval

## 1. Intent

Portfolio centerpiece for an AI Engineer profile. NEXUS ingests a corpus of documents about Indonesian-style companies, builds a knowledge graph plus vector index, and answers questions three ways — traditional RAG, hybrid RAG, GraphRAG — so the difference is measurable, not claimed.

Headline features:
1. **Relationship discovery** — hidden connections via multi-hop graph traversal (e.g. two "unrelated" companies linked through a commissioner who is the spouse of the other's founder).
2. **Global knowledge discovery** — themes and communities across the whole corpus (Leiden communities + LLM summaries).
3. **Evidence-backed intelligence** — every graph edge and every generated claim traces to a source chunk in a source document.

Research component: same dataset, same question set, same retrieval stack → compare RAG vs hybrid vs GraphRAG with published numbers.

## 2. Goals / Non-goals / Anti-goals

Goals
- Runs local-first: a laptop plus self-hosted services on a private network. No public cloud.
- Fictional Indonesian corporate dataset with exact ground truth.
- Hand-built GraphRAG pipeline (approach C) — every stage explainable in an interview.
- Reproducible evaluation harness producing a comparison report.
- UI that makes graph reasoning and evidence visible.

Non-goals (for now)
- Public deployment, auth/SSO, billing.
- Real company / real person data.
- Fine-tuning models.
- Multi-tenant admin UI (tenancy is enforced in data model only, one demo tenant).

Anti-goals (failure even if it "works")
- Rigged comparison: GraphRAG must not get better prompts, more context budget, or a stronger reranker than the baselines.
- Unsupported claims shown as evidence-backed.
- Touching any Milvus collection outside the `nexus_` prefix.
- Secrets (LLM_API_KEY) committed to the repo.
- Generated names that are recognisably real companies/people.

## 3. Constraints & environment

Machine: Apple M4, 24 GB RAM. Container runtime: **Podman** (`podman-compose`), VM has 4 GiB — not Docker.

Remote (self-hosted services on a private network):
| Service | Endpoint | Notes |
|---|---|---|
| LiteLLM gateway | `http://<llm-gateway-host>:4000` (OpenAI-compatible) | `qwen3.8-27b` (chat/extraction), `bge-m3` (embeddings, 1024-d), `qwen3-reranker-4b` (rerank). Do NOT use the `-abliterated` variant. |
| Milvus | `<milvus-host>:19530` | Shared. Collection prefix **`nexus_`** only. |

Local (Podman):
| Service | Why local |
|---|---|
| Neo4j 5 Community + GDS plugin | Not available on db host; GDS gives Leiden + path algorithms. |
| PostgreSQL 16 | Tenant/document metadata, jobs, eval runs, query logs. Kept local. |

All LLM/embedding/rerank calls go through one OpenAI-compatible client configured by env, so the stack can later be pointed at any other provider.

`.env` (gitignored) holds: `LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, EMBEDDING_MODEL, RERANKER_MODEL, RERANKER_TOP_N, RETRIEVAL_TOP_K, SIMILARITY_THRESHOLD, MILVUS_HOST, MILVUS_PORT, MILVUS_COLLECTION_PREFIX=nexus_, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATABASE_URL`. `.env.example` committed without values.

Node: use `/opt/homebrew/bin/node` (v26); the default node 22.18 is too old for some current frameworks.

## 4. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| A | Wrap Microsoft GraphRAG / LightRAG | Fastest; own parquet/stores, not Neo4j/Milvus; reads as "configured a library". |
| B | `neo4j-graphrag` package + LangGraph | Medium effort; opinionated, assumes Neo4j vector index, fights Milvus. |
| **C** | **Hand-built pipeline** | Most work; every stage owned and explainable; fair comparison because all modes share one retrieval stack. |

**Chosen: C** (user decision).

## 5. Dataset — fictional Indonesian corporate world

Generation is **graph-first**: a seeded Python generator creates the ground-truth graph, then the LLM writes documents *from* those facts. Ground truth is therefore exact.

Scale: ~150 companies, ~250 people, ~40 partnerships, ~80 documents, ~8 conglomerate groups.

Indonesian realism:
- Names: `PT <name> Tbk` (listed), `PT <name>` (private), holding vehicles like `PT <name> Investama / Capital / Sejahtera`; fictional state-owned (BUMN-style) companies under a fictional state holding.
- Two-tier board: **Dewan Komisaris** (Komisaris Utama, Komisaris, Komisaris Independen) and **Direksi** (Direktur Utama, Direktur Keuangan, Direktur Operasional, …).
- Conglomerate groups with family control, cross-holdings, nominee holding companies.
- Sectors: perbankan, tambang/nikel, sawit, properti, telekomunikasi, logistik, consumer goods, fintech, energi.
- Locations: Indonesian provinces/cities.

Graph schema (ground truth = extraction target):
- Nodes: `Company`, `Person`, `Group`, `Sector`, `Location`.
- Edges: `FOUNDED`, `SERVES_AS {role, since, until}`, `OWNS_STAKE {pct, since, until}`, `SUBSIDIARY_OF`, `INVESTED_IN {round, amount}`, `PARTNERS_WITH {type: JV|supply|distribution}`, `FAMILY_OF {relation}`, `MEMBER_OF_GROUP`, `IN_SECTOR`, `HEADQUARTERED_IN`.

Planted challenges (~20 each, tracked in ground truth):
- **Hidden multi-hop paths** (2–4 hops) whose hops live in *different* documents.
- **Aliases** (“PT Sinar Jaya Tbk” / “Sinar Jaya” / “SJ Group” / ticker-like code) for entity resolution.
- **Name collisions** (two different people named e.g. "Budi Santoso") that must NOT be merged.
- **Temporal changes** (director replaced; stake sold).

Documents (~70% Bahasa Indonesia, ~30% English, mirroring real local business press): news articles, annual-report excerpts, keterbukaan informasi (disclosures), press releases, English analyst notes. Each doc records which ground-truth facts it states (fact→doc map).

Name safety: generator uses combinatorial fictional names; a blocklist check against a short list of major real Indonesian conglomerates/tickers rejects collisions. README carries a "fictional data" disclaimer.

## 6. Architecture

```
            ┌────────────── Next.js UI ──────────────┐
            │ Ask/Compare · Graph Explorer · Themes · Evidence · Eval │
            └───────────────────┬─────────────────────┘
                                │ REST + SSE
                         FastAPI (Python)
                                │
                     LangGraph query orchestrator
          ┌──────────┬──────────┴───────────┬──────────────┐
        RAG        Hybrid             GraphRAG-local   GraphRAG-global
     (dense)   (dense+sparse+rerank) (entity→k-hop)   (community summaries)
          │          │                     │                 │
        Milvus (remote, nexus_*)       Neo4j (local)    Neo4j + Milvus
                                │
                     PostgreSQL (local): tenants, docs, jobs, eval, logs
                                │
                LiteLLM gateway (remote): qwen3.8-27b · bge-m3 · qwen3-reranker-4b
```

### 6.1 Ingestion pipeline (offline, CLI + API-triggerable)
1. **Register** document in Postgres (tenant_id, source, lang, hash — idempotent re-ingest).
2. **Chunk** (token-based with overlap; chunk IDs stable).
3. **Embed** chunks (bge-m3) → Milvus `nexus_chunks` (tenant_id as partition key / filter).
4. **Extract** entities + relations per chunk with `qwen3.8-27b`, schema-guided JSON output validated by Pydantic; each extracted edge carries `chunk_id`, `doc_id`, and the supporting quote span.
5. **Resolve entities**: candidate blocking (normalised name, alias rules like stripping `PT`/`Tbk`, embedding similarity) → LLM adjudication for ambiguous pairs → merge in Neo4j keeping all aliases and provenance.
6. **Communities**: Neo4j GDS Leiden over entity graph (hierarchical levels).
7. **Summarise communities** with LLM; store on `Community` nodes and embed into Milvus `nexus_communities`.

### 6.2 Query modes (all share chunker, embedder, reranker, context budget, answer prompt)
- **rag**: dense top-k from Milvus → answer.
- **hybrid**: dense + sparse/keyword → fusion (RRF) → `qwen3-reranker-4b` top-N → answer.
- **graph_local**: link question entities to graph nodes → k-hop expansion / shortest paths in Neo4j → collect edge provenance chunks + hybrid chunks → rerank → answer. Returns the path(s) used.
- **graph_global**: map-reduce over relevant community summaries (MS GraphRAG-style) → answer.
- **auto**: LangGraph router classifies the question (lookup / relationship / thematic) and picks a mode.

### 6.3 Evidence & citation verification
Answer prompt requires inline citations to chunk IDs. A LangGraph verification node checks each sentence-level claim against its cited chunk (LLM entailment check); unsupported claims are flagged in the UI (not silently dropped) and counted in eval.

### 6.4 Tenancy
`tenant_id` on every Postgres row, Neo4j node/edge, and Milvus entity; every query path filters by it. One demo tenant; enforced so it's real, not cosmetic.

## 7. Evaluation (research component)

Question set (~120, bilingual), generated from ground truth then hand-reviewed:
- single-hop lookup · multi-hop (2/3/4 hop) · aggregation/thematic (global) · comparison · unanswerable (should abstain).

Metrics:
| Layer | Metric |
|---|---|
| Extraction | entity & relation precision / recall / F1 vs ground truth |
| Entity resolution | pairwise precision / recall / F1 (aliases merged, collisions not) |
| Retrieval | recall@k of gold supporting documents/chunks |
| Answer | exact/F1 on entity-list answers; LLM-judge correctness for free-text |
| Global | pairwise LLM-judge on comprehensiveness / diversity (GraphRAG paper protocol) |
| Evidence | citation precision (claim supported by cited chunk), unsupported-claim rate |
| Cost | latency p50/p95, tokens per query |

Fairness rules: identical answer prompt, context token budget, reranker, and top-k across modes. Judge bias note: judge = same model family as generator; mitigate with deterministic metrics where possible, randomised answer order, and a small human-checked sample. Results stored in Postgres per run; exported as a markdown/HTML report + shown in UI.

## 8. UI (Next.js)
- **Ask / Compare**: one question → answers from all modes side by side, with latency, citations, unsupported-claim flags.
- **Graph Explorer**: entity search, neighbourhood view, path finder between two entities; clicking an edge shows its evidence quote and source doc.
- **Themes**: community hierarchy with summaries and member entities.
- **Evidence panel**: source document with the cited span highlighted.
- **Eval dashboard**: run comparison tables/charts per question category.

## 9. Repo layout
```
nexus/
  infra/compose.yaml        # podman-compose: neo4j(+GDS), postgres
  backend/                  # uv, Python 3.12, FastAPI, LangGraph
    nexus/{config,llm,datagen,ingest,resolve,communities,retrieval,graph,api,eval}
    tests/
  frontend/                 # Next.js
  data/                     # generated dataset (ground truth + docs), gitignored or small committed sample
  eval/                     # question sets, run outputs, reports
  docs/
  .env.example
```

## 10. Decided vs left to builder

Decided: approach C; stack (Neo4j local, Milvus remote, Postgres local, LangGraph, FastAPI, Next.js); Podman; models via LiteLLM; `nexus_` prefix; fictional graph-first Indonesian dataset; bilingual docs; schema in §5; four modes + auto; eval metrics in §7; fairness rules.

Calls made after builder review (author's call, correctable):
- **Global-mode evidence**: community summaries are generated with chunk citations per sentence and store that provenance; `graph_global` answers cite chunks *through* summaries, and verification checks against those chunks. Summaries themselves are never final evidence.
- **Fair budget**: equal token budget for the *final answer prompt* across modes, reranking after merge with the same top-N. Total tokens read (incl. map steps) reported separately as cost, not hidden.
- **Temporal model**: `SERVES_AS` and `OWNS_STAKE` carry `since` / `until` (null = current). Questions default to current state; ~10% ask point-in-time ("siapa Direktur Utama pada 2022?"). Extracting a past fact correctly with its dates counts as correct; asserting it as current counts as wrong.

User answers (2026-11-24):
- Eval numbers **may be published** → single eval track; provider stays env-swappable but no multi-provider harness.
- **No deadline.** Cut order if needed: `auto` mode → hierarchical community levels → Themes view. Core comparison + Graph Explorer never cut.
- User reviews ~120 eval questions (~1–2 h) before milestone 5.
- **UI design language follows https://monveo.app/** (tokens, type, motion extracted into `docs/design-system.md`); NEXUS keeps its own name, logo and copy — no Monveo branding or assets.

Builder's call: chunk size/overlap; Leiden parameters; prompts; graph viz library; sparse retrieval method (Milvus 2.5 built-in BM25 if server version supports it, else Postgres full-text — check server version first); Python ORM/migrations tooling; exact question counts per category; UI styling.

## 11. Suggested milestones
1. Infra (Podman compose, `.env`, connectivity checks) + dataset generator + ground truth.
2. Ingestion → Milvus; `rag` and `hybrid` modes; minimal eval harness (retrieval + answer).
3. Extraction → Neo4j; entity resolution; extraction/ER metrics.
4. Communities + summaries; `graph_local`, `graph_global`, `auto` via LangGraph; citation verification.
5. Full eval run + report.
6. Next.js UI.
