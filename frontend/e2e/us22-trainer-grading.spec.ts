import { expect, test } from "@playwright/test";

import { signUp, uploadSet } from "./helpers";

test("us22_admin_assigns_a_sample_and_a_trainer_grades_it_blind", async ({ browser }) => {
  const lifterPage = await (await browser.newContext()).newPage();
  const lifterEmail = await signUp(lifterPage);
  await uploadSet(lifterPage, { note: "Sam here, my left knee clicked" });

  const trainerPage = await (await browser.newContext()).newPage();
  const trainerEmail = await signUp(trainerPage, { trainer: true });

  const adminPage = await (await browser.newContext()).newPage();
  await signUp(adminPage, { admin: true });
  await adminPage.goto("/admin");
  await adminPage.getByRole("link", { name: "Trainer grading" }).click();
  const form = adminPage.getByRole("region", { name: "Assign a sample" });
  await form.getByLabel("Trainer").selectOption({ label: trainerEmail });
  await form.getByLabel("Number of analyses").fill("1");
  await form.getByRole("button", { name: "Assign" }).click();
  await expect(form.getByRole("status")).toContainText("Assigned 1 of 1");
  const assignments = adminPage.getByRole("region", { name: "Assignments" });
  await expect(assignments.getByRole("row").filter({ hasText: trainerEmail })).toContainText("To grade");

  // The trainer sees the video and the fault list, but none of our feedback and nothing about the lifter.
  await trainerPage.goto("/grading");
  await trainerPage.getByRole("link", { name: /To grade/ }).first().click();
  const own = trainerPage.getByRole("region", { name: "Your top fault" });
  await expect(own).toBeVisible();
  await expect(trainerPage.locator("video")).toBeVisible();
  await expect(trainerPage.getByRole("region", { name: "Our feedback" })).toHaveCount(0);
  for (const hidden of [lifterEmail, "Sam here", "set.mp4"]) await expect(trainerPage.getByText(hidden)).toHaveCount(0);

  await own.getByRole("radio").first().check();
  await own.getByRole("button", { name: "Save my answer" }).click();
  await expect(trainerPage.getByRole("region", { name: "Our feedback" })).toBeVisible();
  await expect(trainerPage.getByRole("button", { name: "Save my answer" })).toHaveCount(0);
  const grade = trainerPage.getByRole("region", { name: "Your grade" });
  await grade.getByLabel("Correct", { exact: true }).check();
  await grade.getByRole("button", { name: "Save grade" }).click();
  await expect(grade.getByRole("status")).toContainText("Saved: Correct");

  await adminPage.reload();
  const row = adminPage.getByRole("region", { name: "Assignments" }).getByRole("row").filter({ hasText: trainerEmail });
  await expect(row).toContainText("Graded");
  await expect(row).toContainText("Correct");

  // Lifters and admins can't use the trainer pages.
  await lifterPage.goto("/grading");
  await expect(lifterPage.getByRole("heading", { name: "403: Trainers only" })).toBeVisible();
});
