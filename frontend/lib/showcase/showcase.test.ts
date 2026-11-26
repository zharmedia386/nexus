import { describe, expect, it } from "vitest";
import { GRAPH_STATS, RUN_ID, WALKTHROUGH } from "@/lib/showcase";

describe("showcase fixtures", () => {
  it("holds the committed walkthrough, stats and run id", () => {
    expect(WALKTHROUGH.question).toBe("At which company does the spouse of the Direktur Utama of Cahaya Teguh since 2015 currently serve as Komisaris Utama since 2019?");
    expect(WALKTHROUGH.graph.mode).toBe("graph_local");
    expect(WALKTHROUGH.graph.text).toContain("PT Karya Semesta");
    expect(WALKTHROUGH.graph.graph_paths[0].node_names).toEqual(expect.arrayContaining(["Zaenab Thamrin", "Raden Prasasta", "PT Karya Semesta"]));
    expect(WALKTHROUGH.baseline.abstained).toBe(true);
    expect(GRAPH_STATS.nodes).toBe(375);
    expect(GRAPH_STATS.relationships).toBe(1142);
    expect(RUN_ID).toBe("96950f8a");
  });
});
