import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us21_confirmed_upload_deletion_removes_it_from_history_results_and_comparison", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const deletedUrl = page.url();
  const deletedId = deletedUrl.split("/").pop();
  await uploadSet(page, { filename: "clean.mp4" });
  const keptId = page.url().split("/").pop();
  await page.getByRole("link", { name: "History", exact: true }).click();
  const trigger = page.getByRole("button", { name: "Delete upload", exact: true }).nth(1);
  await trigger.click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(2);
  await trigger.click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete upload", exact: true }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await page.goto(deletedUrl);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("couldn't find");
  await page.goto(`/compare?first=${deletedId}&second=${keptId}`);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("not found");
  await expect(page.locator("video")).toHaveCount(0);
});

test("us21_settings_deletes_account_and_protects_old_pages", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const email = await signUp(page);
  await uploadSet(page);
  const oldResult = page.url();
  const origin = new URL(oldResult).origin;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Delete account", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Delete your account?" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us21-account-confirmation-mobile.png"), fullPage: true });
  await page.getByRole("dialog").getByRole("button", { name: "Delete account", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?deleted=1$/);
  await expect(page.getByText("Your account was deleted.", { exact: true })).toBeVisible();
  await page.goto(oldResult);
  await expect(page).toHaveURL(/\/login\?next=/);
  expect(new URL(page.url()).origin).toBe(origin);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("squat1234");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Incorrect email or password");
});
