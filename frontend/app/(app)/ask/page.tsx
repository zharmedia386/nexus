import { Suspense } from "react";
import { AskView } from "@/components/ask/ask-view";
import { PageHeader } from "@/components/page-header";

export const metadata = { title: "Ask" };

export default function AskPage() {
  return (
    <>
      <PageHeader
        title="Ask once, compare every mode."
        intro="Run up to three retrieval modes side by side. Every citation opens the exact span of the source document it came from."
      />
      <section id="ask" className="tone-fog pt-16 pb-20 md:pt-[104px] md:pb-24">
        <Suspense fallback={null}>
          <AskView />
        </Suspense>
      </section>
    </>
  );
}
