import Link from "next/link";
import { APP_PAGES, CONTENT_PAGES, REPO_URL } from "@/lib/routes";

const linkClass = "text-muted-fg transition-colors duration-150 ease-std hover:text-fg";

function Column({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-ui font-medium">{title}</h2>
      <ul className="flex flex-col gap-2 text-ui">{children}</ul>
    </div>
  );
}

export function SiteFooter({ runId }: { runId: string }) {
  return (
    <footer className="mx-auto grid max-w-content gap-10 px-6 py-12 text-ui md:grid-cols-4">
      <Column title="Product">
        {APP_PAGES.map((page) => (
          <li key={page.href}><Link href={page.href} className={linkClass}>{page.label}</Link></li>
        ))}
      </Column>
      <Column title="Learn">
        {CONTENT_PAGES.map((page) => (
          <li key={page.href}><Link href={page.href} className={linkClass}>{page.label}</Link></li>
        ))}
      </Column>
      <Column title="Project">
        <li><a href={REPO_URL} target="_blank" rel="noreferrer" className={linkClass}>GitHub<span className="sr-only"> (opens in a new tab)</span></a></li>
        <li className="text-muted-fg">Eval run {runId}</li>
      </Column>
      <div className="flex flex-col gap-2 text-muted-fg">
        <p>Neo4j · Milvus · Postgres · LangGraph · FastAPI · Next.js</p>
        <p>All companies and people are fictional.</p>
      </div>
    </footer>
  );
}
