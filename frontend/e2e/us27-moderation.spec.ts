import { expect, test, type Page } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

async function logIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("squat1234");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

test("us27_admin_reviews_usage_and_removes_an_upload_and_the_owner_is_told", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const lifter = await signUp(page);
  await uploadSet(page);
  const resultUrl = new URL(page.url()).pathname;
  await page.getByRole("button", { name: "Log out" }).click();

  await signUp(page, { admin: true });
  await page.goto("/admin");
  await page.getByRole("link", { name: "Usage and moderation" }).click();
  const usage = page.getByRole("region", { name: "Sign-ups and uploads" });
  await expect(usage.getByText("Total sign-ups")).toBeVisible();
  await expect(usage.getByText("Total uploads")).toBeVisible();

  const uploads = page.getByRole("region", { name: "Uploads" });
  const row = uploads.getByRole("row").filter({ hasText: lifter });
  await expect(row).toHaveCount(1);
  await expect(row.getByRole("link", { name: "Analysis" })).toHaveAttribute("href", /\/admin\/analyses\/[\w-]+$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us27-moderation-mobile.png"), fullPage: true });

  // Cancelling removes nothing.
  await row.getByRole("button", { name: "Remove" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await expect(row).toHaveCount(1);

  await row.getByRole("button", { name: "Remove" }).click();
  const dialog = page.getByRole("dialog", { name: "Remove this upload?" });
  await expect(dialog.getByRole("button", { name: "Remove upload" })).toBeDisabled();
  await dialog.getByLabel("Off-topic").check();
  await dialog.getByRole("button", { name: "Remove upload" }).click();
  await expect(row).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Moderation log" }).getByRole("listitem").filter({ hasText: lifter }))
    .toContainText("Off-topic");

  await page.getByRole("button", { name: "Log out" }).click();
  await logIn(page, lifter);
  await page.goto("/history");
  await expect(page.getByText("No uploads yet.")).toBeVisible();
  await page.goto(resultUrl);
  await expect(page.getByRole("heading", { name: "This upload was removed by a moderator" })).toBeVisible();
  await expect(page.getByText(/Reason: Off-topic/)).toBeVisible();
});

test("us27_non_admin_sees_403_on_usage_and_moderation", async ({ page }) => {
  await signUp(page);
  await page.goto("/admin/moderation");
  await expect(page.getByRole("heading", { name: "403: Admins only" })).toBeVisible();
});
