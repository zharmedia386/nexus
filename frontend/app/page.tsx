import { AskView } from "@/components/ask/ask-view";
import { EvalSection } from "@/components/eval/eval-section";
import { ExploreView } from "@/components/graph/explore-view";
import { HomeBento } from "@/components/home-bento";
import { NetworkHero } from "@/components/network-hero";
import { PageHeader } from "@/components/page-header";
import { Section } from "@/components/section";
import { ThemesSection } from "@/components/themes/themes-section";

export default function HomePage() {
  return (
    <>
      <PageHeader
        eyebrow="GraphRAG · local-first"
        title="Answers that show their path."
        intro="NEXUS reads a corpus of filings, news and analyst notes, builds an entity graph, and answers multi-hop questions with a citation for every claim and a quote for every hop."
      >
        <NetworkHero />
      </PageHeader>
      <section className="mx-auto max-w-content px-6 pt-16 md:pt-[104px]">
        <div className="mb-10 grid gap-4 md:grid-cols-[3fr_2fr] md:items-end">
          <h2 className="text-heading font-normal md:text-heading-lg">Four ways in.</h2>
          <p className="max-w-md text-body-lg text-muted-fg md:justify-self-end">
            Ask a question, walk the graph, read the themes, or check how each retrieval mode actually scores.
          </p>
        </div>
        <HomeBento />
      </section>
      <div className="mt-16 md:mt-[104px]">
        <Section
          id="ask"
          tone="fog"
          eyebrow="01 · Ask"
          title="Ask once, compare every mode."
          intro="Run up to three retrieval modes side by side. Every citation opens the exact span of the source document it came from."
          placeholderClassName="min-h-[450px]"
          eager
        >
          <AskView />
        </Section>
        <Section
          id="explore"
          tone="paper"
          eyebrow="02 · Explore"
          title="Walk the entity graph."
          intro="Search companies, people and groups, open their neighbourhood, and trace the shortest path between any two. Every relation links to the passage it was read from."
          placeholderClassName="min-h-[820px]"
        >
          <ExploreView />
        </Section>
        <Section
          id="themes"
          tone="fog"
          eyebrow="03 · Themes"
          title="Communities, summarised."
          intro="Leiden clusters of the graph, each with a generated summary grounded in the chunks that describe it."
          placeholderClassName="min-h-[600px]"
        >
          <ThemesSection />
        </Section>
        <Section
          id="eval"
          tone="paper"
          eyebrow="04 · Eval"
          title="RAG, hybrid and graph, side by side."
          intro="Answer match and latency per mode and question type with 95% confidence intervals, plus graph extraction quality and an LLM judge on thematic questions."
          placeholderClassName="min-h-[1200px]"
        >
          <EvalSection />
        </Section>
      </div>
    </>
  );
}
