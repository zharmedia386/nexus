import { Code, CodeBlock, ContentSection, Steps, Table } from "@/components/content/prose";
import { PageHeader } from "@/components/page-header";
import { REPO_URL } from "@/lib/routes";

export const metadata = { title: "Docs" };

// Keys mirror .env.example; values stay out of the site on purpose.
const ENV: { group: string; keys: [string, string][] }[] = [
  {
    group: "Model gateway",
    keys: [
      ["LLM_BASE_URL", "OpenAI-compatible gateway serving all three models"],
      ["LLM_API_KEY", "Gateway key; secret, never commit it"],
      ["LLM_MODEL", "Answers, extraction, summaries, routing and verification"],
      ["EMBEDDING_MODEL", "Chunk and community embeddings"],
      ["RERANKER_ENABLED", "Turns reranking off for hybrid and graph modes"],
      ["RERANKER_MODEL", "Reranker behind hybrid, graph_local and graph_global"],
      ["RERANKER_TEMPLATE", "qwen3 wraps inputs in the Qwen3 reranker chat template"],
      ["RERANKER_TOP_N", "Chunks handed to the answer prompt"],
      ["RETRIEVAL_TOP_K", "Candidates fetched from Milvus before reranking"],
      ["SIMILARITY_THRESHOLD", "Cosine cut-off for rag"],
    ],
  },
  {
    group: "Milvus",
    keys: [
      ["MILVUS_HOST", "Milvus server host"],
      ["MILVUS_PORT", "Milvus gRPC port"],
      ["MILVUS_SEARCH_NPROBE", "IVF clusters probed per dense search"],
      ["MILVUS_COLLECTION_PREFIX", "Must start with nexus_"],
    ],
  },
  {
    group: "Postgres",
    keys: [
      ["POSTGRES_HOST", "Postgres host"],
      ["POSTGRES_PORT", "5432 for a local server, 5433 for the compose file"],
      ["POSTGRES_USER", "Database user"],
      ["POSTGRES_PASSWORD", "Secret"],
      ["POSTGRES_DB", "Database name"],
    ],
  },
  {
    group: "Neo4j",
    keys: [
      ["NEO4J_URI", "Bolt URI"],
      ["NEO4J_USER", "Database user"],
      ["NEO4J_PASSWORD", "Secret; the compose file refuses to start without it"],
    ],
  },
  { group: "API", keys: [["CORS_ORIGINS", "Comma-separated origins allowed to call the API"]] },
];

const SETUP = `cp .env.example .env        # fill LLM_API_KEY, POSTGRES_PASSWORD, NEO4J_PASSWORD
cd backend
uv sync
uv run nexus check          # pings Postgres, Milvus, Neo4j and the gateway
uv run nexus db migrate`;

const PIPELINE = `uv run nexus datagen world --seed 42   # only to regenerate; the world is committed
uv run nexus datagen docs
uv run nexus datagen reference        # ticker table
uv run nexus ingest
uv run nexus graph extract
uv run nexus graph build
uv run nexus graph eval
uv run nexus graph communities
uv run nexus graph summarize`;

const EVAL = `uv run nexus eval questions
uv run nexus eval run --modes rag,hybrid,graph_local,graph_global,auto
uv run nexus eval rescore-claims --run <run-id> --verify
uv run nexus eval judge --run <run-id> --a graph_global --b hybrid --categories thematic
uv run nexus eval report --run <run-id> --rescored --graph ../eval/runs/graph-<ts>.json --judge ../eval/runs/judge-<run-id>-graph_global-vs-hybrid.json`;

const SERVE = `cd backend && uv run uvicorn nexus.api.app:create_app --factory --port 8000
cd frontend && cp .env.example .env.local && npm i && npm run dev`;

const ENDPOINTS: [string, string, string][] = [
  ["POST", "/query", "Answer a question. Body: question, mode (rag, hybrid, graph_local, graph_global, auto), verify (default true)."],
  ["GET", "/documents/{doc_id}", "One document with its full text and metadata."],
  ["GET", "/chunks/{chunk_id}", "One chunk with its character offsets in the document."],
  ["GET", "/graph/entity/{entity_id}", "An entity and up to 40 of its relationships."],
  ["GET", "/graph/path", "Shortest path of up to 4 hops between ?from= and ?to= entity ids, or null."],
  ["GET", "/graph/search", "Entities matching ?q= (2 to 80 characters), ?limit= up to 50."],
  ["GET", "/graph/stats", "Node and relationship counts, counts by type and the best-connected entities."],
  ["GET", "/eval/report", "The latest eval report as JSON; 404 until one is generated."],
  ["GET", "/communities", "Community summaries; ?level= 0 (top) or 1 (split communities)."],
  ["GET", "/health", "ok or down for postgres, milvus, gateway and neo4j."],
];

