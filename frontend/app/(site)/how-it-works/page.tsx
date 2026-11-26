import { DOCUMENTS, PipelineDiagram, total } from "@/components/content/pipeline-diagram";
import { Code, ContentSection, Steps, Table } from "@/components/content/prose";
import { PageHeader } from "@/components/page-header";
import { GRAPH_STATS, REPORT, RUN_ID } from "@/lib/showcase";

export const metadata = { title: "How it works" };

const { dataset, models, graph, routes } = REPORT;
const docsIn = (lang: string) => Object.values(dataset.docs).reduce((count, byLang) => count + (byLang[lang] ?? 0), 0);
const routed = Object.entries(routes ?? {}).map(([mode, count]) => `${mode} ${count}`).join(", ");

const MODES = [
  {
    mode: "rag",
    how: `Dense search over chunk embeddings (${models.EMBEDDING_MODEL}), top ${models.RETRIEVAL_TOP_K}, cut at cosine ${models.SIMILARITY_THRESHOLD}.`,
    sees: `Up to ${models.RERANKER_TOP_N} chunks that sit closest to the question in embedding space.`,
  },
  {
    mode: "hybrid",
    how: `Dense and BM25 searches in Milvus, fused with reciprocal rank fusion, then reranked by ${models.RERANKER_MODEL}.`,
    sees: `The ${models.RERANKER_TOP_N} chunks the reranker scores highest out of the fused pool.`,
  },
  {
    mode: "graph_local",
    how: "Links entity names in the question to the graph, takes the shortest paths between them, then lets the LLM walk up to 4 hops, choosing at most 3 edges per hop.",
    sees: "The provenance chunks of every edge the walk followed, pinned first, then reranked neighbourhood and hybrid chunks to fill the budget.",
  },
  {
    mode: "graph_global",
    how: "Finds the 8 community summaries closest to the question; a map step asks the LLM which summary sentences help and scores each point.",
    sees: "Community summaries during the map step; the answer prompt gets the chunks cited by the highest-scoring points, reranked.",
  },
  {
    mode: "auto",
    how: "An LLM classifier routes each question to hybrid (single fact), graph_local (relationships) or graph_global (themes); a gateway error falls back to hybrid.",
    sees: `Whatever the chosen mode sees. In the eval run it routed ${routed}.`,
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <PageHeader
        title="From a planted world to a cited answer."
        intro={`Every stage, what it stores and where each retrieval mode gets its evidence. Figures are read from eval run ${RUN_ID}.`}
      />
      <div className="pb-24 md:pb-[104px]">
        <ContentSection id="pipeline" title="The pipeline" lead="From synthetic world to scored answer. Each build step is its own CLI command, so any of them can be re-run alone.">
          <PipelineDiagram />
        </ContentSection>

        <ContentSection
          id="corpus"
          title="A fictional corpus with known answers"
          lead={`Generation runs graph first. A seeded generator (seed ${dataset.seed}) builds the ground-truth world, then the LLM writes documents from those facts, so gold answers come straight from the world.`}
        >
          <Steps
            items={[
              {
                title: "World",
                body: `${total(dataset.entities)} entities (companies, people, groups, sectors, locations) and ${total(dataset.edges).toLocaleString("en-US")} relations: board seats, stakes, subsidiaries, family ties, partnerships.`,
              },
              {
                title: "Documents",
                body: `${DOCUMENTS} annual-report excerpts, disclosures, news, press releases and analyst notes: ${docsIn("id")} in Indonesian, ${docsIn("en")} in English.`,
              },
              {
                title: "Planted traps",
                body: `${dataset.hidden_paths} hidden multi-hop paths whose hops sit in different documents, and ${dataset.name_collisions} name collisions: different people with the same name that must not be merged.`,
              },
              {
                title: "Fictional by design",
                body: "Names are combinatorial and checked against a blocklist of real Indonesian conglomerates and tickers. Any resemblance to a real company is coincidental.",
              },
            ]}
          />
        </ContentSection>

        <ContentSection id="ingest" title="Ingestion" lead="Documents land in Postgres, chunks land in Postgres and Milvus. Unchanged files are skipped by content hash.">
          <Steps
            items={[
              { title: "Chunk", body: "Up to 300 words with a 50-word overlap, cut at paragraph or sentence boundaries. Each chunk keeps its character offsets, so a citation can highlight the exact span in its document." },
              { title: "Embed and index", body: <>Chunks are embedded with {models.EMBEDDING_MODEL} into the Milvus collection <Code>nexus_chunks</Code>, which also holds a BM25 index on the text. Hybrid search fuses both with reciprocal rank fusion.</> },
            ]}
          />
        </ContentSection>

        <ContentSection
          id="graph"
          title="Graph build"
          lead={`The extracted graph holds ${GRAPH_STATS.nodes} entities and ${GRAPH_STATS.relationships.toLocaleString("en-US")} relationships in Neo4j. Every edge points back to the text that states it.`}
        >
          <Steps
            items={[
              {
                title: "Schema-guided extraction",
                body: "The LLM reads one chunk at a time against a fixed schema: five entity types, ten relation types, board roles copied verbatim in Indonesian, years only when the text states them.",
              },
              {
                title: "Verbatim-quote check",
                body: (
                  <>
                    Each relation must carry a quote of at most 300 characters copied from the chunk. The quote is located in the text; if it is not there, or an endpoint is not among the extracted entities, the relation is dropped
                    {graph ? ` (${graph.dropped_unverified} dropped as unverified in the scored build)` : ""}.
                  </>
                ),
              },
              {
                title: "Entity resolution",
                body: "Names are normalised and merged per type; stock tickers link to their companies. People with the same name are kept apart per document until an LLM adjudicator finds a concrete shared link: the same company, a family member or an event.",
              },
              {
                title: "Provenance on every edge",
                body: "Each Neo4j relationship stores the chunk ids, document ids, quotes and character spans it came from, so a graph hop in an answer can show its source sentence.",
              },
            ]}
          />
        </ContentSection>

        <ContentSection id="communities" title="Communities" lead="For questions about themes rather than facts, the graph is grouped and summarised ahead of time.">
          <Steps
            items={[
              { title: "Leiden clustering", body: "Leiden partitions the entity graph, weighting each pair by its number of relationships. Communities over 25 members are split once more into a second level." },
              { title: "Cited summaries", body: <>The LLM writes 3 to 8 sentences per community from its evidence lines. Every sentence must cite chunk ids copied from that evidence. Summaries are embedded into <Code>nexus_communities</Code>.</> },
            ]}
          />
        </ContentSection>

        <ContentSection
          id="modes"
          title="Four modes and a router"
          lead={`All modes hand the same answer model (${models.LLM_MODEL}) at most ${models.RERANKER_TOP_N} chunks. What differs is how those chunks are found.`}
        >
          <Table
            caption="Retrieval modes: how each retrieves and what the answer model sees"
            head={["Mode", "How it retrieves", "What the LLM sees"]}
            minWidth="min-w-[720px]"
            rows={MODES.map((row) => [<Code key={row.mode}>{row.mode}</Code>, row.how, row.sees])}
          />
        </ContentSection>

        <ContentSection id="verify" title="Citations and the verifier" lead="An answer is only as good as the chunk each sentence cites, so every claim is checked against it.">
          <Steps
            items={[
              {
                title: "Answer with ids",
                body: <>The answer prompt shows each chunk with its id and asks for a <Code>[chunk_id]</Code> after every factual sentence, no outside knowledge, and a fixed abstain sentence when no excerpt states the fact.</>,
              },
              {
                title: "Check each claim",
                body: "The answer is split into sentence-level claims. A claim with no citation, or citing a chunk that was not retrieved, is unsupported. The rest go to the LLM as a strict fact-checker that sees only the cited excerpts.",
              },
            ]}
          />
        </ContentSection>
      </div>
    </>
  );
}
