# Alibi: project guide for Claude

## What we're building
A mobile-first web app. A lifter uploads a video of a squat, deadlift or bench set and gets:
one top fix, one cue for the next set, an annotated frame showing where the fault happened,
and a rep-by-rep breakdown. Every critique must be backed by measurements from the video.
Target users: beginner and intermediate college lifters who train without a coach (UVA).

## Pipeline
1. **Pose estimation** (MediaPipe Pose): landmarks + confidence per frame.
2. **Measurements** (NumPy, plain code): joint angles, depth, bar path, rep count, camera angle.
3. **LLM** (multimodal, provider configurable): gets measurements + 3–5 key frames, returns
   strict JSON: lift, camera angle, rep count, top fault ID (from a fixed list), fault reps,
   supporting measurement, other faults, cue, explanation.
4. **Validator** (plain code, never an LLM): checks the JSON against the measurements
   (schema, lift, rep count, faults confirmed on cited reps, numbers match, measurability,
   safety faults first, no medical claims, professional referral if the user mentions pain).
5. **Correction loop**: validation errors go back to the LLM, at most 3 attempts in total.
   After 3 failures, show only verified measurements and the rep breakdown. Log every attempt.

## Stack
- Frontend: Next.js, React, Tailwind CSS
- Backend: Python, FastAPI
- Database and storage: Supabase (Postgres + Storage)
- Deploy: Vercel (frontend), Render (backend)

## How we work (required by the course: AI-assisted TDD)
- Every feature maps to a GitHub issue (`[US-xx]` user stories, `[SETUP-xx]` setup).
  Each acceptance criterion is tagged [unit], [integration] or [e2e].
- For each issue: write tests for every acceptance criterion FIRST, run them and confirm they
  fail, then write code until they pass.
- Name tests after the issue so we can count tests per issue, e.g. `test_us08_rejects_wrong_rep_count`.
- Mark tests that a person refined or added by hand with a `# manual` comment (Python) or
  `// manual` (TS), so we can report the AI-generated vs. manual ratio.
- Keep line coverage reported in CI. Mock the LLM in tests; never call the real API in CI.
- Reference the issue in commits and PRs (e.g. "Closes #12").

## Key files
- `issues/issues.py` and `issues/create_issues.py`: source of truth for the GitHub issues
  (run `python3 issues/create_issues.py radwnkhn/LLMsInSWEProject`).
- `docs/User_Stories_and_Acceptance_Criteria.md`: stories and criteria for the written report.
