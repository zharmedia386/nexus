import type { Answer, EvalReport, GraphStats } from "@/lib/types";
import graphStats from "./graph-stats.json";
import report from "./report.json";
import walkthrough from "./walkthrough.json";

// JSON imports widen string unions; the files are captured API bodies.
export const WALKTHROUGH = walkthrough as unknown as { question: string; graph: Answer; baseline: Answer };
export const GRAPH_STATS = graphStats as GraphStats;
export const REPORT = report as unknown as EvalReport;
export const RUN_ID = REPORT.run_id.slice(0, 8);
