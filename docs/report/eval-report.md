# NEXUS evaluation report — run 96950f8a

## 1. Summary

Run `96950f8a-16ae-4976-a616-15fef9fd59d9` scored 136 questions across 5 modes (claim split v2, rescored). answer_match covers the 112 answerable questions; the 24 unanswerable ones are scored by abstain accuracy. graph_local answer_match is 0.7007 [0.6163, 0.7808] against hybrid 0.5219 [0.4316, 0.6098]; the paired difference is +0.1788 [0.087, 0.2773] (significant, 95% bootstrap). Versus hybrid, graph_local is significantly better on multi_hop_2, multi_hop_3; significantly worse on thematic; no significant difference on single_hop, temporal. Synthetic data and a single run: read §9 before quoting these numbers.

**answer_match [95% CI] by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.4723 [0.3825, 0.5646] | 0.5219 [0.4316, 0.6098] | 0.7007 [0.6163, 0.7808] | 0.3198 [0.236, 0.4053] | 0.6739 [0.5876, 0.7589] |
| multi_hop_2 | 0.0 [0.0, 0.0] | 0.0714 [0.0, 0.2143] | 0.6429 [0.3571, 0.8571] | 0.0 [0.0, 0.0] | 0.5714 [0.2857, 0.7857] |
| multi_hop_3 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.5455 [0.3636, 0.7727] | 0.0 [0.0, 0.0] | 0.5455 [0.3636, 0.7727] |
| single_hop | 0.725 [0.6, 0.85] | 0.825 [0.7, 0.925] | 0.9 [0.8, 0.975] | 0.475 [0.3, 0.625] | 0.9 [0.8, 0.975] |
| temporal | 0.4286 [0.1429, 0.7143] | 0.4286 [0.2143, 0.7143] | 0.5 [0.2143, 0.7857] | 0.2143 [0.0, 0.4286] | 0.4286 [0.2143, 0.7143] |
| thematic | 0.8137 [0.7028, 0.9149] | 0.8386 [0.7609, 0.9154] | 0.6579 [0.4862, 0.8049] | 0.628 [0.4437, 0.7909] | 0.6124 [0.4358, 0.7721] |
| unanswerable | - | - | - | - | - |

**Δ answer_match vs hybrid (paired bootstrap, * = CI excludes 0)**

| category | rag | graph_local | graph_global | auto |
|---|---|---|---|---|
| all | -0.0495 [-0.0986, -0.0052] * | +0.1788 [0.087, 0.2773] * | -0.2021 [-0.2815, -0.1251] * | +0.152 [0.061, 0.244] * |
| multi_hop_2 | -0.0714 [-0.2143, 0.0] | +0.5714 [0.2857, 0.7857] * | -0.0714 [-0.2143, 0.0] | +0.5 [0.2143, 0.7857] * |
| multi_hop_3 | +0.0 [0.0, 0.0] | +0.5455 [0.3182, 0.7727] * | +0.0 [0.0, 0.0] | +0.5455 [0.3182, 0.7727] * |
| single_hop | -0.1 [-0.2, -0.025] * | +0.075 [-0.025, 0.2] | -0.35 [-0.5, -0.2] * | +0.075 [0.0, 0.175] |
| temporal | +0.0 [-0.2143, 0.2143] | +0.0714 [0.0, 0.2143] | -0.2143 [-0.4286, 0.0] | +0.0 [0.0, 0.0] |
| thematic | -0.0248 [-0.0891, 0.038] | -0.1807 [-0.3906, -0.0032] * | -0.2106 [-0.4364, -0.0122] * | -0.2262 [-0.4449, -0.0325] * |
| unanswerable | - | - | - | - |

**recall@k by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.5557 | 0.6018 | 0.8843 | 0.3612 | 0.8237 |
| multi_hop_2 | 0.2857 | 0.3214 | 0.9286 | 0.1429 | 0.8214 |
| multi_hop_3 | 0.2576 | 0.2689 | 0.8333 | 0.197 | 0.8333 |
| single_hop | 0.775 | 0.825 | 1.0 | 0.475 | 0.95 |
| temporal | 0.7143 | 0.7857 | 1.0 | 0.2143 | 0.7857 |
| thematic | 0.5262 | 0.5902 | 0.6231 | 0.5508 | 0.6098 |
| unanswerable | - | - | - | - | - |

**abstain accuracy by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.7574 | 0.7941 | 0.8603 | 0.5074 | 0.8382 |
| multi_hop_2 | 0.5714 | 0.6429 | 0.7143 | 0.1429 | 0.7143 |
| multi_hop_3 | 0.5 | 0.6364 | 0.9545 | 0.2273 | 0.9545 |
| single_hop | 0.75 | 0.825 | 0.925 | 0.475 | 0.9 |
| temporal | 0.5714 | 0.5 | 0.5714 | 0.2143 | 0.5 |
| thematic | 1.0 | 1.0 | 0.7727 | 0.7273 | 0.7273 |
| unanswerable | 1.0 | 0.9583 | 1.0 | 1.0 | 1.0 |

