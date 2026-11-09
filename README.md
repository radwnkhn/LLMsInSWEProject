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

## Deploy

- **Database:** run `supabase/migrations/*.sql` in the Supabase SQL editor (or `supabase db push`).
  In Supabase Auth, turn off "Confirm email" for the Alpha. Make someone an admin by setting their
  `app_metadata` to `{"role": "admin"}`.
- **Backend (Render):** `render.yaml` defines the service. Set the variables from `backend/.env.example`.
- **Frontend (Vercel):** import the repo with `frontend` as the root directory and set
  `NEXT_PUBLIC_API_URL` to the Render URL. `/status` shows whether the frontend can reach the backend.
