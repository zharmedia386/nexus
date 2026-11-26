import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TENANT = process.env.NEXT_PUBLIC_TENANT ?? "demo";
const OUT = new URL("../lib/showcase/", import.meta.url);
const QUESTION = "At which company does the spouse of the Direktur Utama of Cahaya Teguh since 2015 currently serve as Komisaris Utama since 2019?";

const call = async (path: string, body?: unknown) => {
  const response = await fetch(`${API_URL}${path}`, {
    method: body ? "POST" : "GET",
    headers: { "X-Tenant": TENANT, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(300_000),
  });
  if (!response.ok) throw new Error(`${path} -> HTTP ${response.status}`);
  return response.json();
};

const check = (ok: boolean, message: string) => {
  if (!ok) throw new Error(`Capture rejected, nothing written: ${message}`);
};

const REPORT_PATH = new URL("../../docs/report/eval-report.json", import.meta.url);

try {
  const report = JSON.parse(readFileSync(REPORT_PATH, "utf8"));
  check(String(report.run_id).startsWith("96950f8a"), `report run_id ${report.run_id}`);
  const [graph, baseline, stats] = await Promise.all([
    call("/query", { question: QUESTION, mode: "graph_local", verify: true }),
    call("/query", { question: QUESTION, mode: "hybrid", verify: true }),
    call("/graph/stats"),
  ]);
  const names: string[] = graph.graph_paths?.[0]?.node_names ?? [];
  check(graph.mode === "graph_local", "graph mode");
  check(graph.text.includes("PT Karya Semesta"), "graph answer misses PT Karya Semesta");
  check(["Zaenab Thamrin", "Raden Prasasta", "PT Karya Semesta"].every((name) => names.includes(name)), "graph path nodes");
  check(baseline.abstained === true, "hybrid should abstain");
  check(stats.nodes === 375 && stats.relationships === 1142, `graph stats ${stats.nodes}/${stats.relationships}`);

  mkdirSync(OUT, { recursive: true });
  writeFileSync(new URL("walkthrough.json", OUT), JSON.stringify({ question: QUESTION, graph, baseline }, null, 2) + "\n");
  writeFileSync(new URL("graph-stats.json", OUT), JSON.stringify(stats, null, 2) + "\n");
  copyFileSync(REPORT_PATH, new URL("report.json", OUT));
  console.log("showcase fixtures written");
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
