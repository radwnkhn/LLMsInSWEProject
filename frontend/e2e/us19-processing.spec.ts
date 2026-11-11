import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

// Hold API snapshots at each stage: the test backend otherwise finishes between polls.
// Backend tests separately verify that these stages are persisted before the real work.
test("us19_progress_updates_without_reload_and_results_open_automatically", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signUp(page);
  let stage = "measuring";
  let original: Record<string, unknown>;
  let documents = 0;
  page.on("request", (request) => { if (request.isNavigationRequest() && request.resourceType() === "document") documents++; });
  await page.route("**/analyses/*", async (route) => {
    const response = await route.fetch();
    original = await response.json();
    await route.fulfill({ response, json: stage === "done" ? original : {
      ...original, status: "processing", final_status: null, processing_stage: stage,
    } });
  });
  // uploadSet waits for completion, so drive the upload here while snapshots remain held.
  await page.goto("/upload");
  await page.getByLabel("Squat", { exact: true }).check();
  await page.getByRole("button", { name: "Got it" }).click();
  await page.getByLabel("Video of your set").setInputFiles("e2e/fixtures/set.mp4");
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page).toHaveURL(/\/results\/[\w-]+$/);
  for (const [value, label] of [["measuring", "Measuring"], ["writing_feedback", "Writing feedback"], ["checking", "Checking"]]) {
    stage = value;
    await expect(page.getByRole("status")).toContainText(label);
    await expect(page.getByRole("list", { name: "Analysis progress" }).locator('[aria-current="step"]')).toHaveText(label);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us19-checking-mobile.png"), fullPage: true });
  const loadedDocuments = documents;
  stage = "done";
  await expect(page.getByRole("heading", { name: "Top fix" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  expect(documents).toBe(loadedDocuments);
});

test("us19_failed_analysis_retries_the_saved_video", async ({ page }) => {
  await signUp(page);
  let uploads = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/uploads") uploads++;
  });
  // Test mode simulates one transient worker failure for this filename, then succeeds.
  await uploadSet(page, { filename: `fail_once-us19-${Date.now()}.mp4` });
  const failedUrl = page.url();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Something went wrong analyzing this video");
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page).not.toHaveURL(failedUrl);
  await expect(page.getByRole("heading", { name: "Top fix" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  expect(uploads).toBe(1);
});
