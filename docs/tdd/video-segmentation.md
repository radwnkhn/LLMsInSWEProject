# US-04 / US-06 segmentation and trimming TDD

See [investigation, implementation, and release checks](../video-segmentation-investigation.md).

Tests were generated with AI and executed against the old implementation before the corresponding
changes. They are not tagged as human-refined tests.

| Red evidence | Failing acceptance checks before implementation |
| --- | --- |
| `red-rep-segmentation.txt` | 6 failures, 9 passes: wrong movement/count, tracking gaps, low confidence, validator trust |
| `red-video-trimming.txt` | 13 failures: boundary validation, selection, persistence, original frame times |
| `red-video-trimmer-ui.txt` | 4 failures: optional selection, preview, reset, invalid bounds/retry |
| `red-pose-quality.txt` | 3 failures, 20 passes: partial landmarks, nonfinite coordinates, source timing |
| `red-tail-tracking.txt` | 1 failure: tracking loss at the end silently hides the last rep |
| `red-interval-validation.txt` | 2 failures, 4 passes: overlapping times and nonfinite metrics |

Verification already completed locally:

- Full backend run before the final edge-case additions: **807 passed, 42 skipped**.
- Final focused backend checks: **102 passed, 13 PostgreSQL variants skipped**.
- Frontend: **239 passed**, **93.57% line coverage** (`frontend-suite.txt`).
- Browser: **34 passed, 1 deployment-only skip** (`browser-suite.txt`). The new trimming flow passed
  against a production frontend build and the real API in test mode: preview stops at the selected end,
  only complete selected reps are returned, playback seeks use original times, and the full video is retained.
- ESLint and TypeScript passed. A subsequent lint after coverage generation reports one warning from
  generated coverage JavaScript, with no source errors.
- `git diff --check` passed.

The final complete backend coverage result and CI migration/runtime results will be appended after
completion. Local PostgreSQL variants require a disposable database; the installed Docker engine
is stopped. The labeled real-video fixture is also absent. No tests were removed or newly marked
as skipped to make this feature pass.
