import { expect, loadAllSections, shoot, test, unnamedControls } from "./helpers";

const SECTION_LABELS = [
  ["ask", "Ask"],
  ["explore", "Explore"],
  ["themes", "Themes"],
  ["eval", "Eval"],
] as const;

test("home loads and nav anchors scroll and update aria-current", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Answers that show their path");
  await shoot(page, testInfo.project.name, "main");

  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const [id, label] of SECTION_LABELS) {
    await nav.getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`#${id}$`));
    await expect(nav.getByRole("link", { name: label, exact: true })).toHaveAttribute("aria-current", "location");
    await expect(nav.locator('[aria-current="location"]')).toHaveCount(1);
  }
});

test("eval: table renders and caveats are visible", async ({ page }, testInfo) => {
  await page.goto("/#eval");
  const section = page.locator("#eval");
  await expect(section.locator("table").first()).toBeVisible({ timeout: 30_000 });
  await expect(section.getByRole("heading", { name: "Read before quoting" })).toBeVisible();
  await shoot(page, testInfo.project.name, "eval");
});

test("old route /ask?q=x redirects to /?q=x#ask", async ({ page, request }) => {
  const response = await request.get("/ask?q=x", { maxRedirects: 0 });
  expect(response.headers()["location"]).toBe("/?q=x#ask");
  await page.goto("/ask?q=x");
  // The Ask section appends its modes once it runs the shared question.
  await expect(page).toHaveURL(/\/\?q=x(&modes=[^#]*)?#ask$/);
  await expect(page.locator("#question")).toHaveValue("x");
});

test("keyboard-only: skip link first, then nav links, then the Ask input", async ({ page }) => {
  await page.goto("/");
  const order: string[] = [];
  for (let step = 0; step < 100; step++) {
    await page.keyboard.press("Tab");
    const label = await page.evaluate(() => {
      const element = document.activeElement;
      return element?.id === "question" ? "#question" : (element?.textContent ?? "").trim();
    });
    order.push(label);
    if (label === "#question") break;
  }
  expect(order[0]).toBe("Skip to content");
  for (const [, label] of SECTION_LABELS) expect(order).toContain(label);
  expect(order.at(-1)).toBe("#question");
  expect(order.indexOf("Ask")).toBeLessThan(order.indexOf("#question"));
});

test("every interactive control has an accessible name", async ({ page }) => {
  await page.goto("/");
  await loadAllSections(page);
  await expect(page.locator("#eval table").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#explore").locator("#graph-canvas, [aria-labelledby=neighbour-list-title]")).toBeVisible({ timeout: 30_000 });
  expect(await unnamedControls(page)).toEqual([]);
});
