# NEXUS evaluation report — run 410c2a78

## 1. Summary

Run `410c2a78-442e-4085-b342-86556c27c41c` scored 136 questions across 5 modes (claim split v2, rescored). answer_match covers the 112 answerable questions; the 24 unanswerable ones are scored by abstain accuracy. graph_local answer_match is 0.6632 [0.5755, 0.7454] against hybrid 0.5227 [0.432, 0.611]; the paired difference is +0.1405 [0.0524, 0.2387] (significant, 95% bootstrap). Versus hybrid, graph_local is significantly better on multi_hop_2, multi_hop_3; significantly worse on thematic; no significant difference on single_hop, temporal. Synthetic data and a single run: read §9 before quoting these numbers.

**answer_match [95% CI] by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.4723 [0.3825, 0.5646] | 0.5227 [0.432, 0.611] | 0.6632 [0.5755, 0.7454] | 0.3222 [0.2385, 0.4078] | 0.6445 [0.5548, 0.7273] |
| multi_hop_2 | 0.0 [0.0, 0.0] | 0.0714 [0.0, 0.2143] | 0.5714 [0.2857, 0.7857] | 0.0 [0.0, 0.0] | 0.5 [0.2143, 0.7857] |
| multi_hop_3 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.4545 [0.2727, 0.6364] | 0.0 [0.0, 0.0] | 0.4545 [0.2727, 0.6364] |
| single_hop | 0.725 [0.6, 0.85] | 0.825 [0.7, 0.925] | 0.9 [0.8, 0.975] | 0.475 [0.3, 0.625] | 0.9 [0.8, 0.975] |
| temporal | 0.4286 [0.1429, 0.7143] | 0.4286 [0.2143, 0.7143] | 0.4286 [0.2143, 0.7143] | 0.2143 [0.0, 0.4286] | 0.4286 [0.2143, 0.7143] |
| thematic | 0.8137 [0.7028, 0.9149] | 0.8427 [0.7664, 0.9183] | 0.6488 [0.4796, 0.7926] | 0.6401 [0.4565, 0.8027] | 0.5995 [0.4286, 0.7581] |
| unanswerable | - | - | - | - | - |

**Δ answer_match vs hybrid (paired bootstrap, * = CI excludes 0)**

| category | rag | graph_local | graph_global | auto |
|---|---|---|---|---|
| all | -0.0503 [-0.1003, -0.006] * | +0.1405 [0.0524, 0.2387] * | -0.2005 [-0.2807, -0.1234] * | +0.1219 [0.0315, 0.2141] * |
| multi_hop_2 | -0.0714 [-0.2143, 0.0] | +0.5 [0.2143, 0.7857] * | -0.0714 [-0.2143, 0.0] | +0.4286 [0.2143, 0.7143] * |
| multi_hop_3 | +0.0 [0.0, 0.0] | +0.4545 [0.2727, 0.6818] * | +0.0 [0.0, 0.0] | +0.4545 [0.2727, 0.6818] * |
| single_hop | -0.1 [-0.2, -0.025] * | +0.075 [-0.025, 0.2] | -0.35 [-0.5, -0.2] * | +0.075 [0.0, 0.175] |
| temporal | +0.0 [-0.2143, 0.2143] | +0.0 [0.0, 0.0] | -0.2143 [-0.4286, 0.0] | +0.0 [0.0, 0.0] |
| thematic | -0.029 [-0.0964, 0.0371] | -0.1939 [-0.4054, -0.0168] * | -0.2026 [-0.4313, -0.004] * | -0.2432 [-0.457, -0.053] * |
| unanswerable | - | - | - | - |

**recall@k by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.5557 | 0.6018 | 0.8664 | 0.3671 | 0.8069 |
| multi_hop_2 | 0.2857 | 0.3214 | 0.9286 | 0.1786 | 0.8214 |
| multi_hop_3 | 0.2576 | 0.2689 | 0.7424 | 0.197 | 0.7424 |
| single_hop | 0.775 | 0.825 | 1.0 | 0.475 | 0.95 |
| temporal | 0.7143 | 0.7857 | 1.0 | 0.2143 | 0.7857 |
| thematic | 0.5262 | 0.5902 | 0.6231 | 0.5583 | 0.6155 |
| unanswerable | - | - | - | - | - |

**abstain accuracy by category × mode**

| category | rag | hybrid | graph_local | graph_global | auto |
|---|---|---|---|---|---|
| all | 0.7574 | 0.7941 | 0.8382 | 0.5147 | 0.8235 |
| multi_hop_2 | 0.5714 | 0.6429 | 0.7143 | 0.2143 | 0.7143 |
| multi_hop_3 | 0.5 | 0.6364 | 0.8636 | 0.2273 | 0.8636 |
| single_hop | 0.75 | 0.825 | 0.925 | 0.475 | 0.9 |
| temporal | 0.5714 | 0.5 | 0.5 | 0.2143 | 0.5 |
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
| extract_prompt | v1 |
| summary_prompt | v1 |
| adjudicate_prompt | v1 |
| judge_prompt | 1 |
| claim_split | v2 |
| verify_prompt | - |

N per mode: 136 questions; metrics: answer_match (gold entity mentions), recall@k (gold docs in retrieved), abstain accuracy, citation precision (verifier). CIs: 2000-sample bootstrap, seed 42.

