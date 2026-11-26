import { expect, shootElement, test, unnamedControls } from "./helpers";

test("ask: hybrid vs graph_local on the multi-hop example, path strip and evidence drawer", async ({ page }, testInfo) => {
  await page.goto("/ask");
  const ask = page.locator("#ask");
  // Default modes are hybrid + graph_local.
  await expect(ask.getByRole("button", { name: "hybrid", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(ask.getByRole("button", { name: "graph_local", exact: true })).toHaveAttribute("aria-pressed", "true");
  await ask.getByRole("button", { name: /Multi-hop/ }).click();

  const graphCard = ask.locator("article", { has: page.locator("#card-graph_local") });
  await expect(graphCard.getByText("latency")).toBeVisible({ timeout: 150_000 });
  await expect(ask.locator("article", { has: page.locator("#card-hybrid") }).getByText("latency")).toBeVisible({ timeout: 150_000 });
  await expect(graphCard.getByText(/Graph path · \d+ hops?/)).toBeVisible();

  // Hybrid can open with model self-talk, so the hero frames the graph_local card (answer + path strip).
  await shootElement(page, testInfo.project.name, "ask", graphCard);

  const citation = graphCard.getByRole("button", { name: /^Evidence \d+/ }).first();
  await citation.scrollIntoViewIfNeeded();
  await citation.click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("mark")).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(citation).toBeFocused();

  expect(await unnamedControls(page)).toEqual([]);
});
