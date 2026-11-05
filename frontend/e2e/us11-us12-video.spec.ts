import { expect, test } from "@playwright/test";

import { signUp, uploadSet, videoTime } from "./helpers";

test("us11_tapping_the_frame_plays_the_video_from_the_start_of_that_rep", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const button = page.getByRole("button", { name: /play rep \d+/i });
  const repStart = Number(await button.getAttribute("data-rep-start"));
  expect(repStart).toBeGreaterThan(0);
  await button.click();
  await expect.poll(async () => (await videoTime(page)).paused).toBe(false);
  const { time } = await videoTime(page);
  expect(time).toBeGreaterThanOrEqual(repStart - 0.05);
  expect(time).toBeLessThan(repStart + 1.5);
});

test("us12_tapping_a_rep_row_jumps_the_video_to_that_rep", async ({ page }) => {
  await signUp(page);
  await uploadSet(page);
  const row = page.getByRole("listitem", { name: "Rep 3" });
  const repStart = Number(await row.getByRole("button").getAttribute("data-rep-start"));
  await row.getByRole("button").click();
  await expect.poll(async () => (await videoTime(page)).time).toBeGreaterThanOrEqual(repStart - 0.05);
  expect((await videoTime(page)).time).toBeLessThan(repStart + 1.5);
});
