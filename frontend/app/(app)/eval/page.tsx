import { Suspense } from "react";
import { EvalSection } from "@/components/eval/eval-section";
import { PageHeader } from "@/components/page-header";

export const metadata = { title: "Eval" };

export default function EvalPage() {
  return (
    <>
      <PageHeader
        title="RAG, hybrid and graph, side by side."
        intro="Answer match and latency per mode and question type with 95% confidence intervals, plus graph extraction quality and an LLM judge on thematic questions."
      />
      <section id="eval" className="pt-16 pb-20 md:pt-[104px] md:pb-24">
        <Suspense fallback={null}>
          <EvalSection />
        </Suspense>
      </section>
    </>
  );
}
