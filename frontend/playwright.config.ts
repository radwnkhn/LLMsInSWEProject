import { defineConfig, devices } from "@playwright/test";

// The e2e suite runs the real frontend against the real backend in test mode
// (ALIBI_TEST_MODE=1): in-memory database and storage, synthetic pose data picked from the
// uploaded file name, and a mocked LLM. No external service is called.
const API_PORT = 8765;
const WEB_PORT = 3123;
const PYTHON = process.env.PYTHON ?? ".venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    ...devices["Pixel 7"],
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn app.asgi:app --port ${API_PORT}`,
      cwd: "../backend",
      env: { ALIBI_TEST_MODE: "1", CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}` },
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // A production build: no on-demand compiling, so timings match what users get.
      command: `npx next build && npx next start -p ${WEB_PORT} -H 127.0.0.1`,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}` },
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
    },
  ],
});
