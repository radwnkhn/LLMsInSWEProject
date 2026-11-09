import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us05_unanalyzable_message_has_refilm_button_that_opens_the_guide", async ({ page }) => {
  await signUp(page);
  await uploadSet(page, { filename: "no_person.mp4" });
  await expect(page.getByRole("heading", { name: "Couldn't analyze: no person found" })).toBeVisible();
  await page.getByRole("link", { name: "Refilm" }).click();
  await expect(page).toHaveURL(/\/upload\?lift=squat&guide=1$/);
  await expect(page.getByRole("dialog", { name: "Filming tips: Squat" })).toBeVisible();
});

test("us09_fallback_result_shows_the_note", async ({ page }) => {
  await signUp(page);
  // In test mode, "#fallback" in the note makes the mocked LLM fail every attempt.
  await uploadSet(page, { note: "#fallback" });
  await expect(page.getByText("Coaching feedback isn't available for this video. Here are your measurements.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Top fix" })).toHaveCount(0);
  await expect(page.getByRole("listitem", { name: /^Rep \d$/ })).toHaveCount(5);
});
