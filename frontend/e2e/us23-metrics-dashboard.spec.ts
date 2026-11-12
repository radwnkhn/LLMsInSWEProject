import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

const METRICS = ["Trainer agreement", "Helpful ratings (4–5)", "Cue tried", "7-day return"];

test("us23_admin_sees_the_four_metrics_with_targets_counts_and_a_date_filter", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signUp(page, { admin: true });
  await uploadSet(page);
  await page.getByRole("radiogroup", { name: "How helpful was this feedback?" }).getByRole("radio", { name: "5" }).check();
  await page.getByRole("button", { name: "Send feedback" }).click();
  await expect(page.getByText("Thanks for the feedback!")).toBeVisible();

  await page.goto("/admin");
  await page.getByRole("link", { name: "Hypothesis metrics" }).click();
  await expect(page.getByRole("heading", { name: "Hypothesis metrics" })).toBeVisible();
  for (const name of METRICS) {
    const card = page.getByRole("region", { name });
    await expect(card).toContainText("Target:");
    await expect(card).toContainText("Based on");
  }
  await expect(page.getByRole("region", { name: "Helpful ratings (4–5)" })).not.toContainText("No data");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  // A range long before the app existed has nothing in it.
  await page.getByLabel("From").fill("2020-01-01");
  await page.getByLabel("To").fill("2020-01-31");
  await page.getByRole("button", { name: "Show" }).click();
  for (const name of METRICS) await expect(page.getByRole("region", { name })).toContainText("No data yet");

  await page.getByLabel("From").fill("2020-02-01");
  await page.getByRole("button", { name: "Show" }).click();
  await expect(page.getByRole("alert")).toContainText("on or before the end date");
});
