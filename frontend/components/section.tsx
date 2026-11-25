import { Suspense, type ReactNode } from "react";
import { LazySection } from "@/components/lazy-section";
import { Reveal } from "@/components/ui/reveal";
import type { SectionId } from "@/lib/sections";

type SectionProps = {
  id: SectionId;
  tone: "paper" | "fog";
  eyebrow: string;
  title: string;
  intro: string;
  placeholderClassName: string;
  // Mount with the page; for sections that fetch nothing until the user acts.
  eager?: boolean;
  children: ReactNode;
};

// Split header over a lazily mounted body; scroll-mt clears the fixed nav (24px + 48px) plus 16px.
export function Section({ id, tone, eyebrow, title, intro, placeholderClassName, eager, children }: SectionProps) {
  return (
    <section
      id={id}
      tabIndex={-1}
      aria-labelledby={`${id}-title`}
      className={`scroll-mt-[88px] pt-24 pb-20 outline-none md:pt-[104px] md:pb-24 ${tone === "fog" ? "tone-fog" : ""}`}
    >
      <Reveal className="mx-auto mb-10 grid max-w-content gap-4 px-6 md:grid-cols-[3fr_2fr] md:items-end">
        <div>
          <p className="mb-4 font-mono text-mono text-fg-2">{eyebrow}</p>
          <h2 id={`${id}-title`} className="text-heading font-normal text-balance md:text-heading-lg">{title}</h2>
        </div>
        <p className="max-w-md text-body-lg text-fg-2 md:justify-self-end">{intro}</p>
      </Reveal>
      <Suspense fallback={<div aria-hidden="true" className={placeholderClassName} />}>
        <LazySection id={id} placeholderClassName={placeholderClassName} eager={eager}>
          {children}
        </LazySection>
      </Suspense>
    </section>
  );
}
