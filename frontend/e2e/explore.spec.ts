import { expect, shoot, test, unnamedControls } from "./helpers";

test("explore: default entity, search, path finder", async ({ page }, testInfo) => {
  await page.goto("/explore");
  const explore = page.locator("#explore");
  await expect(explore.locator("#graph-canvas, [aria-labelledby=neighbour-list-title]")).toBeVisible({ timeout: 30_000 });
  await expect(explore.locator('nav[aria-label="Exploration history"] [aria-current="page"]')).not.toHaveText("…", { timeout: 30_000 });

  await explore.getByRole("combobox", { name: "Entity" }).fill("Nusantara");
  const option = explore.getByRole("option").filter({ hasText: "Nusantara" }).first();
  await expect(option).toBeVisible({ timeout: 15_000 });
  const picked = (await option.locator("span.truncate").first().textContent())?.trim() ?? "";
  await option.click();
  await expect(explore.locator('nav[aria-label="Exploration history"] [aria-current="page"]')).toHaveText(picked);

  await explore.getByRole("combobox", { name: "From" }).fill("Nusantara Mulia");
  await explore.getByRole("option").filter({ hasText: "Nusantara Mulia" }).first().click();
  await explore.getByRole("combobox", { name: "To" }).fill("PT Bintang Kreasi Tbk");
  await explore.getByRole("option").filter({ hasText: "Bintang Kreasi" }).first().click();
  await expect(explore.getByText(/Graph path · [1-9]\d* hops?/)).toBeVisible({ timeout: 30_000 });

  await shoot(page, testInfo.project.name, "explore");
  expect(await unnamedControls(page)).toEqual([]);
});

test("themes: expand first card, member chip opens Explore on that entity", async ({ page }, testInfo) => {
  await page.goto("/themes");
  const themes = page.locator("#themes");
  const toggle = themes.locator('button[aria-controls^="community-panel-"]').first();
  await expect(toggle).toBeVisible({ timeout: 30_000 });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await shoot(page, testInfo.project.name, "themes");

  const chip = themes.locator('ul[aria-label^="Members of"]').first().getByRole("button").first();
  const name = (await chip.textContent())?.trim() ?? "";
  expect(name).not.toBe("");
  await chip.click();
  await expect(page).toHaveURL(/[?&]e=/);
  await expect(page.locator('#explore nav[aria-label="Exploration history"] [aria-current="page"]')).toHaveText(name, { timeout: 30_000 });
});
