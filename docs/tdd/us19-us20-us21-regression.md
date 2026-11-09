# US-19, US-20 and US-21 regression verification

US-21 was committed as `c677813` before this verification run. US-19 is `578b3f3` and US-20 is
`3bd01bf`. The individual TDD records remain in [US-19](us19.md), [US-20](us20.md) and [US-21](us21.md).

## Combined workflow

The added [browser regression](../../frontend/e2e/us19-us20-us21-flow.spec.ts) checks the boundaries
between all three stories in one account:

1. A worker fails once. Retry creates a successful analysis using the saved video, without a second upload.
2. History can compare that retried analysis with a newer, improved upload using saved measurements.
3. Deleting the retried upload removes both the failed and successful attempts, clears its comparison
   selection and makes old result/comparison URLs unavailable. The other upload still works.
4. Account deletion removes the remaining upload, redirects old pages to login on the same origin and
   rejects the deleted credentials.

This is additional regression coverage after implementation, not a new test-first feature claim.
The test is AI-generated and is not marked manual.

The first focused browser run passed the seven existing cases. The new combined case reached the
preserved clean upload but incorrectly expected a "Top fix" heading. The displayed result correctly
said "No major issues found". The assertion was corrected to require that message and the rep
breakdown ([diagnostic log](regression-us19-us20-us21-e2e-diagnostic.txt)); no application code changed.

## Focused verification

| Check | Result | Evidence |
| --- | --- | --- |
| Backend US-19/20/21 and related repository contracts | 66 passed, 5 skipped | [Log](regression-us19-us20-us21-backend.txt) |
| Frontend US-19/20/21 | 48 passed | [Log](regression-us19-us20-us21-frontend.txt) |
| Browser US-19/20/21 including the combined workflow | 8 passed | [Log](regression-us19-us20-us21-e2e.txt) |

The focused checks run before the wider suites. Browser tests use an isolated test-mode API on port
8767 and a fresh production frontend on port 3125, with build files in the ignored
`frontend/node_modules/.cache/us19-us20-us21-e2e/` directory. Existing demo servers and accounts are
preserved. Only accounts created by the tests are deleted. LLM calls and pose analysis use the project's
test services; no external service or real user data is used.

## Wider verification

| Check | Result | Evidence |
| --- | --- | --- |
| Full backend suite | 453 passed, 18 skipped; 93% line coverage | [Log](regression-full-backend.txt) |
| Full frontend suite, four workers | 142 passed; 82.18% line coverage | [Log](regression-full-frontend.txt) |
| All browser tests | 19 passed, 1 skipped | [Log](regression-full-e2e.txt) |
| Production frontend build | Passed | [Log](regression-us19-us20-us21-build.txt) |
| ESLint and TypeScript | Passed | [Log](regression-static-checks.txt) |

The initial parallel frontend run hit the existing five-second limits in two UI tests (140 passed,
2 timed out; [diagnostic](regression-full-frontend-diagnostic.txt)). Assertions and timeouts were kept
unchanged for the subsequent run with fewer workers.
The parallel backend run likewise exceeded the existing 30-second startup health-check deadline
(452 passed, 1 failed, 18 skipped; [diagnostic](regression-full-backend-diagnostic.txt)). The complete
backend suite was rerun on its own. No application code or timeout threshold was changed.
Both reruns passed. This points to resource contention during the parallel run rather than a
reproduced behavior regression. The temporary browser-test servers were stopped afterward, and the
existing US-21 demo API and login page were rechecked successfully.

## Commands

```powershell
# backend
.venv\Scripts\python.exe -m pytest -k 'us19 or us20 or us21' -q -ra
.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term --cov-report=xml -ra

# frontend
npm test -- us19 us20 us21
npm run e2e -- us19 us20 us21
npm run test:coverage -- --maxWorkers=4
npm run e2e
npm run lint -- --ignore-pattern coverage/**
npx tsc --noEmit
```

Browser commands use `E2E_API_PORT=8767`, `E2E_WEB_PORT=3125`,
`E2E_BUILD_DIR=node_modules/.cache/us19-us20-us21-e2e`, `PYTHON` set to the backend virtual
environment's absolute executable path, and the installed Playwright browser cache in
`frontend/node_modules/.cache/ms-playwright`. The production build uses the same build directory
and `NEXT_PUBLIC_API_URL=http://127.0.0.1:8767` ([build log](regression-us19-us20-us21-build.txt)).

## Environment limits

The Postgres checks require `TEST_DATABASE_URL` pointing to a disposable database. Docker is installed,
but its Linux engine was unavailable, and the startup attempt did not provide a running test database.
Those checks remain skipped locally; CI supplies a disposable Postgres service. The team's labeled
real-video fixtures and a deployed frontend URL are also required for their respective checks.
