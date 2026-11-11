# Alibi (FormCheck)

Upload a video of a squat, deadlift or bench set and get one top fix, one cue for the next set,
an annotated frame showing where the fault happened, and a rep-by-rep breakdown. Every critique is
checked against measurements from the video before you see it.

| Part | Stack | Folder |
| --- | --- | --- |
| Web app | Next.js, React, Tailwind CSS | `frontend/` |
| API and analysis | Python, FastAPI, MediaPipe, NumPy | `backend/` |
| Database and storage | Supabase (Postgres + Storage) | `supabase/migrations/` |

## Run it

One-time setup (Python 3.13 and Node 22):

```bash
make setup
```

Then each part starts with one command:

```bash
make backend    # API on http://localhost:8000 (needs backend/.env, see backend/.env.example)
make frontend   # web app on http://localhost:3000
```

No Supabase project or LLM key yet? `make backend-test-mode` runs the same API with an in-memory
database, synthetic pose data and a mocked LLM.

For real videos, download the pose model once with `backend/scripts/download_pose_model.sh` and set
`POSE_MODEL_PATH` in `backend/.env`.

## Tests

```bash
make test                         # backend (pytest) + frontend (Vitest), with line coverage
cd frontend && npm run e2e        # Playwright end-to-end tests against the API in test mode
```

- Tests are named after their issue (`test_us08_rejects_wrong_rep_count`, `us02_...`), so tests per
  issue can be counted with `grep`.
- The LLM is always mocked. CI never calls a real provider.
- The Postgres migration and row-level security tests run when `TEST_DATABASE_URL` points at a
  disposable Postgres database (CI provides one).
- Tests refined or added by hand are marked `# manual` (Python) or `// manual` (TypeScript).
- `docs/tdd/` holds the output of the failing (red) run for each suite.

## Processing status (US-19 / #21)

Uploads show Uploading → Measuring → Writing feedback → Checking. The results page polls the API every
1.5 seconds while a job is queued or processing and opens the result automatically when it finishes.
Worker failures offer Retry using the saved video; each retry creates an analysis and keeps the failed
attempt for inspection. Network failures offer Retry to reconnect.

Apply `supabase/migrations/20261109000000_us19_processing_stage.sql` to an existing Alpha database before
running the updated backend. Fresh databases should apply all migrations in order as usual.

The acceptance criteria, red/green evidence and test commands are in `docs/tdd/us19.md`.

## Compare uploads (US-20 / #22)

In **History**, select two completed uploads of the same lift and choose **Compare selected uploads**.
The comparison shows the earlier and newer videos side by side, their rep counts and key measurements,
and whether measurements in the newer set still confirm the earlier top fault. It reports when that
fault cannot be measured instead of implying that it was fixed. Measurements-only results are supported.

Different lifts, another user's uploads, unfinished analyses and two analyses of the same upload cannot
be compared. No new LLM call or database migration is needed. See `docs/tdd/us20.md` for TDD evidence.

Browser tests use `.next-e2e/` for their build so a local development server can keep its own `.next/` files.

## Delete uploads or your account (US-21 / #23)

In **History**, choose **Delete upload** and confirm to remove that video, all of its analysis attempts,
frames, measurements, AI output and ratings. In **Settings**, choose **Delete account** and confirm to
remove your account and all its data. Successful account deletion signs you out and prevents old
sessions from accessing the API. Both confirmation dialogs support Cancel and Escape.

Wait for queued or processing analyses to finish before deleting. Cleanup failures show an error and
allow another attempt. The backend coordinates deletion with uploads/retries, removes files through
the Storage API, and uses the existing database cascades for related records. Account deletion also
cleans orphaned media under that user's private folders. The existing backend-only Supabase service
role key is used for Auth account deletion; no new migration or environment variable is needed.

See `docs/tdd/us21.md` for acceptance coverage and red/green evidence. To run browser tests alongside an
existing demo, set `E2E_API_PORT`, `E2E_WEB_PORT` and `E2E_BUILD_DIR` to unused ports and a separate build
folder (this change was verified with ports 8766/3124 and `.next-us21-e2e`).

## Deploy

- **Database:** run `supabase/migrations/*.sql` in the Supabase SQL editor (or `supabase db push`).
  In Supabase Auth, turn off "Confirm email" for the Alpha. Make someone an admin by setting their
  `app_metadata` to `{"role": "admin"}`.
- **Backend (Render):** `render.yaml` defines the service. Set the variables from `backend/.env.example`.
- **Frontend (Vercel):** import the repo with `frontend` as the root directory and set
  `NEXT_PUBLIC_API_URL` to the Render URL. `/status` shows whether the frontend can reach the backend.
