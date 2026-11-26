import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

// Real stack only: no page.route anywhere in this file. Each test records one beat of the film.
const QUESTION = "At which company does the spouse of the Direktur Utama of Cahaya Teguh since 2015 currently serve as Komisaris Utama since 2019?";
const ABSTAIN = "The documents do not contain this information.";
const OUT = path.join(__dirname, "raw");

type Mark = { t: number; label: string; box?: { x: number; y: number; width: number; height: number } };

// Next dev overlay is tooling, not product; hide it so it never reads as UI.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    const hide = () => document.head?.insertAdjacentHTML("beforeend", "<style>nextjs-portal{display:none!important}</style>");
    if (document.head) hide();
    else document.addEventListener("DOMContentLoaded", hide);
  });
});

function recorder(page: Page, beat: string) {
  const start = Date.now();
  const marks: Mark[] = [];
  mkdirSync(path.join(OUT, "shots"), { recursive: true });
  return {
    mark: async (label: string, target?: Locator) => {
      const box = target ? (await target.boundingBox()) ?? undefined : undefined;
      marks.push({ t: (Date.now() - start) / 1000, label, box });
    },
    shot: async (label: string) => {
      await page.screenshot({ path: path.join(OUT, "shots", `${beat}-${label}.png`) });
      marks.push({ t: (Date.now() - start) / 1000, label: `shot:${label}` });
    },
    save: async () => {
      writeFileSync(path.join(OUT, `${beat}.marks.json`), JSON.stringify(marks, null, 2));
      const video = page.video();
      await page.close();
      await video?.saveAs(path.join(OUT, `${beat}.webm`));
    },
  };
}

async function click(rec: ReturnType<typeof recorder>, label: string, target: Locator) {
  await target.scrollIntoViewIfNeeded();
  await rec.mark(label, target);
  await target.click();
}

async function glide(page: Page, distance: number, steps = 30) {
  for (let step = 0; step < steps; step += 1) {
    await page.mouse.wheel(0, distance / steps);
    await page.waitForTimeout(16);
  }
}

test("a-abstain: plain RAG on the multi-hop question", async ({ page }) => {
  const rec = recorder(page, "a-abstain");
  await page.goto("/ask");
  await page.waitForLoadState("networkidle");
  const modes = page.getByRole("group", { name: /compare up to/i });
  await modes.getByRole("button", { name: "rag", exact: true }).click();
  await modes.getByRole("button", { name: "hybrid", exact: true }).click();
  await modes.getByRole("button", { name: "graph_local", exact: true }).click();
  await page.waitForTimeout(600);
  const input = page.getByLabel("Question");
  await click(rec, "focus-input", input);
  await rec.mark("type-start");
  await input.pressSequentially(QUESTION, { delay: 28 });
  await rec.mark("type-end");
  await page.waitForTimeout(500);
  await click(rec, "ask", page.getByRole("button", { name: "Ask" }));
  await page.waitForTimeout(300);
  await rec.mark("scroll-start");
  await glide(page, 360, 24);
  const answer = page.getByText(ABSTAIN);
  await expect(answer).toBeVisible({ timeout: 120_000 });
  await rec.mark("answer", answer);
  await page.waitForTimeout(2500);
  await rec.shot("answer");
  await page.waitForTimeout(1000);
  await rec.save();
});

test("b-ask: graph_local beside hybrid, path strip, citation", async ({ page }) => {
  const rec = recorder(page, "b-ask");
  await page.goto(`/ask?q=${encodeURIComponent(QUESTION)}&modes=hybrid,graph_local`);
  await rec.mark("asked");
  await page.waitForTimeout(1500);
  await rec.mark("scroll-1");
  await glide(page, 420, 30);
  const hybrid = page.getByRole("article", { name: "Hybrid" });
  const graph = page.locator("article", { has: page.locator("#card-graph_local") });
  await expect(hybrid.getByText(ABSTAIN)).toBeVisible({ timeout: 120_000 });
  await rec.mark("hybrid-answer");
  await expect(graph.getByText("PT Karya Semesta").first()).toBeVisible({ timeout: 180_000 });
  await rec.mark("graph-answer", graph);
  await page.waitForTimeout(2500);
  await rec.shot("answers");
  await rec.mark("scroll-2");
  await glide(page, 320);
  await page.waitForTimeout(1200);
  await rec.shot("answers-scrolled");
  const hops = graph.getByRole("button", { name: /Show quotes/ });
  await expect(hops).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    await click(rec, `hop-${index}`, hops.nth(index));
    await page.waitForTimeout(1800);
    await rec.shot(`hop-${index}`);
  }
  await click(rec, "cite", graph.getByRole("button", { name: "doc_056:0001", exact: true }));
  const drawer = page.getByRole("dialog");
  await expect(drawer.locator("mark").first()).toBeVisible({ timeout: 30_000 });
  await rec.mark("drawer", drawer);
  await page.waitForTimeout(2500);
  await rec.shot("drawer");
  await page.waitForTimeout(1000);
  await rec.save();
});

test("c-explore: Zaenab Thamrin neighbourhood", async ({ page }) => {
  const rec = recorder(page, "c-explore");
  await page.goto("/explore");
  await page.waitForLoadState("networkidle");
  const search = page.getByRole("combobox").first();
  await click(rec, "search", search);
  await search.fill("");
  await search.pressSequentially("Zaenab", { delay: 60 });
  const option = page.getByRole("option", { name: /Zaenab Thamrin/ }).first();
  await expect(option).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(600);
  await click(rec, "pick", option);
  await page.waitForTimeout(2500);
  await rec.mark("scroll-start");
  await glide(page, 420, 40);
  await page.waitForTimeout(2500);
  await rec.shot("neighbourhood");
  await rec.mark("settled");
  await page.waitForTimeout(2500);
  await rec.save();
});

test("d-themes: community cards", async ({ page }) => {
  const rec = recorder(page, "d-themes");
  await page.goto("/themes");
  await expect(page.locator("h3").first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1500);
  await rec.mark("cards");
  await rec.shot("cards");
  await glide(page, 500, 60);
  await page.waitForTimeout(1500);
  await rec.shot("cards-scrolled");
  await page.waitForTimeout(1000);
  await rec.save();
});

test("e-benchmarks: eval chart", async ({ page }) => {
  const rec = recorder(page, "e-benchmarks");
  await page.goto("/benchmarks");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  await rec.shot("top");
  await rec.mark("scroll-start");
  await glide(page, 700, 60);
  await page.waitForTimeout(1500);
  await rec.shot("chart");
  await glide(page, 700, 60);
  await page.waitForTimeout(1500);
  await rec.shot("chart-2");
  await page.waitForTimeout(1000);
  await rec.save();
});
