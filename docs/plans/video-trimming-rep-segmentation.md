# Alibi — Improve Video Segmentation and Rep-Counting Accuracy

You are working in the Alibi repository: `radwnkhn/LLMsInSWEProject`.

## Objective

Improve Alibi's workout video analysis reliability by implementing two complementary features:

1. **Optional manual video trimming:** Allow users to select which portion of their uploaded video should be analyzed.
2. **Improved automatic rep segmentation:** Accurately identify complete exercise repetitions while excluding unrelated movements.

These improvements should resolve the rep-counting vulnerability identified during our Red Team review without unnecessarily changing the existing AI architecture.

## Background

Our Red Team tested a video containing two squats and one forward bend. Alibi detected only one repetition and used that incorrect interval to generate form feedback.

The existing implementation uses MediaPipe landmarks and deterministic rep-counting logic.

A comparison between the Alpha milestone (`5e15c33`) and the audited version (`2346c2c`) suggests that the original squat-counting logic remained unchanged. Therefore, do not assume this was caused by a merge.

Relevant files include:

- `backend/app/measure.py`
- `backend/app/video.py`
- `backend/app/pose.py`
- `backend/app/pipeline.py`

Inspect the current repository structure before making changes.

---

## Feature 1: Optional Manual Video Trimming

Add a video-trimming interface to the existing upload flow.

### Requirements

- Display a preview of the uploaded video.
- Include an interactive timeline with adjustable start and end points.
- Let users trim unwanted footage before analysis.
- Show the selected segment's duration.
- Allow users to preview their selection.
- Provide a reset option to analyze the entire video.
- Make trimming optional.
- Do not automatically remove the first or last three seconds.
- Preserve the original video unless the existing storage architecture requires otherwise.

Ensure the selected interval is respected throughout processing, including rep counting, form analysis, annotated frames, and timestamps.

Prefer non-destructive trimming using start/end timestamps rather than re-encoding the video unnecessarily.

Validate trim boundaries on the backend and reject invalid or empty intervals.

If the full video is retained, ensure feedback timestamps can be mapped correctly to the original video.

### Recording Experience

If Alibi currently supports in-app recording, add an optional three-second countdown before recording begins.

Do not add an entirely new recording system solely for this feature.

---

## Feature 2: Improve Automatic Rep Segmentation

Investigate and improve the existing `count_reps()` algorithm.

### Current Problem

The squat algorithm relies heavily on vertical hip movement. Walking, forward bending, camera movement, or incomplete repetitions can distort the movement signal.

This can cause Alibi to merge multiple repetitions or misclassify unrelated movements.

### Requirements

Implement exercise-specific segmentation using existing MediaPipe landmarks.

For squats, consider:

- Hip vertical displacement
- Knee flexion and extension
- Hip joint angles
- Standing, descending, bottom, and ascending phases
- Temporal consistency and landmark confidence

Use a deterministic movement state machine or another justified approach.

A valid squat should follow a plausible movement sequence:

Standing → Descending → Bottom → Ascending → Standing

Do not count unrelated forward bends, walking, or incomplete repetitions as valid squats.

Avoid relying on a single global movement amplitude across the entire video if unrelated movements can distort that amplitude.

Use adaptive thresholds where appropriate, but avoid hard-coded assumptions that only work for one person's movement pattern.

Maintain the current support for deadlift, bench press, overhead press, and Romanian deadlift. Do not apply squat-specific rules indiscriminately to other lifts.

If existing exercise logic can be reused safely, prefer that over unnecessary rewrites.

---

## Feature 3: Improve Feedback Reliability

Rep-counting errors should not propagate into confident but inaccurate form feedback.

Implement safeguards that:

- Detect unreliable or ambiguous rep segmentation.
- Avoid analyzing movements that cannot confidently be identified as the selected exercise.
- Ensure form measurements and annotated frames correspond to the correct repetition intervals.
- Reject inconsistent exercise measurements and feedback.
- Return a clear user-facing message when the video cannot be analyzed reliably.

Do not allow the validator to treat measurements as unquestionably correct merely because they came from the deterministic measurement pipeline.

Where independent verification is not possible, explicitly represent uncertainty rather than claiming feedback has been fully verified.

---

## Feature 4: Test-Driven Development

Follow the project's existing test-first development methodology.

**Write failing regression tests before implementing the fixes.**

Cover the following scenarios:

1. Two valid squats and one forward bend → exactly two repetitions.
2. Walking before the workout → walking excluded.
3. Walking after the workout → walking excluded.
4. Five consecutive squats → exactly five repetitions.
5. Squats separated by standing pauses → correctly segmented.
6. Incomplete repetitions → not counted as complete.
7. Changing camera position → appropriately handled or rejected.
8. Missing or low-confidence landmarks → no fabricated measurements.
9. A manually trimmed video → only selected frames analyzed.
10. An untrimmed video → existing workflow preserved.
11. All other supported exercises → existing regression tests remain passing.

Use realistic synthetic pose sequences for deterministic unit tests.

Also use labeled real workout videos where available. Do not claim real-world accuracy has been established through synthetic tests alone.

If the original Red Team video is unavailable, document that limitation.

---

## Implementation Constraints

- Preserve the current architecture and existing functionality.
- Do not fine-tune or replace the LLM.
- Use MediaPipe and existing deterministic measurement utilities.
- Follow existing frontend components and styling conventions.
- Avoid unnecessary dependencies.
- Keep the changes modular and maintainable.
- Do not weaken existing validator checks.
- Do not modify unrelated features.
- Do not delete or skip failing tests to obtain a passing result.

Prioritize reliability over making every video analyzable.

---

## Acceptance Criteria

The implementation is complete when:

- Users can optionally trim videos before analysis.
- Trimming is accurately applied to backend processing.
- The rep counter distinguishes valid squats from unrelated movements in regression tests.
- Multiple repetitions are not incorrectly merged.
- Unreliable measurements do not generate confident form recommendations.
- Existing exercises remain functional.
- All relevant backend and frontend tests pass.

## Final Deliverables

Provide:

1. Root-cause analysis of the Red Team finding.
2. Explanation of the segmentation algorithm changes.
3. Description of the new trimming interface.
4. Files modified.
5. Test results and actual repetition counts.
6. Known limitations and remaining risks.
7. Any additional validation needed before release.

Implement the changes on a new branch.

Do not merge directly into `main`.

**Goal:** Make Alibi reliably distinguish actual exercise repetitions from unrelated video movements while giving users a simple way to control which portion of their workout gets analyzed.