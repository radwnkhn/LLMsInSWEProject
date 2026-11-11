import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

// Test mode prices the mocked LLM ("mock-coach") from its own entry, so costs show without a real provider.
test("us26_admin_sees_cost_per_attempt_and_a_summary_including_retries", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signUp(page, { admin: true });
  await uploadSet(page);
  await uploadSet(page, { note: "#fallback" }); // three failed attempts: correction retries
  const fallback = page.url().split("/").pop();

  await page.goto("/admin");
  const summary = page.getByRole("region", { name: "AI cost" });
  await expect(summary).toContainText("Total cost");
  await expect(summary).toContainText(/Total cost\$\d/);
  await expect(summary).toContainText(/Spent on correction retries([1-9]\d?|100)%/);
  await expect(summary).not.toContainText("unknown cost");

  await page.goto(`/admin/analyses/${fallback}`);
  const attempts = page.getByRole("article");
  await expect(attempts).toHaveCount(3);
  await expect(attempts.first()).toContainText("mock · mock-coach");
  await expect(attempts.first()).toContainText(/\d+ in \/ \d+ out tokens/);
  await expect(attempts.first()).toContainText(/\$\d/);
  await expect(page.getByRole("region", { name: "AI usage" })).toContainText(/\$\d/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us26-ai-usage-mobile.png"), fullPage: true });
});

test("us26_non_admin_cannot_see_costs", async ({ page }) => {
  await signUp(page);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "403: Admins only" })).toBeVisible();
  await expect(page.getByRole("region", { name: "AI cost" })).toHaveCount(0);
});
