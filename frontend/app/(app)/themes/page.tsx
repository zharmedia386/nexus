import { Suspense } from "react";
import { ThemesSection } from "@/components/themes/themes-section";
import { PageHeader } from "@/components/page-header";

export const metadata = { title: "Themes" };

export default function ThemesPage() {
  return (
    <>
      <PageHeader
        title="Communities, summarised."
        intro="Leiden clusters of the graph, each with a generated summary grounded in the chunks that describe it."
      />
      <section id="themes" className="tone-fog pt-16 pb-20 md:pt-[104px] md:pb-24">
        <Suspense fallback={null}>
          <ThemesSection />
        </Suspense>
      </section>
    </>
  );
}
