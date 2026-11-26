import { PipelineDiagram } from "@/components/content/pipeline-diagram";
import { REPORT } from "@/lib/showcase";

const { models } = REPORT;

export function Pipeline() {
  return (
    <section aria-labelledby="pipeline-title" className="mx-auto max-w-content px-6 pt-24 md:pt-[104px]">
      <h2 id="pipeline-title" className="text-heading font-normal md:text-heading-lg">Under the hood</h2>
      <p className="mt-4 mb-12 max-w-[60ch] text-body-lg text-muted-fg">
        Everything runs on one machine: three stores, a Python API and this site. Models are served through a local gateway.
      </p>
      <PipelineDiagram />
      <p className="mt-12 flex flex-wrap gap-x-6 gap-y-2 border-t border-line pt-5 font-mono text-caption text-muted-fg">
        <span>answers and verification · <span className="text-fg">{models.LLM_MODEL}</span></span>
        <span>embeddings · <span className="text-fg">{models.EMBEDDING_MODEL}</span></span>
        <span>rerank · <span className="text-fg">{models.RERANKER_MODEL}</span></span>
      </p>
    </section>
  );
}