**auto routing**: graph_global 6, graph_local 75, hybrid 55

## 2. Dataset

Synthetic world, seed 42: 150 Company, 8 Group, 12 Location, 250 Person, 9 Sector entities; 1434 edges; 20 planted multi-hop paths; 20 planted name collisions.

| edge type | count |
|---|---|
| FAMILY_OF | 64 |
| FOUNDED | 58 |
| HEADQUARTERED_IN | 150 |
| INVESTED_IN | 12 |
| IN_SECTOR | 133 |
| MEMBER_OF_GROUP | 112 |
| OWNS_STAKE | 231 |
| PARTNERS_WITH | 40 |
| SERVES_AS | 527 |
| SUBSIDIARY_OF | 107 |

**Documents by type × language**

| doc type | en | id | total |
|---|---|---|---|
| analyst_note | 16 | 0 | 16 |
| annual_report | 4 | 30 | 34 |
| disclosure | 2 | 3 | 5 |
| news | 4 | 28 | 32 |
| press_release | 4 | 9 | 13 |

Plus non-planned docs: ref_001.

**Questions by category × language (questions.jsonl)**

| category | en | id | total | in this run |
|---|---|---|---|---|
| multi_hop_2 | 5 | 9 | 14 | 14 |
| multi_hop_3 | 7 | 15 | 22 | 22 |
| single_hop | 15 | 25 | 40 | 40 |
| temporal | 5 | 9 | 14 | 14 |
| thematic | 12 | 10 | 22 | 22 |
| unanswerable | 10 | 14 | 24 | 24 |

Review exclusions: 0 questions excluded in this run; review sheet has 0 rejected, 0 of 136 rows marked by a human.

## 3. Method

- **rag**: dense top-k from Milvus, similarity threshold
- **hybrid**: dense + keyword, RRF fusion, reranker top-N (baseline)
- **graph_local**: question entities linked to graph nodes, then an LLM-guided traversal in Neo4j (up to 4 hops, beam 3); the source chunks of followed edges are placed first, the rest of the top-N comes from the reranker over neighbourhood + hybrid chunks; returns paths
- **graph_global**: map-reduce over community summaries (MS GraphRAG style)
- **auto**: LLM router picks a mode per question

Fairness rules (design): every mode shares the chunker, embedder, reranker, answer prompt and top-N, except graph_global, which answers via map-reduce over community summaries (its map calls are reported as cost, not hidden).

| setting | value |
|---|---|
| LLM_MODEL | qwen3.8-27b |
| EMBEDDING_MODEL | bge-m3 |
| RERANKER_MODEL | qwen3-reranker-4b |
| RERANKER_TOP_N | 6 |
| RETRIEVAL_TOP_K | 10 |
| SIMILARITY_THRESHOLD | 0.4 |

**Version constants** (from current code; not recorded in the run file; the verify prompt has no version constant)

| constant | value |
|---|---|
| extract_prompt | v2 |
| summary_prompt | v1 |
| adjudicate_prompt | v1 |
| judge_prompt | 1 |
| claim_split | v2 |
| verify_prompt | - |

N per mode: 136 questions; metrics: answer_match (gold entity mentions), recall@k (gold docs in retrieved), abstain accuracy, citation precision (verifier). CIs: 2000-sample bootstrap, seed 42.

## 4. Cost (all categories)

| mode | p50_ms | p95_ms | mean_llm_calls | mean_verify_calls | mean_verify_ms | total LLM calls |
|---|---|---|---|---|---|---|
| rag | 2921 | 56222 | 1.0 | 0.5588 | 4098.5882 | 136 |
| hybrid | 3706 | 51578 | 1.0 | 0.6324 | 4682.1838 | 136 |
| graph_local | 5998 | 66398 | 3.3162 | 0.6765 | 5156.0 | 451 |
| graph_global | 5700 | 89732 | 8.5 | 0.3309 | 3351.3971 | 1156 |
| auto | 6114 | 67505 | 3.9191 | 0.6544 | 5008.6838 | 533 |

## 5. Graph quality

Scored over 100 docs against the world ground truth (file timestamp 20261126T011306Z).

| metric | precision | recall | f1 | support |
|---|---|---|---|---|
| entities (macro) | 0.9921 | 0.9937 | 0.9923 | 1092 |
| entities (micro) | 0.9927 | 0.9908 | 0.9918 | 1092 |
| relations (macro) | 0.9523 | 0.914 | 0.9251 | 1151 |
| relations (micro) | 0.9753 | 0.927 | 0.9506 | 1151 |
| entity resolution | 0.9688 | 1.0 | 0.9842 | - |