export default function DocsPage() {
  return (
    <>
      <PageHeader
        title="Run NEXUS on your own machine."
        intro="Three stores, a Python API and this site. Setup, the pipeline commands, the API and the failures you are most likely to hit."
      />
      <div className="pb-24 md:pb-[104px]">
        <ContentSection id="prerequisites" title="Prerequisites">
          <Steps
            items={[
              { title: "Python 3.12 and uv", body: <>The backend pins Python 3.12 and installs with <Code>uv sync</Code>.</> },
              { title: "Node 22 or newer", body: "For the Next.js site and its Playwright tests." },
              { title: "Postgres, Neo4j, Milvus", body: <>Postgres and Neo4j run locally (or via <Code>infra/compose.yaml</Code> with Podman). Milvus can be local or shared; NEXUS only touches its own collections.</> },
              { title: "A model gateway", body: "An OpenAI-compatible endpoint serving the answer model, the embedding model and the reranker." },
            ]}
          />
        </ContentSection>

        <ContentSection
          id="setup"
          title="Setup"
          lead={<>Copy <Code>.env.example</Code> to <Code>.env</Code> at the repo root. It ships with keys only; fill the three secrets before the first run.</>}
        >
          <CodeBlock label="From the repo root">{SETUP}</CodeBlock>
          <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
            <div className="flex flex-col gap-2 border-t border-line pt-5">
              <h3 className="text-heading-sm">Postgres</h3>
              <p className="text-body text-fg-2">
                A local server on 5432, or <Code>podman-compose --env-file .env -f infra/compose.yaml up -d</Code> and set <Code>POSTGRES_PORT=5433</Code>. Run <Code>nexus db migrate</Code> once.
              </p>
            </div>
            <div className="flex flex-col gap-2 border-t border-line pt-5">
              <h3 className="text-heading-sm">Neo4j</h3>
              <p className="text-body text-fg-2">
                <Code>brew install neo4j && brew services start neo4j</Code>, or the compose file. Set <Code>NEO4J_PASSWORD</Code> to match.
              </p>
            </div>
            <div className="flex flex-col gap-2 border-t border-line pt-5 md:col-span-2">
              <h3 className="text-heading-sm">Milvus prefix rule</h3>
              <p className="max-w-[72ch] text-body text-fg-2">
                Milvus may be shared infrastructure, so the backend config rejects any <Code>MILVUS_COLLECTION_PREFIX</Code> that does not begin with <Code>nexus_</Code>. It creates and reads only <Code>nexus_chunks</Code> and <Code>nexus_communities</Code>.
              </p>
            </div>
          </div>
          {ENV.map((section) => (
            <div key={section.group} className="flex flex-col gap-4">
              <h3 className="text-heading-sm">{section.group}</h3>
              <Table caption={`${section.group} environment keys`} head={["Key", "What it sets"]} rows={section.keys.map(([key, note]) => [<Code key={key}>{key}</Code>, note])} minWidth="min-w-[520px]" firstCol="w-[45%]" />
            </div>
          ))}
        </ContentSection>

        <ContentSection id="pipeline" title="Pipeline" lead={<>Run from <Code>backend/</Code>, in this order. Every command takes <Code>--help</Code>; most take <Code>--tenant</Code> (default <Code>demo</Code>).</>}>
          <CodeBlock label="Corpus, ingestion and graph">{PIPELINE}</CodeBlock>
          <CodeBlock label="Evaluation">{EVAL}</CodeBlock>
          <CodeBlock label="API and site, in two terminals">{SERVE}</CodeBlock>
        </ContentSection>

        <ContentSection
          id="api"
          title="API"
          lead={<>FastAPI on port 8000. Query, document, chunk and graph endpoints read the <Code>X-Tenant</Code> header (default <Code>demo</Code>); it selects a dataset and is not an access control.</>}
        >
          <Table
            caption="API endpoints"
            head={["Path", "Method", "Returns"]}
            minWidth="min-w-[640px]"
            rows={ENDPOINTS.map(([method, path, note]) => [<Code key={path}>{path}</Code>, <span key="m" className="font-mono text-mono">{method}</span>, note])}
          />
        </ContentSection>

        <ContentSection id="troubleshooting" title="Troubleshooting">
          <Steps
            items={[
              {
                title: "Gateway down",
                body: <><Code>/query</Code> returns 502 with “upstream model gateway error”, and <Code>/health</Code> reports gateway down. Check <Code>LLM_BASE_URL</Code>, the key, and that all three models are listed: <Code>nexus check</Code> names any missing one.</>,
              },
              {
                title: "Milvus unreachable",
                body: <><Code>/health</Code> reports milvus down and <Code>/query</Code> fails for every mode. Check <Code>MILVUS_HOST</Code> and <Code>MILVUS_PORT</Code>, then the prefix rule above.</>,
              },
              {
                title: "graph_local ignores new entities",
                body: <>Restart the API after every <Code>nexus graph build</Code>. The entity lexicon that links question names to the graph is loaded once per process.</>,
              },
              {
                title: "The site cannot reach the API",
                body: <>Add the site origin to <Code>CORS_ORIGINS</Code> and point <Code>NEXT_PUBLIC_API_URL</Code> in <Code>frontend/.env.local</Code> at the API.</>,
              },
            ]}
          />
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex self-start text-body text-fg underline decoration-line underline-offset-4 transition-colors duration-150 ease-std hover:decoration-fg">
            Source and README on GitHub<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </ContentSection>
      </div>
    </>
  );
}
