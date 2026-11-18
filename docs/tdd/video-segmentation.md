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
| `red-repeated-descents.txt` | 1 failure: repeated descents were merged when the standing return was unclear |

Verification already completed locally:

- Full backend run before the final edge-case additions: **807 passed, 42 skipped**.
- Final focused backend checks: **102 passed, 13 PostgreSQL variants skipped**.
- Complete backend after the interval/tracking safeguards: **819 passed, 44 skipped**
  (`backend-final-suite.txt`). The earlier complete coverage run reports **92%** (`backend-suite.txt`).
- After the last repeated-descent safeguard: **128 passed, 1 missing labeled-video fixture skipped**
  across segmentation, measurements, analyzability, and validation.
- Frontend: **239 passed**, **93.57% line coverage** (`frontend-suite.txt`).
- Browser: **34 passed, 1 deployment-only skip** (`browser-suite.txt`). The new trimming flow passed
  against a production frontend build and the real API in test mode: preview stops at the selected end,
  only complete selected reps are returned, playback seeks use original times, and the full video is retained.
- ESLint and TypeScript passed. A subsequent lint after coverage generation reports one warning from
  generated coverage JavaScript, with no source errors.
- `git diff --check` passed.

The [draft PR and its CI checks](https://github.com/radwnkhn/LLMsInSWEProject/pull/43) run the complete
tree against disposable PostgreSQL 16, including migration constraints, repository round trips,
and RLS. The backend image job builds Docker and runs actual MediaPipe inference. The local Docker
engine is stopped; the labeled real-video fixture is absent. No tests were removed or newly marked
as skipped to make this feature pass.

Full-flow evidence uses the real web/API applications in test mode, with in-memory storage and a
mocked LLM. It does not claim production Supabase or live-provider validation:

| Boundary | Evidence |
| --- | --- |
| UI → request | User edits original-video bounds; multipart request retains the original file |
| API → saved upload | Bounds validated before storage; persisted with upload and reused on retry |
| Saved upload → analysis | Only selected frames reach pose inference; excluded faults never enter coaching |
| Analysis → response | Selected-only rep count, measurements, analysis range, and quality metadata |
| Response → playback | Browser asserts two selected reps, original-time seek, and retained 12-second video |
