import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  intro: string;
  children?: ReactNode;
};

// Dark inset frame (hero style) that the floating glass nav sits on.
export function PageHeader({ eyebrow, title, intro, children }: PageHeaderProps) {
  return (
    <section data-surface="dark" className="relative mx-3 mt-3 overflow-hidden rounded-card bg-ink-night text-paper">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(90%_70%_at_85%_-10%,var(--accent)_0%,transparent_65%)]" />
      <div className="relative mx-auto grid max-w-content gap-8 px-6 pt-36 pb-14 animate-content-reveal md:grid-cols-[3fr_2fr] md:items-end md:pt-44">
        <div>
          <p className="mb-5 font-mono text-mono text-paper/60">{eyebrow}</p>
          <h1 className="text-display-sm font-normal text-balance md:text-display">{title}</h1>
        </div>
        <p className="max-w-md text-body-lg text-paper/70 md:justify-self-end">{intro}</p>
      </div>
      {children}
    </section>
  );
}
