import { Suspense } from "react";
import { ExploreView } from "@/components/graph/explore-view";
import { PageHeader } from "@/components/page-header";

export const metadata = { title: "Explore" };

export default function ExplorePage() {
  return (
    <>
      <PageHeader
        title="Walk the entity graph."
        intro="Search companies, people and groups, open their neighbourhood, and trace the shortest path between any two. Every relation links to the passage it was read from."
      />
      <section id="explore" className="pt-16 pb-20 md:pt-[104px] md:pb-24">
        <Suspense fallback={null}>
          <ExploreView />
        </Suspense>
      </section>
    </>
  );
}