**Relations by type**

| type | precision | recall | f1 | support |
|---|---|---|---|---|
| FAMILY_OF | 1.0 | 0.9688 | 0.9841 | 64 |
| FOUNDED | 1.0 | 1.0 | 1.0 | 58 |
| INVESTED_IN | 1.0 | 0.8333 | 0.9091 | 12 |
| MEMBER_OF_GROUP | 1.0 | 0.9286 | 0.963 | 112 |
| OWNS_STAKE | 0.9912 | 0.9784 | 0.9847 | 231 |
| PARTNERS_WITH | 1.0 | 0.8 | 0.8889 | 40 |
| SERVES_AS | 0.9493 | 0.888 | 0.9176 | 527 |
| SUBSIDIARY_OF | 1.0 | 1.0 | 1.0 | 107 |

Temporal accuracy 1.0 over 1067 dated relations; 13 entity-resolution collision merges; ticker links 28/28; 58 extracted edges dropped as unverified.

## 6. Evidence quality

| mode | citation_precision | unsupported_claim_rate | claims | uncited | awaiting re-verify | dropped by splitter |
|---|---|---|---|---|---|---|
| rag | 0.7701 | 0.2299 | 553 | 165 | 0 | 0 |
| hybrid | 0.7705 | 0.2295 | 663 | 224 | 0 | 0 |
| graph_local | 0.7867 | 0.2133 | 735 | 257 | 0 | 0 |
| graph_global | 0.7352 | 0.2648 | 578 | 266 | 0 | 0 |
| auto | 0.7801 | 0.2199 | 720 | 255 | 0 | 0 |

Uncited claims count as unsupported; claims awaiting re-verify count in neither rate.

Claim splitter v2 skips non-claim lines (headings, step labels, abstentions); it dropped 0 lines in this run. The dropped lines of this run were not hand-checked.

**Human audit** of 30 sampled unsupported claims (graph_local / multi_hop_3, run 23b9a166)

| class | meaning | count |
|---|---|---|
| a | verifier correct (claim not supported by its citations) | 5 |
| b | verifier too strict (citations do support the claim) | 0 |
| c | claim true in the world, wrong chunk attached | 1 |
| d | non-claim (header, scaffolding, meta, abstention, malformed citation) | 24 |

## 7. Global (thematic) questions

**A = graph_global vs B = hybrid** (categories: thematic; judge prompt v1; mean answer length 1912 vs 2038 chars)

| criterion | A wins | B wins | ties | n | errors |
|---|---|---|---|---|---|
| comprehensiveness | 13 | 8 | 1 | 22 | 0 |
| diversity | 14 | 7 | 1 | 22 | 0 |
| empowerment | 13 | 8 | 1 | 22 | 0 |
| directness | 5 | 8 | 9 | 22 | 0 |

**A = graph_local vs B = hybrid** (categories: thematic; judge prompt v1; mean answer length 1923 vs 2038 chars)

| criterion | A wins | B wins | ties | n | errors |
|---|---|---|---|---|---|
| comprehensiveness | 9 | 9 | 4 | 22 | 0 |
| diversity | 9 | 9 | 4 | 22 | 0 |
| empowerment | 9 | 9 | 4 | 22 | 0 |
| directness | 8 | 7 | 7 | 22 | 0 |


## 8. Examples

Selection rule: the first 3 multi-hop question ids (sorted) where graph_local matched the gold answer and hybrid did not, excluding abstaining or hedged answers and requiring at least one supported claim. Across all multi-hop questions, graph_local matched where hybrid did not on 20; the reverse (hybrid matched, graph_local did not) on 0.

### m2_001 (multi_hop_2)

**Question:** At which company does the holder of a stake in PT Nusantara Mulia currently serve as Direktur Keuangan?

**graph_local answer:**

> Based on the documents provided, **Prasetya Utama** is identified as the founder and a shareholder (holding 46% since 2011) of **Nusantara Mulia** [doc_078:0000].
>
> Prasetya Utama currently serves as **Direktur Keuangan** (Finance Director) at **PT Bintang Kreasi Tbk** [doc_063:0000] [doc_063:0001].
>
> Therefore, the company is **PT Bintang Kreasi Tbk**.

**Claims:**

- [supported] Based on the documents provided, Prasetya Utama is identified as the founder and a shareholder (holding 46% since 2011) of Nusantara Mulia. (doc_078:0000)
- [supported] Prasetya Utama currently serves as Direktur Keuangan (Finance Director) at PT Bintang Kreasi Tbk. (doc_063:0000, doc_063:0001)
- [unsupported] Therefore, the company is PT Bintang Kreasi Tbk. (no citation)

**Graph paths** (1):

