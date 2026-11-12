import { expect, test, type Page } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

const HIPS = "Hips rise before your shoulders";

function faultRow(page: Page, name: string) {
  return page.getByRole("region", { name: "Squat faults", exact: true }).getByRole("row").filter({ hasText: name });
}

async function openFaultList(page: Page) {
  await page.goto("/admin");
  await page.getByRole("link", { name: "Fault list" }).click();
  await expect(page.getByRole("heading", { name: "Fault list" })).toBeVisible();
}

async function setThreshold(page: Page, value: string) {
  await faultRow(page, HIPS).getByRole("button", { name: "Edit" }).click();
  const squat = page.getByRole("region", { name: "Squat faults", exact: true });
  await squat.getByLabel(/^Threshold/).fill(value);
  await squat.getByRole("button", { name: "Save" }).click();
  await expect(faultRow(page, HIPS)).toContainText(`above ${value}°`);
}

test("us24_admin_changes_a_threshold_it_is_logged_and_only_new_analyses_use_it", async ({ page }) => {
  // The default synthetic squat raises the torso lean by about 5° on reps 1-3 and 29° on reps 4-5.
  const email = await signUp(page, { admin: true });
  await uploadSet(page);
  const before = page.url();
  await expect(page.getByRole("listitem", { name: "Rep 1" })).toContainText("Clean");

  await openFaultList(page);
  await setThreshold(page, "4");
  const log = page.getByRole("region", { name: "Threshold changes" });
  await expect(log.getByRole("row").filter({ hasText: HIPS }).first()).toContainText("10° → 4°");
  await expect(log.getByRole("row").filter({ hasText: HIPS }).first()).toContainText(email);

  await uploadSet(page);
  await expect(page.getByRole("listitem", { name: "Rep 1" })).toContainText(HIPS);

  await page.goto(before);                                   // the earlier result keeps what it reported
  await expect(page.getByRole("listitem", { name: "Rep 1" })).toContainText("Clean");

  // Invalid values are refused before anything is saved, and the threshold is put back for other tests.
  await openFaultList(page);
  await faultRow(page, HIPS).getByRole("button", { name: "Edit" }).click();
  const squat = page.getByRole("region", { name: "Squat faults", exact: true });
  await squat.getByLabel(/^Threshold/).fill("500");
  await squat.getByRole("button", { name: "Save" }).click();
  await expect(squat.getByRole("alert")).toContainText("between 0 and 180");
  await squat.getByRole("button", { name: "Cancel" }).click();
  await setThreshold(page, "10");
  await expect(log.getByRole("row").filter({ hasText: HIPS }).first()).toContainText("4° → 10°");
});
