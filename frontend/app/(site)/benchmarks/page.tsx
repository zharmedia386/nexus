import { Code, ContentSection, Table } from "@/components/content/prose";
import { JudgeBars, ModeTable, answerRows } from "@/components/eval/charts";
import { MODES, MODE_LABEL, SPOTLIGHT, BASELINE, bound, caveats, diffRow, fixed, headline, signed, signedBound, summaryRow } from "@/components/eval/derive";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { REPO_URL } from "@/lib/routes";
import { REPORT, RUN_ID } from "@/lib/showcase";
import type { Mode } from "@/lib/types";

export const metadata = { title: "Benchmarks" };

const REPORT_URL = `${REPO_URL}/blob/main/docs/report/eval-report.md`;
const overall = diffRow(REPORT, SPOTLIGHT, "all");
const byCategory = headline(REPORT)[1];
const { graph, judges, models } = REPORT;
const family = graph?.relations.by_type.FAMILY_OF;
const interval = (low: number, high: number) => `[${bound(low)}, ${bound(high)}]`;
const four = (value: number) => fixed(value, 4);

function Score({ mode }: { mode: Mode }) {
  const row = summaryRow(REPORT, mode, "all");
  if (row?.answer_match == null || row.answer_match_ci_low == null || row.answer_match_ci_high == null) return null;
  return (
    <div className="flex flex-col gap-1 border-t border-line pt-4">
      <dt className="order-2 text-ui text-muted-fg">
        {MODE_LABEL[mode]} <span className="font-mono">{interval(row.answer_match_ci_low, row.answer_match_ci_high)}</span>
      </dt>
      <dd className="order-1 font-mono text-heading tabular-nums">{fixed(row.answer_match)}</dd>
    </div>
  );
}

export default function BenchmarksPage() {
  return (
    <>
      <PageHeader
        eyebrow={`Benchmarks · run ${RUN_ID}`}
        title="What the eval measured, and how far to trust it."
        intro={`${REPORT.answerable + REPORT.unanswerable} questions with gold answers, ${MODES.length} modes, one answer model (${models.LLM_MODEL}). Every interval is a 95% bootstrap CI.`}
      />
      <div className="pb-24 md:pb-[104px]">
        <ContentSection id="headline" title="Headline" lead={`${MODE_LABEL[SPOTLIGHT]} against ${MODE_LABEL[BASELINE].toLowerCase()} on the same questions. ${byCategory ?? ""}`}>
          {overall ? (
            <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-end">
              <figure className="flex flex-col gap-2">
                <p className="text-display-sm font-normal tabular-nums">{signed(overall.mean_diff)}</p>
                <figcaption className="flex flex-col gap-1">
                  <span className="text-body text-fg">
                    {MODE_LABEL[SPOTLIGHT]} minus {MODE_LABEL[BASELINE].toLowerCase()} answer match, paired over {overall.n} answerable questions
                  </span>
                  <span className="font-mono text-caption text-muted-fg">95% CI [{signedBound(overall.ci_low)}, {signedBound(overall.ci_high)}]</span>
                </figcaption>
              </figure>
              <dl className="grid grid-cols-2 gap-6">
                <Score mode={SPOTLIGHT} />
                <Score mode={BASELINE} />
              </dl>
            </div>
          ) : null}
        </ContentSection>

        <ContentSection
          id="answer-match"
          title="Answer match by question type"
          lead={`Share of answers that name the gold entities. A dot marks the best mode in each row; the dark column is ${MODE_LABEL[SPOTLIGHT].toLowerCase()}.`}
        >
          <ModeTable caption="answer_match with 95% confidence interval, by question type and retrieval mode" modes={MODES} spotlight={SPOTLIGHT} rows={answerRows(REPORT)} minWidth="min-w-[760px]" />
        </ContentSection>

        {graph ? (
          <ContentSection
            id="graph-quality"
            title="Graph extraction quality"
            lead={`Extraction from ${graph.docs} documents scored against the planted world.${family ? ` FAMILY_OF, the relation behind spouse and in-law hops, has recall ${fixed(family.recall, 3)}.` : ""}`}
          >
            <dl className="grid grid-cols-2 gap-6 md:grid-cols-4">
              {[
                { label: "Relation F1, micro", value: four(graph.relations.micro.f1) },
                { label: "Entity F1, micro", value: four(graph.entity_micro.f1) },
                ...(graph.er ? [{ label: "Entity resolution F1", value: four(graph.er.f1) }] : []),
                { label: `Temporal accuracy, ${graph.relations.temporal_support.toLocaleString("en-US")} dated`, value: four(graph.relations.temporal_accuracy) },
              ].map((fact) => (
                <div key={fact.label} className="flex flex-col gap-1 border-t border-line pt-4">
                  <dt className="order-2 text-ui text-muted-fg">{fact.label}</dt>
                  <dd className="order-1 font-mono text-heading tabular-nums">{fact.value}</dd>
                </div>
              ))}
            </dl>
            <Table
              caption="Relation extraction precision, recall and F1 by relation type"
              head={["Relation", "Precision", "Recall", "F1", "Support"]}
              rows={Object.entries(graph.relations.by_type).map(([type, score]) => [
                <Code key={type}>{type}</Code>,
                <span key="p" className="font-mono tabular-nums">{four(score.precision)}</span>,
                <span key="r" className="font-mono tabular-nums">{four(score.recall)}</span>,
                <span key="f" className="font-mono tabular-nums">{four(score.f1)}</span>,
                <span key="s" className="font-mono tabular-nums">{score.support}</span>,
              ])}
            />
            <p className="text-ui text-muted-fg">
              {graph.dropped_unverified} extracted relations were dropped because their quote was not found in the chunk.
              {graph.er ? ` ${graph.er.collision_merges} entity-resolution merges joined different people who share a name; ticker links resolved ${graph.er.ticker_links}/${graph.er.ticker_total}.` : ""}
            </p>
          </ContentSection>
        ) : null}

        {judges?.length ? (
          <ContentSection
            id="judge"
            title="Thematic questions, judged pairwise"
            lead="On the thematic set an LLM judge also compares answers pairwise on four criteria. Each pair is judged in both orders; a disagreement counts as a tie."
          >
            <Card className="grid gap-10 p-5 md:grid-cols-2 md:p-8">
              {judges.map((judge) => (
                <JudgeBars key={`${judge.mode_a}-${judge.mode_b}`} judge={judge} />
              ))}
            </Card>
          </ContentSection>
        ) : null}

        <ContentSection id="caveats" title="Read before quoting">
          <ul className="grid gap-4 md:grid-cols-2 md:gap-x-10">
            {caveats(REPORT).map((item) => (
              <li key={item} className="flex gap-3 text-body text-fg-2">
                <span aria-hidden="true" className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-ash" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <a
            href={REPORT_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex self-start text-body text-fg underline decoration-line underline-offset-4 transition-colors duration-150 ease-std hover:decoration-fg"
          >
            Read the full report on GitHub<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </ContentSection>
      </div>
    </>
  );
}