- Nusantara Mulia -[FOUNDED]- Prasetya Utama -[SERVES_AS]- PT Bintang Kreasi Tbk

### m2_003 (multi_hop_2)

**Question:** Di perusahaan mana Direktur Utama Nusantara Mulia saat ini memegang saham?

**graph_local answer:**

> Berdasarkan dokumen, Direktur Utama Nusantara Mulia saat ini adalah **Karsa Permadi** [doc_078:0000].
>
> Karsa Permadi memegang saham di perusahaan **Samudra Bahari** (sebesar 50% sejak 2011) [doc_077:0000].

**Claims:**

- [supported] Berdasarkan dokumen, Direktur Utama Nusantara Mulia saat ini adalah Karsa Permadi. (doc_078:0000)
- [supported] Karsa Permadi memegang saham di perusahaan Samudra Bahari (sebesar 50% sejak 2011). (doc_077:0000)

**Graph paths** (1):

- Nusantara Mulia -[SERVES_AS]- Karsa Permadi -[OWNS_STAKE]- PT Samudra Bahari Tbk

### m2_006 (multi_hop_2)

**Question:** Di perusahaan mana pemegang saham PT Arta Harmoni Tbk saat ini menjabat sebagai Direktur Utama?

**graph_local answer:**

> Berdasarkan dokumen yang disediakan, pemegang saham PT Arta Harmoni Tbk adalah **Prasetya Utama** yang memegang 34% saham sejak tahun 2009 [doc_080:0000].
>
> Namun, dalam dokumen tersebut, Prasetya Utama **tidak** disebutkan menjabat sebagai Direktur Utama di PT Arta Harmoni Tbk (posisi tersebut dijabat oleh Fitria Yuliarti) [doc_080:0000].
>
> Jika merujuk pada dokumen lain, nama **Prasetya Utama** juga disebutkan menjabat sebagai:
> 1.  **Direktur Utama** di **BKQM** sejak tahun 2010 [doc_070:0000].
> 2.  **Direktur Keuangan** di **PT Bintang Kreasi Tbk** sejak tahun 2011 [doc_063:0000].
>
> Jadi, perusahaan tempat pemegang saham PT Arta Harmoni Tbk (Prasetya Utama) menjabat sebagai Direktur Utama adalah **BKQM** [doc_070:0000].

**Claims:**

- [supported] Berdasarkan dokumen yang disediakan, pemegang saham PT Arta Harmoni Tbk adalah Prasetya Utama yang memegang 34% saham sejak tahun 2009. (doc_080:0000)
- [supported] Namun, dalam dokumen tersebut, Prasetya Utama tidak disebutkan menjabat sebagai Direktur Utama di PT Arta Harmoni Tbk (posisi tersebut dijabat oleh Fitria Yuliarti). (doc_080:0000)
- [supported] Direktur Utama di BKQM sejak tahun 2010. (doc_070:0000)
- [supported] Direktur Keuangan di PT Bintang Kreasi Tbk sejak tahun 2011. (doc_063:0000)
- [supported] Jadi, perusahaan tempat pemegang saham PT Arta Harmoni Tbk (Prasetya Utama) menjabat sebagai Direktur Utama adalah BKQM. (doc_070:0000)

**Graph paths** (1):

- PT Arta Harmoni Tbk -[OWNS_STAKE]- Prasetya Utama -[SERVES_AS]- BKQM

## 9. Caveats

- **Synthetic data, upper bound.** Documents and questions were generated from a planted world; the documents were generated with the project's gateway model (qwen3.8-27b, LLM_MODEL at report time; datagen stores no model provenance), the same family that extracts the graph and answers (qwen3.8-27b in this run). Real corpora will likely score lower.
- **Judge = same model family** as the generator, and LLM judges favour longer answers; verdicts count only when both answer orders agree. Mean answer lengths are listed in §7.
- **Single run, temperature 0.** No run-to-run variance is measured.
- **answer_match is a mention check**: an answer that names the gold entity while hedging or declining to commit still scores 1. §8 examples are picked by rule, not by hand: they skip answers carrying the abstention phrase and need a supported claim, but a hedge worded another way can still get through.
- **Small n per category** (multi_hop_2 14, multi_hop_3 22, single_hop 40, temporal 14, thematic 22, unanswerable 24); widest per-category 95% CI spans 0.57.
- **Claim splitter v2** drops non-claim lines; this run's dropped lines were not hand-checked.
- **13 entity-resolution collision merges**: distinct people sharing a name were merged, which can create false graph paths.
- **graph_global is weak on factual questions by design**: it answers from community summaries (single_hop answer_match 0.475 vs hybrid 0.825); its target is thematic questions.
- **Questions not yet human-reviewed**: gold answers are generated from the world graph; no review-sheet rows are marked.
