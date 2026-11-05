import { expect, test } from "@playwright/test";

import { signUp } from "./helpers";

test.use({ viewport: { width: 375, height: 812 } });

for (const lift of ["Squat", "Deadlift", "Bench Press"]) {
  test(`us03_guide_fits_375px_without_sideways_scroll_${lift.replace(" ", "_").toLowerCase()}`, async ({ page }) => {
    await signUp(page);
    await page.getByLabel(lift, { exact: true }).check();
    const guide = page.getByRole("dialog", { name: `Filming tips: ${lift}` });
    await expect(guide).toBeVisible();
    await expect(guide.getByRole("img")).toBeVisible();
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(clientWidth).toBe(375);
    expect(scrollWidth).toBeLessThanOrEqual(375);
    const box = await guide.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);
  });
}
