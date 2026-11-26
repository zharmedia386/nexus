# NEXUS demo film: script

105.6 s, 1920×1080, 30 fps. Voice: Kokoro `af_heart`. 23 takes, about 240 words of speech in 92 s (about 155 wpm).
The VO times below are the take start times on the film clock (`vo/schedule.json`; speech starts about 0.3 s after each).
Every company and person in the corpus is fictional; L01 says so.

## The idea

One question, followed all the way through the product. Plain retrieval abstains because the three facts sit in
three documents; NEXUS walks the graph from one fact to the next and cites a sentence at each hop. The walk is the
product's own gesture (the path strip in Ask), so the film's hero moment is that walk, drawn large, then shown again
in the real UI.

## Beats

| # | Time | Beat | Picture | VO |
|---|---|---|---|---|
| 1 | 0:00–0:10.3 | Cold open | Real Ask capture, `rag` only. The question is typed into the input, Ask is pressed, the answer card reads "The documents do not contain this information." Camera on the input, then pushes in on the abstain. | L01 0.0 "Here's a question about a set of company filings. Every company and person in them is made up." · L02 5.8 "Plain RAG searches the filings, and says the answer isn't there." |
| 2 | 0:10.3–0:20.5 | Problem | The three chunks the answer cites, verbatim (doc_061:0001, doc_025:0000, doc_056:0001). Wide on all three, then the camera whips to each as it is named and the cited sentence is highlighted. | L03 10.2 "It is there. It's just split across three documents." · L04a 13.4 "One says who runs Cahaya Teguh." · L04b 15.9 "Another names her spouse." · L04c 17.8 "A third says which board that spouse chairs." |
| 3a | 0:20.5–0:24.6 | NEXUS: the graph | The extracted graph opens from the centre; counters land on 375 entities and 1,142 relations. Node colours and type counts come from `/graph/stats`; the layout is illustrative. | L05 20.5 "NEXUS turns the filings into a graph first." |
| 3b | 0:24.6–0:37.0 | NEXUS: real Ask | Real capture, `hybrid` beside `graph_local`. Hybrid abstains in about 4 s; graph_local shows its running timer, a jump cut from 7 s to 21 s, and the cited answer arrives. | L06 24.6 "Ask again, with hybrid search alongside. Hybrid still comes back empty." · L07 29.8 "Graph local takes about twenty seconds, because it walks the graph." |
| 3c | 0:37.0–0:51.4 | NEXUS: the walk | Back in the graph: the field dims, the path draws hop by hop with the relation and chunk id on each edge. PT Karya Semesta lands in the evidence colour. | L08 37.0 "From Cahaya Teguh, to its Direktur Utama, Zaenab Thamrin." · L09 41.1 "Then to her spouse, Raden Prasasta." · L10a 43.8 "Then to PT Karya Semesta," · L10b 46.2 "where Raden Prasasta has been Komisaris Utama since 2019." |
| 3d | 0:51.4–0:58.5 | NEXUS: citation | Real capture: a hop in the path strip is opened, then its chunk; the evidence drawer opens and a ring marks the cited sentence. | L11 52.0 "Every hop cites its sentence. Open one, and there's the source." |
| 4a | 0:58.5–1:04.6 | Explore | Real capture: search "Zaenab", pick Zaenab Thamrin, the neighbourhood graph. | L12 58.6 "Explore opens the same graph by hand. This is Zaenab Thamrin's neighbourhood." |
| 4b | 1:04.6–1:09.6 | Themes | Real capture of Themes, then its 2x screenshot for the push-in on one community card. | L13 64.7 "Themes groups it into communities, each with a written summary." |
| 5 | 1:09.6–1:32.6 | Proof | Real capture of Benchmarks, then its 2x screenshot. Callouts count up to graph local 0.70 and hybrid 0.52, then paired diff +0.18; a ring on the 95% CI [+0.09, +0.28]; the camera drops to the Thematic row, where hybrid 0.84 beats graph local 0.66. | L14a 70.0 "On 112 answerable questions, graph local matched the gold answer 70% of the time." · L14b 76.4 "Hybrid, 52%." · L15 78.3 "The paired difference is +0.18, with a 95% interval from +0.09 to +0.28." · L16a 85.6 "It doesn't win everything." · L16b 87.6 "On thematic questions, hybrid leads, 0.84 to 0.66." |
| 6 | 1:32.6–1:43.6 | Close | The stack word by word as it is spoken, the three local models, then "Runs on your machine" and the repo URL. Slow drift to the last frame. | L17 92.7 "Underneath: Neo4j, Milvus and Postgres, with LangGraph, FastAPI and Next.js." · L18 99.0 "All of it runs on your machine. The code is on GitHub." |

The 136-question total and the eval run id are on screen in the Benchmarks capture (the page header reads
"Benchmarks · run 96950f8a" and "136 questions"); the VO only says 112 answerable to stay under 160 wpm.

## On-screen text (everything the composition adds; the rest is captured UI)

- Chunk captions: `doc_061:0001 · Laporan Tahunan PT Nusantara Sakti Capital 2023`, `doc_025:0000 · Profil Prayitna Prasasta`, `doc_056:0001 · Laporan Tahunan 2021` (titles from `/documents/{id}`).
- Chunk text, verbatim from `/chunks/{id}`, with the cited sentences highlighted:
  - "Zaenab Thamrin menjabat sebagai Direktur Utama di PT Cahaya Teguh sejak 2015."
  - "Raden Prasasta adalah pasangan suami/istri dari Zaenab Thamrin."
  - "Raden Prasasta menjabat sebagai Komisaris Utama di PT Karya Semesta sejak tahun 2019."
- `375 entities · 1,142 relations · extracted graph`
- Path: `PT Cahaya Teguh` → `Zaenab Thamrin` (Direktur Utama since 2015, doc_061:0001) → `Raden Prasasta` (spouse, doc_025:0000) → `PT Karya Semesta` (Komisaris Utama since 2019, doc_056:0001). Same path as the API's `graph_paths` for this question.
- Callouts: `graph local 0.70`, `hybrid 0.52`, `paired diff +0.18`, `thematic hybrid 0.84 · graph local 0.66`.
- Close: `Neo4j · Milvus · Postgres · LangGraph · FastAPI · Next.js`, `qwen3.8-27b · bge-m3 · qwen3-reranker-4b · all local`, `Runs on your machine`, `github.com/zharmedia386/nexus`.

## Writing pass

The first draft ran 120 s of speech. Cuts: the "one passage at a time" line (the picture shows it), the graph counts
(on screen instead), the full model list (on screen instead). The humanizer pass removed a rule-of-three closer, a
"not X but Y" turn and the word "highlighted" (the product highlights the whole chunk, not only the sentence, so
the line now says "there's the source"). Indonesian names are left as written; Kokoro reads "Direktur" close to
"director", which the captions spell correctly. Numbers are spelled in `vo/lines.txt` the way they should be read
("point one eight"); the captions use digits.
