import Link from "next/link";
import { buttonClass } from "@/components/ui/button";
import { REPO_URL } from "@/lib/routes";

// From the README quickstart; keep in sync with it.
const COMMANDS = [
  { label: "Install and start the API", note: "in backend/", command: "cd backend && uv sync && uv run uvicorn nexus.api.app:create_app --factory --port 8000" },
  { label: "Ingest the corpus and build the graph", note: "second terminal, in backend/; restart the API afterwards", command: "uv run nexus ingest && uv run nexus graph extract && uv run nexus graph build" },
  { label: "Start the site", note: "from the repo root", command: "cd frontend && npm i && npm run dev" },
];

export function RunIt() {
  return (
    <section aria-labelledby="run-title" className="mx-auto max-w-content px-6 pt-24 pb-24 md:pt-[104px] md:pb-[104px]">
      <div className="grid gap-10 lg:grid-cols-[2fr_3fr] lg:items-start">
        <div className="flex flex-col gap-4">
          <h2 id="run-title" className="text-heading font-normal md:text-heading-lg">Run it yourself</h2>
          <p className="max-w-[48ch] text-body-lg text-muted-fg">
            Needs Postgres, Milvus and Neo4j running, a <code className="font-mono text-mono text-fg">.env</code> copied from <code className="font-mono text-mono text-fg">.env.example</code>, and <code className="font-mono text-mono text-fg">uv run nexus db migrate</code> once.
          </p>
          <div className="mt-2 flex flex-wrap gap-3">
            <Link href="/docs" className={buttonClass("primary")}>Read the Docs</Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer" className={buttonClass("secondary")}>GitHub<span className="sr-only"> (opens in a new tab)</span></a>
          </div>
        </div>
        <ol data-surface="dark" className="flex min-w-0 flex-col gap-6 rounded-card bg-ink-night p-5 text-paper md:p-8">
          {COMMANDS.map((item, index) => (
            <li key={item.label} className="flex min-w-0 flex-col gap-2">
              <p className="flex flex-wrap items-baseline gap-x-3 text-ui">
                <span className="font-mono text-paper/50">{index + 1}</span>
                <span>{item.label}</span>
                <span className="text-caption text-paper/50">{item.note}</span>
              </p>
              <pre className="overflow-x-auto rounded-control bg-paper/5 px-4 py-3 font-mono text-mono text-paper/90" tabIndex={0}>
                <code>{item.command}</code>
              </pre>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
