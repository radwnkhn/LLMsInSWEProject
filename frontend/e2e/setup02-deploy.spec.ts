import { expect, test } from "@playwright/test";

// Runs against the real deployment. Set DEPLOYED_FRONTEND_URL (Vercel) to enable it, e.g. in a
// post-deploy CI job: DEPLOYED_FRONTEND_URL=https://alibi.vercel.app npx playwright test setup02
const FRONTEND = process.env.DEPLOYED_FRONTEND_URL;

test("setup02_deployed_frontend_reaches_backend_health", async ({ page }) => {
  test.skip(!FRONTEND, "set DEPLOYED_FRONTEND_URL to check the deployment");
  await page.goto(new URL("/status", FRONTEND).toString());
  await expect(page.getByRole("status")).toHaveText("Backend: ok", { timeout: 60_000 });
});

test("setup02_status_page_reports_backend_health_locally", async ({ page }) => {
  await page.goto("/status");
  await expect(page.getByRole("status")).toHaveText("Backend: ok");
});
