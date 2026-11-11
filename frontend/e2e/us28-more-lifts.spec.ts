import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test.use({ viewport: { width: 375, height: 812 } });

// Test mode picks the synthetic pose scenario from the file name: ohp.mp4 and rdl.mp4 have two faulty reps.
const LIFTS = [
  { label: "Overhead Press", file: "ohp.mp4", topFix: "Arms don't fully lock out overhead", reps: ["Rep 4", "Rep 5"] },
  { label: "Romanian Deadlift", file: "rdl.mp4", topFix: "Knees bend too much, turning it into a deadlift", reps: ["Rep 2", "Rep 3"] },
];

for (const lift of LIFTS) {
  const slug = lift.label.replace(" ", "_").toLowerCase();

  test(`us28_${slug}_filming_guide_fits_375px_without_sideways_scroll`, async ({ page }) => {
    await signUp(page);
    await page.getByLabel(lift.label, { exact: true }).check();
    const guide = page.getByRole("dialog", { name: `Filming tips: ${lift.label}` });
    await expect(guide).toBeVisible();
    await expect(guide.getByRole("img")).toBeVisible();
    await expect(guide).toContainText(/side view/i);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const box = await guide.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);
  });

  test(`us28_${slug}_upload_gets_a_top_fix_cue_annotated_frame_and_rep_breakdown`, async ({ page }, testInfo) => {
    await signUp(page);
    await uploadSet(page, { filename: lift.file, lift: lift.label });
    await expect(page.getByRole("region", { name: "Top fix" })).toContainText(lift.topFix);
    await expect(page.getByLabel("Cue for your next set")).toBeVisible();
    await expect(page.getByRole("button", { name: /play rep \d+/i })).toBeVisible();
    for (const rep of lift.reps) {
      await expect(page.getByRole("listitem", { name: rep })).not.toContainText("Clean");
    }
    await expect(page.getByRole("listitem", { name: "Rep 1" })).toContainText("Clean");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`us28-${slug}-results.png`), fullPage: true });
  });
}
