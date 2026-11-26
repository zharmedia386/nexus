import type { ReactNode } from "react";

type SectionProps = { id: string; title: string; lead?: ReactNode; children: ReactNode };

// Titled section with an anchor id, used to lay out the content pages.
export function ContentSection({ id, title, lead, children }: SectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="mx-auto max-w-content scroll-mt-24 px-6 pt-20 md:pt-[104px]">
      <h2 id={`${id}-title`} className="text-heading font-normal md:text-heading-lg">{title}</h2>
      {lead ? <p className="mt-4 max-w-[64ch] text-body-lg text-muted-fg">{lead}</p> : null}
      <div className="mt-10 flex flex-col gap-10">{children}</div>
    </section>
  );
}

export function Code({ children }: { children: ReactNode }) {
  return <code className="font-mono text-mono text-fg">{children}</code>;
}

export function CodeBlock({ label, children }: { label?: string; children: string }) {
  return (
    <figure data-surface="dark" className="flex min-w-0 flex-col gap-2 rounded-card bg-ink-night p-5 text-paper md:p-6">
      {label ? <figcaption className="text-ui text-paper/60">{label}</figcaption> : null}
      <pre className="overflow-x-auto rounded-control bg-paper/5 px-4 py-3 font-mono text-mono text-paper/90" tabIndex={0}>
        <code>{children}</code>
      </pre>
    </figure>
  );
}

type TableProps = { caption: string; head: string[]; rows: ReactNode[][]; minWidth?: string; firstCol?: string };

export function Table({ caption, head, rows, minWidth = "min-w-[560px]", firstCol = "" }: TableProps) {
  return (
    <div className="-mx-6 overflow-x-auto px-6" tabIndex={0} role="region" aria-label={caption}>
      <table className={`w-full border-collapse text-left ${minWidth}`}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {head.map((label, index) => (
              <th key={label} scope="col" className={`pr-6 pb-3 align-bottom text-ui font-medium text-fg-2 last:pr-0 ${index === 0 ? firstCol : ""}`}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, rowIndex) => (
            <tr key={rowIndex} className="border-t border-line">
              {cells.map((cell, cellIndex) =>
                cellIndex === 0 ? (
                  <th key={cellIndex} scope="row" className="py-4 pr-6 align-top text-body font-normal">{cell}</th>
                ) : (
                  <td key={cellIndex} className="py-4 pr-6 align-top text-body text-fg-2 last:pr-0">{cell}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p aria-hidden="true" className="sticky left-0 pt-3 text-caption text-muted-fg sm:hidden">Scroll sideways for more columns</p>
    </div>
  );
}

export function Steps({ items }: { items: { title: string; body: ReactNode }[] }) {
  return (
    <ol className="grid gap-x-10 gap-y-8 md:grid-cols-2">
      {items.map((item, index) => (
        <li key={item.title} className="flex flex-col gap-2 border-t border-line pt-5">
          <span className="font-mono text-caption text-muted-fg">{String(index + 1).padStart(2, "0")}</span>
          <span className="text-heading-sm">{item.title}</span>
          <div className="text-body text-fg-2">{item.body}</div>
        </li>
      ))}
    </ol>
  );
}
