import { expect, loadAllSections, test } from "./helpers";

test("reduced motion: no running animations after load", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  const running = () => page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running").map((animation) => animation.id || String((animation.effect as KeyframeEffect | null)?.target?.className)));
  expect(await running()).toEqual([]);
  await loadAllSections(page);
  await page.waitForTimeout(1000);
  expect(await running()).toEqual([]);
});
