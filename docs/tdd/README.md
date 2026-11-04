# TDD record for the Alpha milestone (SETUP-01, SETUP-02, US-01 to US-18)

All tests below were AI-generated (Claude Code). None are marked `# manual` / `// manual` yet: the team
still needs to review them, refine them and add edge cases, and mark what they change.

## Red: tests written first, confirmed failing

Tests were written against stub modules whose functions raised `NotImplementedError` (and React
components that rendered nothing), so each test failed on behavior rather than on a missing import.

| Suite | Result against stubs | Log |
| --- | --- | --- |
| Backend (pytest) | 215 failed, 123 errors, 3 passed, 8 skipped | `red-backend.txt` |
| Frontend (Vitest) | 82 failed, 6 passed | `red-frontend.txt` |

What passed or skipped against the stubs, and why:

- Backend passes were trivially true: the Next.js scaffold already existed, the landmark-name list is a
  data constant, and the empty validator stub had no imports (the "validator makes no LLM calls" check).
- Backend skips: 5 Postgres tests (no `TEST_DATABASE_URL`), the labeled-video test (no videos yet),
  and 2 parametrized tests whose parameter lists were still empty stub constants.
- The 6 frontend passes are "absence" checks (for example "no warning label on a technique fault")
  that hold trivially when a component renders nothing. Each has a failing positive test for the same
  criterion.
- The Playwright e2e specs were written in the red phase but weren't run until the app existed.

## Green: code written until the tests passed

| Suite | Result | Line coverage | Log |
| --- | --- | --- | --- |
| Backend (pytest), with Postgres 18 | 373 passed, 1 skipped | 96% | `green-backend.txt` |
| Frontend (Vitest) | 91 passed | 67% (pages are covered by e2e, not unit tests) | `green-frontend.txt` |
| E2E (Playwright, Chromium, phone viewport) | 11 passed, 1 skipped | n/a | `green-e2e.txt` |

The one backend skip is the labeled-video rep-count test (see "Still open"). The e2e skip is the live
deployment check, which runs when `DEPLOYED_FRONTEND_URL` is set.

### Tests changed during the green phase

- `test_us06_squat_angles_at_the_bottom_match_hand_calculation`: the hand calculation was for torso
  lean at the bottom of the squat, but the test compared it with the rep's *maximum* lean (which
  happens mid-descent). It now checks the bottom-frame lean against the hand value.
- `test_us09_correction.py`: a module-level request object was built at import time, which broke
  collection while the code was stubbed. It's now built per test.
- `e2e/us01-auth.spec.ts`: the alert locator is scoped to `<main>`, because Next.js adds its own empty
  `role="alert"` route announcer to every page.

### Bugs the tests caught

- Rep counting missed a shallow rep among deep ones (hysteresis threshold too strict).
- Form labels included hint text, so "Password" and "Video of your set" weren't the accessible names.
- E2E against `next dev` timed out on first-visit compiles; e2e now runs against a production build.

### Bug found in manual testing: uploads over 50 MB failed (US-04)

The first real upload returned a 500: Supabase's free plan stores at most 50 MB per file, but US-04 accepts up
to 200 MB. Fixed test-first in `tests/test_us04_compress.py` (11 tests, all failing against a stub; see
`red-us04-compress.txt`). The server now re-encodes each upload to H.264 MP4 with the longer side at most 1280 px
and the bitrate capped at 4 Mb/s (60 s ≈ 30 MB) before storing it, and a storage failure returns a clear 502
message instead of crashing. A 159 MB test clip was stored as 5.3 MB.

### Bug found in manual testing: a moving camera hid reps (US-06)

A real 3-rep squat was counted as 1 rep. The phone tilted while recording, so the whole body rose about 10% of
the frame height over the set, and the counter used one fixed "standing" height for the whole video. Fixed
test-first (see `red-us06-drift.txt`):

- `height_signal` now measures the hips above the ankles (bench: wrists above shoulders) instead of from the
  frame edge, falling back to the old measure when the feet are out of frame.
- `count_reps` compares each rep with the standing height just before it, which tolerates slow changes in
  distance or zoom too.

