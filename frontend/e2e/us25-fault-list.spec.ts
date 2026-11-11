import { expect, test, type Page } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

function faultRow(page: Page, lift: string, name: string) {
  return page.getByRole("region", { name: `${lift} faults`, exact: true }).getByRole("row").filter({ hasText: name });
}

async function openFaultList(page: Page) {
  await page.goto("/admin");
  await page.getByRole("link", { name: "Fault list" }).click();
  await expect(page.getByRole("heading", { name: "Fault list" })).toBeVisible();
}

test("us25_admin_edits_disables_and_reenables_a_fault_and_new_analyses_follow", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signUp(page, { admin: true });
  await openFaultList(page);
  // Exact names: "Deadlift faults" would also match "Romanian Deadlift faults" (US-28).
  for (const lift of ["Squat", "Deadlift", "Bench Press", "Overhead Press", "Romanian Deadlift"]) {
    await expect(page.getByRole("region", { name: `${lift} faults`, exact: true })).toBeVisible();
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("us25-fault-list-mobile.png"), fullPage: true });

  const original = "Hips rise before your shoulders";
  const renamed = `Hips shoot up first ${Date.now() % 100000}`;
  await faultRow(page, "Squat", original).getByRole("button", { name: "Edit" }).click();
  await page.getByRole("region", { name: "Squat faults" }).getByLabel("Display name").fill(renamed);
  await page.getByRole("region", { name: "Squat faults" }).getByRole("button", { name: "Save" }).click();
  await expect(faultRow(page, "Squat", renamed)).toBeVisible();

  await uploadSet(page);
  await expect(page.getByRole("region", { name: "Top fix" })).toContainText(renamed);

  await openFaultList(page);
  await faultRow(page, "Squat", renamed).getByRole("button", { name: "Disable" }).click();
  await expect(faultRow(page, "Squat", renamed)).toContainText("Disabled");
  await uploadSet(page);
  // The same synthetic set still has other confirmed faults; the disabled one is gone from every section.
  await expect(page.getByRole("region", { name: "Top fix" })).toBeVisible();
  await expect(page.getByText(renamed)).toHaveCount(0);

  await openFaultList(page);
  await faultRow(page, "Squat", renamed).getByRole("button", { name: "Enable" }).click();
  await expect(faultRow(page, "Squat", renamed)).toContainText("Enabled");
  await faultRow(page, "Squat", renamed).getByRole("button", { name: "Edit" }).click();
  await page.getByRole("region", { name: "Squat faults" }).getByLabel("Display name").fill(original);
  await page.getByRole("region", { name: "Squat faults" }).getByRole("button", { name: "Save" }).click();
  await uploadSet(page);
  await expect(page.getByRole("region", { name: "Top fix" })).toContainText(original);
});

test("us25_admin_adds_a_fault_from_an_existing_measurement_and_it_is_reported", async ({ page }) => {
  await signUp(page, { admin: true });
  await openFaultList(page);
  const form = page.getByRole("region", { name: "Add a fault" });
  await form.getByLabel("Lift").selectOption("bench_press");
  await expect(form.getByLabel("Measurement", { exact: true })).toHaveJSProperty("tagName", "SELECT");
  await form.getByLabel("Measurement", { exact: true }).selectOption("elbow_angle_min_deg");
  const id = `bar_stops_high_${Date.now() % 100000}`;
  await form.getByLabel("Fault ID").fill(id);
  await form.getByLabel("Display name").fill("Bar stops high above your chest");
  await form.getByLabel("Short description").fill("high touch");
  await form.getByLabel("Flag when the measurement is").selectOption("above");
  await form.getByLabel("Threshold").fill("1");
  await form.getByRole("button", { name: "Add fault" }).click();
  const row = faultRow(page, "Bench Press", "Bar stops high above your chest");
  await expect(row).toContainText("Enabled");

  await form.getByLabel("Fault ID").fill(id);
  await form.getByLabel("Display name").fill("Duplicate");
  await form.getByLabel("Short description").fill("duplicate");
  await form.getByLabel("Threshold").fill("1");
  await form.getByRole("button", { name: "Add fault" }).click();
  await expect(form.getByRole("alert")).toContainText("already has a fault");

  await uploadSet(page, { filename: "bench.mp4", lift: "Bench Press" });
  await expect(page.getByRole("region", { name: "Top fix" })).toContainText("Bar stops high above your chest");

  // Leave the shared test-mode server's fault list as the other browser tests expect it.
  await openFaultList(page);
  await faultRow(page, "Bench Press", "Bar stops high above your chest").getByRole("button", { name: "Disable" }).click();
  await expect(faultRow(page, "Bench Press", "Bar stops high above your chest")).toContainText("Disabled");
});

test("us25_non_admin_sees_403_on_the_fault_list", async ({ page }) => {
  await signUp(page);
  await page.goto("/admin/faults");
  await expect(page.getByRole("heading", { name: "403: Admins only" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Add a fault" })).toHaveCount(0);
});
