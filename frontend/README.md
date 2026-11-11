# Alibi frontend

The Next.js, React, and Tailwind CSS web app for Alibi. It provides signup and login, video uploads,
analysis progress and results, upload history and comparisons, account settings, and admin review.

See the [application README](../README.md) for the architecture, backend setup, and deployment.

## Local development

Use Node.js 22 and npm:

```bash
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). The API defaults to `http://localhost:8000`.
To use another API, set `NEXT_PUBLIC_API_URL` in `.env.local` and restart the development server.
The backend must allow the frontend origin through `CORS_ORIGINS`.

## Checks

```bash
npm run lint
npm run test:coverage
npm run e2e
npm run build
```

Playwright starts the API in test mode and a separate Next.js server. It uses `.next-e2e/` so browser
tests can run alongside development. Set `E2E_API_PORT`, `E2E_WEB_PORT`, and `E2E_BUILD_DIR` when you
need different ports or a separate browser-test build.