Tests changed: `test_us06_height_signal_uses_hips_...` became `test_us06_height_signal_is_hips_above_ankles_...`
(it hard-coded the old measure). The new size-change test was first written with the body shrinking to 60% of
its size; that turned out to be past what a deadlift can tolerate, so it now uses 75%. That's still more than
3× the real clip, but the squat case of that test also passes on the old code. Scaling the signal by shin length
was tried and dropped: it broke front-view squats, where shins look shorter at the bottom.

### Bug found in manual testing: a clear fault reported as "No major issues found" (US-06, US-08, US-10)

A bodyweight squat with the hips rising early (torso lean up 13–23° per rep, threshold 10°) came back as "No
major issues found". Three causes, fixed test-first (see `red-camera-lift.txt`):

- **US-06:** the side view (MediaPipe width ratio about 0.19) was classified as angled, because the side cutoff
  was 0.15, so every side-view check was skipped. The cutoff is now 0.25 (`SIDE_MAX_RATIO`), about 20° of turn.
  The first version of the new test used a turn that only reached a ratio of 0.13, so it passed on the old code;
  it was widened to match the real clip (about 0.20) before the fix.
- **US-08:** with the arms held out front, the wrists sat at hip height and lift detection said deadlift, and
  the validator then forced the feedback to say deadlift. Detection now only overrides the selected lift when it
  disagrees on lying down vs standing (`SetMeasurements.analysis_lift`), so "deadlift for a bench video" is
  still rejected.

### Bug found in manual testing: bar drift reported with no bar (US-13)

The same bodyweight squat was flagged for bar drift. Without a bar the squat's "bar" is the shoulder midpoint,
so the check means nothing. Squats now list bar drift under "Not measured" ("no bar on your back (your hands
aren't at your shoulders)") when the hands are more than half a torso length from the shoulders on most frames
(`hands_at_shoulders`; a bar on the back measures about 0.1–0.3, the two real clips 0.77 and 1.44). Deadlift and
bench are unchanged, since the hands are on the bar there. Fixed test-first (see `red-us13-no-bar.txt`).
- **US-10:** "No major issues found" now says how many checks couldn't be run. The heading text is unchanged.

### Tests added after the code (not test-first)

- `tests/test_setup02_repository.py`: the same contract run against the in-memory store and Postgres.
- The four `video backend` tests at the end of `tests/test_us06_measure.py` (OpenCV + MediaPipe path).

## Tests per issue

Parametrized cases count as separate tests.

| Issue | Backend (pytest) | Frontend (Vitest) | E2E (Playwright) |
|---|---|---|---|
| SETUP-01 | 19 | 0 | 0 |
| SETUP-02 | 39 | 0 | 2 |
| US-01 | 28 | 6 | 2 |
| US-02 | 11 | 5 | 0 |
| US-03 | 0 | 10 | 3 |
| US-04 | 29 | 26 | 0 |
| US-05 | 20 | 1 | 1 |
| US-06 | 54 | 0 | 0 |
| US-07 | 33 | 0 | 0 |
| US-08 | 30 | 0 | 0 |
| US-09 | 12 | 3 | 1 |
| US-10 | 8 | 8 | 0 |
| US-11 | 10 | 3 | 1 |
| US-12 | 9 | 4 | 1 |
| US-13 | 12 | 3 | 0 |
| US-14 | 9 | 3 | 0 |
| US-15 | 31 | 5 | 0 |
| US-16 | 22 | 8 | 0 |
| US-17 | 10 | 3 | 1 |
| US-18 | 14 | 6 | 0 |
| **Total** | **400** | **94** | **12** |

## Still open

- **US-06 labeled videos:** rep counts are checked on synthetic pose data. Add the team's labeled videos
  to `backend/tests/fixtures/labeled_videos/` with a `labels.json` (`[{"file": "...", "lift": "squat",
  "reps": 5}]`) to run the real-video test. It also needs the pose model
  (`backend/scripts/download_pose_model.sh`).
- **SETUP-02 deployment:** nothing is deployed yet. Create the Supabase project, Render service
  (`render.yaml`) and Vercel project, then run `DEPLOYED_FRONTEND_URL=... npx playwright test setup02`.
- **Fault thresholds** (for example 10° of knee valgus, 10° of torso lean increase) are first guesses
  in `backend/app/faults.py`; they should be checked against trainer-graded videos.
