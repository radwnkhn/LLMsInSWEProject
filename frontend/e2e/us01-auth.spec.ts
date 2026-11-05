import { expect, test } from "@playwright/test";

import { signUp } from "./helpers";

test("us01_after_logging_out_history_redirects_to_login", async ({ page }) => {
  await signUp(page);
  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "Your uploads" })).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/history");
  await expect(page).toHaveURL(/\/login\?next=%2Fhistory$/);
});

test("us01_wrong_password_shows_message", async ({ page }) => {
  const email = await signUp(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("not-my-password");
  await page.getByRole("button", { name: "Log in" }).click();
  // Scoped to <main>: Next.js adds its own empty role="alert" route announcer.
  await expect(page.getByRole("main").getByRole("alert")).toHaveText("Incorrect email or password");
  await expect(page).toHaveURL(/\/login/);
});
