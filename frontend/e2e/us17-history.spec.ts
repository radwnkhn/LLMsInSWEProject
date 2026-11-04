import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us17_tapping_a_history_entry_opens_its_full_results", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const resultsUrl = page.url();
  await page.goto("/history");
  const entry = page.getByRole("listitem").first();
  await expect(entry).toContainText("Squat");
  await expect(entry).toContainText("Hips rise before your shoulders");
  await entry.getByRole("link").click();
  await expect(page).toHaveURL(resultsUrl);
  await expect(page.getByRole("heading", { name: "Top fix" })).toBeVisible();
  await expect(page.getByRole("listitem", { name: /^Rep \d$/ })).toHaveCount(5);
});
