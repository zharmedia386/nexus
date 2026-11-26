import { expect, shoot, test, unnamedControls } from "./helpers";

const SECTION_LABELS = [
  ["ask", "Ask"],
  ["explore", "Explore"],
  ["themes", "Themes"],
  ["eval", "Eval"],
] as const;

test("home: landing hero, nav links to routes, no legacy in-page sections", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Answers that show their path");
  // The hero figures count up from 0; shoot only once each has landed on its final value.
  await page.waitForFunction(() => [...document.querySelectorAll("[data-count]")].every((element) => element.textContent === element.parentElement?.dataset.final));
  await shoot(page, testInfo.project.name, "main", "main");

  const nav = page.getByRole("navigation", { name: "Primary" });
  // The mobile project collapses the links behind the menu button.
  const menu = nav.getByRole("button", { name: "Menu" });
  if (await menu.isVisible()) await menu.click();
  for (const [href, label] of [["/how-it-works", "How it works"], ["/benchmarks", "Benchmarks"], ["/docs", "Docs"]]) {
    await expect(nav.getByRole("link", { name: label, exact: true })).toHaveAttribute("href", href);
  }
  if (await menu.isVisible()) await menu.click();
  await expect(page.locator("#ask, #explore, #themes, #eval")).toHaveCount(0);
  const film = page.locator("#film");
  await expect(film).toBeVisible();
  const video = film.locator("video");
  await expect(video).toHaveAttribute("src", "/film/nexus-demo.mp4");
  await expect(film.getByText("The film is not published yet")).toHaveCount(0);
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.duration || 0)).toBeGreaterThan(75);
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.textTracks[0]?.cues?.length ?? 0)).toBeGreaterThan(10);
  expect(await unnamedControls(page)).toEqual([]);

  await page.locator("main").getByRole("link", { name: "Open app" }).click();
  await expect(page).toHaveURL(/\/ask$/);
});

test("eval: table renders and caveats are visible", async ({ page }, testInfo) => {
  await page.goto("/eval");
  const section = page.locator("#eval");
  await expect(section.locator("table").first()).toBeVisible({ timeout: 30_000 });
  await expect(section.getByRole("heading", { name: "Read before quoting" })).toBeVisible();
  await shoot(page, testInfo.project.name, "eval");
});

test("legacy hash bookmark lands on the route", async ({ page }) => {
  await page.goto("/?q=x#ask");
  await expect(page).toHaveURL(/\/ask\?q=x/);
  await expect(page.locator("#question")).toHaveValue("x");
});

test("keyboard-only: skip link first, then nav links, then the Ask input", async ({ page }) => {
  await page.goto("/ask");
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

test("every interactive control has an accessible name on each page", async ({ page }) => {
  await page.goto("/eval");
  await expect(page.locator("#eval table").first()).toBeVisible({ timeout: 30_000 });
  expect(await unnamedControls(page)).toEqual([]);
  await page.goto("/explore");
  await expect(page.locator("#explore").locator("#graph-canvas, [aria-labelledby=neighbour-list-title]")).toBeVisible({ timeout: 30_000 });
  expect(await unnamedControls(page)).toEqual([]);
});
