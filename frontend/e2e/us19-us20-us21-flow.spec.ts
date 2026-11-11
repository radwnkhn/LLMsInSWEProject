import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us19_us20_us21_retry_compare_delete_upload_and_account", async ({ page }) => {
  const email = await signUp(page);
  let uploadRequests = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/uploads") uploadRequests++;
  });

  // US-19: a failed worker retries the saved video without uploading it again.
  await uploadSet(page, { filename: `fail_once-cross-story-${Date.now()}.mp4` });
  const failedUrl = page.url();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Something went wrong analyzing this video");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page).not.toHaveURL(failedUrl);
  await expect(page.getByRole("heading", { name: "Top fix" })).toBeVisible();
  const retriedUrl = page.url();
  const retriedId = new URL(retriedUrl).pathname.split("/").pop()!;
  expect(uploadRequests).toBe(1);

  // US-20: the successful retry can be compared with a newer, improved upload.
  await uploadSet(page, { filename: "cross-story-clean.mp4" });
  const keptUrl = page.url();
  const keptId = new URL(keptUrl).pathname.split("/").pop()!;
  expect(uploadRequests).toBe(2);
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(page.getByRole("listitem")).toHaveCount(3);
  const retryRow = page.getByRole("listitem").filter({ has: page.locator(`a[href="/results/${retriedId}"]`) });
  const keptRow = page.getByRole("listitem").filter({ has: page.locator(`a[href="/results/${keptId}"]`) });
  await retryRow.getByRole("checkbox").check();
  await keptRow.getByRole("checkbox").check();
  await page.getByRole("link", { name: "Compare selected uploads" }).click();
  await expect(page.getByRole("table", { name: "Key measurements" })).toBeVisible();
  await expect(page.getByText("Not detected in the newer upload", { exact: true })).toBeVisible();
  await expect(page.locator("video")).toHaveCount(2);
  const comparisonUrl = page.url();

  // US-21: deleting the retried upload removes both attempts and its comparison selection.
  await page.getByRole("link", { name: "History", exact: true }).click();
  await retryRow.getByRole("checkbox").check();
  await keptRow.getByRole("checkbox").check();
  await retryRow.getByRole("button", { name: "Delete upload", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete upload", exact: true }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(keptRow).toBeVisible();
  await expect(page.getByRole("button", { name: "Compare selected uploads", exact: true })).toBeDisabled();
  for (const url of [failedUrl, retriedUrl]) {
    await page.goto(url);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("couldn't find");
  }
  await page.goto(comparisonUrl);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("not found");
  await expect(page.locator("video")).toHaveCount(0);
  await page.goto(keptUrl);
  await expect(page.getByText("No major issues found", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Rep by rep" })).toBeVisible();

  // Account deletion removes the remaining upload and prevents reuse of its session/credentials.
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Delete account", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete account", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?deleted=1$/);
  await expect(page.getByText("Your account was deleted.", { exact: true })).toBeVisible();
  await page.goto(keptUrl);
  await expect(page).toHaveURL(/\/login\?next=/);
  expect(new URL(page.url()).origin).toBe(new URL(keptUrl).origin);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("squat1234");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Incorrect email or password");
});
