import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { signUp, videoTime } from "./helpers";

test("us04_trim_preview_and_selected_feedback_keep_full_video_timestamps", async ({ page }) => {
  await signUp(page);
  await page.getByLabel("Squat", { exact: true }).check();
  await page.getByRole("button", { name: "Got it" }).click();
  await page.getByLabel("Video of your set").setInputFiles({ name: "set.mp4", mimeType: "video/mp4", buffer: readFileSync(path.join(__dirname, "fixtures", "set.mp4")) });
  await expect(page.getByText("Full video: 12.0 seconds")).toBeVisible();
  await page.getByRole("button", { name: "Choose a segment" }).click();
  // Synthetic pose reps 2 and 3 are complete in this original-video interval.
  await page.getByRole("spinbutton", { name: "Start time (seconds)" }).fill("1.8");
  await page.getByRole("spinbutton", { name: "End time (seconds)" }).fill("5.5");
  await page.getByRole("button", { name: "Preview selection" }).click();
  await expect.poll(async () => (await videoTime(page)).paused).toBe(false);
  await expect.poll(async () => (await videoTime(page)).paused, { timeout: 10000 }).toBe(true);
  await expect(page.getByText("Selected: 3.7 seconds (1.8–5.5s)")).toBeVisible();
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page).toHaveURL(/\/results\/[\w-]+$/);
  await expect(page.getByRole("status")).toHaveCount(0, { timeout: 30000 });
  await expect(page.getByText("2 reps", { exact: true })).toBeVisible();
  await expect(page.getByText(/Analyzed 1.8–5.5s/)).toBeVisible();
  await expect(page.getByText(/estimates from video pose tracking/)).toBeVisible();
  const rep = page.getByRole("listitem", { name: "Rep 1", exact: true });
  await rep.getByRole("button").click();
  await expect.poll(async () => (await videoTime(page)).time).toBeGreaterThan(1.8);
  // The retained source remains twelve seconds long after the shorter analysis.
  await expect.poll(() => page.locator("video").evaluate((v: HTMLVideoElement) => v.duration)).toBeCloseTo(12, 0);
});
