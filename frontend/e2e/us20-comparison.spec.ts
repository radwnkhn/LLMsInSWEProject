import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us20_history_opens_two_uploads_with_measurements_and_a_resolved_previous_fault", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signUp(page);
  await uploadSet(page);
  await uploadSet(page, { filename: "clean.mp4" });
  await page.getByRole("link", { name: "History", exact: true }).click();
  await page.getByRole("checkbox").nth(0).check();
  await page.getByRole("checkbox").nth(1).check();
  await page.getByRole("link", { name: "Compare selected uploads" }).click();
  await expect(page.getByRole("heading", { name: "Compare Squat uploads" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Key measurements" })).toBeVisible();
  await expect(page.getByText("Not detected in the newer upload", { exact: true })).toBeVisible();
  await expect(page.locator("video")).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us20-comparison-mobile.png"), fullPage: true });
});

test("us20_comparison_shows_the_earlier_fault_is_still_present", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const older = page.url().split("/").pop();
  await uploadSet(page);
  const newer = page.url().split("/").pop();
  await page.goto(`/compare?first=${newer}&second=${older}`);
  await expect(page.getByText("Still present in the newer upload", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Earlier top fix" })).toContainText("Reps 4, 5");
});

test("us20_different_lifts_are_blocked_in_history_and_in_direct_comparison_urls", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const squat = page.url().split("/").pop();
  await uploadSet(page, { lift: "Deadlift", filename: "deadlift.mp4" });
  const deadlift = page.url().split("/").pop();
  await page.goto("/history");
  await page.getByRole("checkbox").nth(0).check();
  await expect(page.getByRole("checkbox").nth(1)).toBeDisabled();
  await page.goto(`/compare?first=${squat}&second=${deadlift}`);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("same lift");
  await expect(page.locator("video")).toHaveCount(0);
});