## 4. Cost (all categories)

| mode | p50_ms | p95_ms | mean_llm_calls | mean_verify_calls | mean_verify_ms | total LLM calls |
|---|---|---|---|---|---|---|
| rag | 3007 | 55958 | 1.0 | 0.5588 | 4161.3456 | 136 |
| hybrid | 4130 | 59245 | 1.0 | 0.6324 | 4962.4412 | 136 |
| graph_local | 6126 | 67074 | 3.3088 | 0.6618 | 5429.5074 | 450 |
| graph_global | 6018 | 90442 | 8.5 | 0.3382 | 3697.2941 | 1156 |
| auto | 6223 | 68814 | 3.9191 | 0.6471 | 5177.3897 | 533 |

## 5. Graph quality

Scored over 100 docs against the world ground truth (file timestamp 20261124T113033Z).

| metric | precision | recall | f1 | support |
|---|---|---|---|---|
| entities (macro) | 0.9921 | 0.9937 | 0.9923 | 1092 |
| entities (micro) | 0.9927 | 0.9908 | 0.9918 | 1092 |
| relations (macro) | 0.9523 | 0.9132 | 0.9246 | 1151 |
| relations (micro) | 0.9753 | 0.9262 | 0.9501 | 1151 |
| entity resolution | 0.9688 | 1.0 | 0.9842 | - |

**Relations by type**

| type | precision | recall | f1 | support |
|---|---|---|---|---|
| FAMILY_OF | 1.0 | 0.9531 | 0.976 | 64 |
| FOUNDED | 1.0 | 1.0 | 1.0 | 58 |
| INVESTED_IN | 1.0 | 0.8333 | 0.9091 | 12 |
| MEMBER_OF_GROUP | 1.0 | 0.9286 | 0.963 | 112 |
| OWNS_STAKE | 0.9912 | 0.9784 | 0.9847 | 231 |
| PARTNERS_WITH | 1.0 | 0.8 | 0.8889 | 40 |
| SERVES_AS | 0.9493 | 0.888 | 0.9176 | 527 |
| SUBSIDIARY_OF | 1.0 | 1.0 | 1.0 | 107 |

Temporal accuracy 1.0 over 1066 dated relations; 13 entity-resolution collision merges; ticker links 28/28; 59 extracted edges dropped as unverified.

## 6. Evidence quality

| mode | citation_precision | unsupported_claim_rate | claims | uncited | awaiting re-verify | dropped by splitter |
|---|---|---|---|---|---|---|
| rag | 0.763 | 0.237 | 558 | 169 | 0 | 0 |
| hybrid | 0.7709 | 0.2291 | 694 | 237 | 0 | 0 |
| graph_local | 0.7991 | 0.2009 | 723 | 251 | 0 | 0 |
| graph_global | 0.7421 | 0.2579 | 580 | 259 | 0 | 0 |
| auto | 0.786 | 0.214 | 717 | 254 | 0 | 0 |

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

**A = graph_global vs B = hybrid** (categories: thematic; judge prompt v1; mean answer length 1891 vs 2030 chars)

| criterion | A wins | B wins | ties | n | errors |
|---|---|---|---|---|---|
| comprehensiveness | 12 | 7 | 3 | 22 | 0 |
| diversity | 12 | 8 | 2 | 22 | 0 |
| empowerment | 12 | 7 | 3 | 22 | 0 |
| directness | 7 | 6 | 9 | 22 | 0 |

**A = graph_local vs B = hybrid** (categories: thematic; judge prompt v1; mean answer length 1903 vs 2030 chars)

| criterion | A wins | B wins | ties | n | errors |
|---|---|---|---|---|---|
| comprehensiveness | 10 | 10 | 2 | 22 | 0 |
| diversity | 10 | 9 | 3 | 22 | 0 |
| empowerment | 10 | 10 | 2 | 22 | 0 |
| directness | 8 | 7 | 7 | 22 | 0 |


## 8. Examples

Selection rule: the first 3 multi-hop question ids (sorted) where graph_local matched the gold answer and hybrid did not, excluding abstaining or hedged answers and requiring at least one supported claim. Across all multi-hop questions, graph_local matched where hybrid did not on 17; the reverse (hybrid matched, graph_local did not) on 0.

### m2_001 (multi_hop_2)

**Question:** At which company does the holder of a stake in PT Nusantara Mulia currently serve as Direktur Keuangan?

**graph_local answer:**

> Based on the documents provided, the holder of a stake in **Nusantara Mulia** is **Prasetya Utama**, who holds 46% of the shares [doc_078:0000].
>
> Prasetya Utama currently serves as **Direktur Keuangan** (Finance Director) at **PT Bintang Kreasi Tbk** [doc_063:0000] [doc_063:0001].
>
> [doc_078:0000]
> [doc_063:0000]
> [doc_063:0001]

**Claims:**

- [supported] Based on the documents provided, the holder of a stake in Nusantara Mulia is Prasetya Utama, who holds 46% of the shares. (doc_078:0000)
- [supported] Prasetya Utama currently serves as Direktur Keuangan (Finance Director) at PT Bintang Kreasi Tbk. (doc_063:0000, doc_063:0001)

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
