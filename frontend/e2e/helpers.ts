import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

// A 12-second VP9-in-MP4 clip (plays in Playwright's Chromium). The backend's test mode picks the
// synthetic pose scenario from the file name, so one clip can stand in for every scenario.
const CLIP = readFileSync(path.join(__dirname, "fixtures", "set.mp4"));

// In test mode the backend makes accounts at the reserved admin.test domain admins (US-25 browser tests).
export async function signUp(page: Page, { admin = false } = {}) {
  const email = `lifter-${Date.now()}-${Math.floor(Math.random() * 1e6)}@${admin ? "admin.test" : "virginia.edu"}`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("squat1234");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  return email;
}

export async function uploadSet(page: Page, { filename = "set.mp4", lift = "Squat", note = "" } = {}) {
  await page.goto("/upload");
  await page.getByLabel(lift, { exact: true }).check();
  await page.getByRole("button", { name: "Got it" }).click();
  if (note) await page.getByLabel("Anything we should know? (optional)").fill(note);
  await page.getByLabel("Video of your set").setInputFiles({ name: filename, mimeType: "video/mp4", buffer: CLIP });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page).toHaveURL(/\/results\/[\w-]+$/);
  await expect(page.getByRole("status")).toHaveCount(0, { timeout: 30_000 });
}

export async function videoTime(page: Page) {
  return page.locator("video").evaluate((v: HTMLVideoElement) => ({ time: v.currentTime, paused: v.paused }));
}
