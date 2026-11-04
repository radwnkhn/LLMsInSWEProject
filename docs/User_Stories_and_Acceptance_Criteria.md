# Core user stories and acceptance criteria

- **18 core user stories** for the Alpha (17 gym goer, 1 admin), plus 2 setup issues
- **96 acceptance criteria** in the Alpha, each tagged with the test type that will cover it: [unit], [integration] or [e2e]
- **10 Beta backlog stories** (roadmap to Beta)

Labels `core: LLM` and `core: differentiator` mark the stories that carry the AI integration and what sets the product apart.

## Summary

| ID | Story | Core |
|---|---|---|
| SETUP-01 | Project setup and CI |  |
| SETUP-02 | Database, storage and deployment |  |
| US-01 | Sign up and log in |  |
| US-02 | Choose the lift before uploading |  |
| US-03 | Filming guidance before recording |  |
| US-04 | Upload a set video from my phone |  |
| US-05 | Tell me when a video can't be analyzed | differentiator |
| US-06 | Measure my reps, angles, depth and bar path |  |
| US-07 | AI diagnoses my form and picks the top fix | LLM |
| US-08 | Every claim is checked before I see it | LLM, differentiator |
| US-09 | Automatic correction and safe fallback | LLM, differentiator |
| US-10 | Show one top fix and one cue |  |
| US-11 | Annotated frame showing where the fault happened | differentiator |
| US-12 | Rep-by-rep breakdown |  |
| US-13 | Say what couldn't be measured | differentiator |
| US-14 | Safety issues always come first | differentiator |
| US-15 | Recommend a professional if I mention pain | differentiator |
| US-16 | Rate the feedback and say if I tried the cue |  |
| US-17 | Upload history |  |
| US-18 | Inspect analyses and validator logs | LLM |

## Alpha issues

---

### [SETUP-01] Project setup and CI

Labels: setup, area: infra

#### Goal
Set up the codebase so every story can be built test-first.

#### Acceptance criteria
- [ ] [integration] Next.js + Tailwind frontend and FastAPI backend each start with one command, documented in the README.
- [ ] [integration] `GET /health` on the backend returns 200 with `{"status": "ok"}`.
- [ ] [integration] CI runs frontend and backend tests plus a line-coverage report on every pull request.
- [ ] [unit] Config loads Supabase and LLM keys from environment variables and fails with a clear error if one is missing.

---

### [SETUP-02] Database, storage and deployment

Labels: setup, area: infra

#### Goal
Create the data model and deploy the Alpha so test users can reach it.

#### Acceptance criteria
- [ ] [integration] A checked-in migration creates tables for users, uploads, analyses, rep measurements, LLM attempts, validation results and feedback responses.
- [ ] [integration] Row-level security: a user can read only their own uploads and analyses; an admin can read all.
- [ ] [integration] Videos and annotated frames are saved to a private Supabase Storage bucket.
- [ ] [e2e] The frontend (Vercel) and backend (Render) are deployed, and the deployed frontend reaches the backend `/health` endpoint.

---

### [US-01] Sign up and log in

Labels: user story, role: gym goer, area: accounts

#### User story
As a **gym goer**, I want to sign up and log in with my email, so that my uploads and feedback are saved to my account.

#### Acceptance criteria
- [ ] [integration] Signing up with a valid email and a password of 8+ characters creates an account and logs me in.
- [ ] [integration] Logging in with the wrong password shows "Incorrect email or password" and does not log me in.
- [ ] [integration] Requests to upload or view results without being logged in return 401.
- [ ] [integration] Every upload and analysis is saved with my user ID.
- [ ] [e2e] After logging out, visiting my history page redirects to the login page.

---

### [US-02] Choose the lift before uploading

Labels: user story, role: gym goer, area: upload

#### User story
As a **gym goer**, I want to choose whether I'm doing a squat, deadlift or bench press, so that the feedback is specific to my lift.

#### Acceptance criteria
- [ ] [unit] The lift picker offers exactly three options: Squat, Deadlift, Bench Press.
- [ ] [unit] The upload button stays disabled until a lift is selected.
- [ ] [integration] The selected lift is saved with the upload and passed to the analysis.
- [ ] [integration] A request with any other lift value is rejected with a 422 error.

---

### [US-03] Filming guidance before recording

Labels: user story, role: gym goer, area: upload

#### User story
As a **gym goer**, I want short filming instructions for my lift before I record, so that my video can be measured accurately.

#### Acceptance criteria
- [ ] [unit] After choosing a lift, the filming guide shows that lift's tips: side view, phone at hip height, whole body and bar in frame.
- [ ] [unit] The guide shows an example image of correct framing.
- [ ] [unit] The guide can be dismissed and reopened from the upload screen.
- [ ] [e2e] The guide fits on a 375px-wide screen without scrolling sideways.

---

### [US-04] Upload a set video from my phone

Labels: user story, role: gym goer, area: upload

#### User story
As a **gym goer**, I want to record or pick a video of my set and upload it from my phone, so that I can get feedback between sets.

#### Acceptance criteria
- [ ] [unit] MP4 and MOV files are accepted; other file types are rejected with "Please upload an MP4 or MOV video" before uploading.
- [ ] [unit] Videos longer than 60 seconds or larger than 200 MB are rejected with a message stating the limit.
- [ ] [unit] Upload progress is shown as a percentage.
- [ ] [integration] A successful upload stores the video privately and creates an analysis job.
- [ ] [integration] If the upload fails, an error with a Retry button is shown, and retrying doesn't require choosing the file again.

---

### [US-05] Tell me when a video can't be analyzed

Labels: user story, role: gym goer, area: analysis, core: differentiator

#### User story
As a **gym goer**, I want to be told when my video can't be analyzed, and why, so that I can refilm instead of getting bad feedback.

#### Acceptance criteria
- [ ] [unit] If no person is detected, the result is "Couldn't analyze: no person found".
- [ ] [unit] If key joints (hips, knees, ankles, shoulders) have pose confidence below 0.5 on more than half the frames, the result is "Couldn't analyze: body not clearly visible".
- [ ] [unit] If no complete rep is detected, the result is "Couldn't analyze: no reps found".
- [ ] [integration] For an unanalyzable video, the LLM is never called.
- [ ] [e2e] The message shows a Refilm button that opens the filming guide.

---

### [US-06] Measure my reps, angles, depth and bar path

Labels: user story, role: gym goer, area: analysis

#### User story
As a **gym goer**, I want the app to measure my reps, joint angles, depth and bar path from my video, so that every piece of feedback is based on real numbers from my set.

#### Acceptance criteria
- [ ] [unit] Pose estimation (MediaPipe) returns x, y and confidence for each body landmark on every frame.
- [ ] [unit] Joint angles (knee, hip, torso lean) are computed in degrees from three landmarks, within ±1° of a hand-calculated value on test data.
- [ ] [unit] Rep counting splits the set into reps from the hip (squat, deadlift) or wrist (bench) height signal; the count matches the true count on the team's labeled test videos.
- [ ] [unit] Squat depth is marked reached when the hip is below the knee at the bottom of a rep.
- [ ] [unit] Bar path uses the wrist midpoint (bench, deadlift) or shoulder midpoint (squat), with forward/back drift divided by thigh length.
- [ ] [unit] Camera angle is classified as side, front or angled from landmark positions.
- [ ] [integration] Measurements are saved per rep and linked to the analysis.

---

### [US-07] AI diagnoses my form and picks the top fix

Labels: user story, role: gym goer, area: ai, core: LLM

#### User story
As a **gym goer**, I want an AI coach to read my measurements and key video frames, find the underlying fault and pick what I should fix first, so that I get the advice a coach would give, not just a list of numbers.

#### Acceptance criteria
- [ ] [integration] The LLM request includes the selected lift, per-rep measurements, the faults the rules confirmed, checks that couldn't be measured, 3–5 key frames and my optional note.
- [ ] [unit] The LLM must reply in a strict JSON schema: lift, camera angle, rep count, top fault ID, reps where it happened, supporting measurement, other faults, cue and a short explanation.
- [ ] [unit] Fault IDs must come from the fixed fault list for that lift.
- [ ] [unit] Replies that aren't valid JSON are treated as a failed attempt, not a crash.
- [ ] [unit] The LLM provider (Claude, Gemini or GPT) can be switched in config without code changes.
- [ ] [integration] With a mocked LLM, a squat video with hips rising early produces `top_fault = hips_rise_early`.

---

### [US-08] Every claim is checked before I see it

Labels: user story, role: gym goer, area: ai, core: LLM, core: differentiator

#### User story
As a **gym goer**, I want every piece of AI feedback checked against my measurements before it reaches me, so that I never see a wrong rep count or a fault that didn't happen.

#### Acceptance criteria
- [ ] [unit] The validator rejects output that doesn't match the JSON schema.
- [ ] [unit] It rejects a lift that doesn't match the detected movement (e.g. "deadlift" for a bench video).
- [ ] [unit] It rejects a rep count that differs from the measured count, with the error "feedback says N reps but M were detected".
- [ ] [unit] It rejects any fault not confirmed by the measurements on the reps it cites, e.g. "knee cave cited on rep 2, but measured valgus is 4° (threshold 10°)".
- [ ] [unit] It rejects any number (angle, depth, rep) that doesn't match the measured value.
- [ ] [unit] It rejects faults that aren't measurable from the camera angle or pose confidence.
- [ ] [unit] Valid output passes with no errors.
- [ ] [unit] The validator is plain code with no LLM calls.

---

### [US-09] Automatic correction and safe fallback

Labels: user story, role: gym goer, area: ai, core: LLM, core: differentiator

#### User story
As a **gym goer**, I want the app to fix the AI's mistakes automatically, and to show only verified numbers if it can't, so that I always get correct feedback without re-uploading.

#### Acceptance criteria
- [ ] [unit] When validation fails, the exact error messages are sent back to the LLM in the retry request.
- [ ] [unit] The corrected reply is validated again, for at most 3 attempts in total.
- [ ] [unit] If an attempt passes, its feedback is used and no further attempts are made.
- [ ] [unit] After 3 failed attempts, the result contains only the verified measurements and rep breakdown, with no AI text.
- [ ] [integration] Every attempt is logged with attempt number, LLM output, validation errors and token count.
- [ ] [e2e] A fallback result shows the note "Coaching feedback isn't available for this video. Here are your measurements."

---

### [US-10] Show one top fix and one cue

Labels: user story, role: gym goer, area: results

#### User story
As a **gym goer**, I want to see the single most important thing to fix and one cue to try on my next set, so that I know exactly what to change without being overwhelmed.

#### Acceptance criteria
- [ ] [unit] The results screen shows exactly one Top Fix, in plain language (e.g. "Hips rise before your shoulders").
- [ ] [unit] Exactly one cue is shown with the top fix, 12 words or fewer.
- [ ] [unit] Other validated faults appear only under a collapsed "See more" section.
- [ ] [unit] If no faults pass validation, the screen says "No major issues found".
- [ ] [integration] The top fix and cue shown are exactly the ones in the validated output.

---

### [US-11] Annotated frame showing where the fault happened

Labels: user story, role: gym goer, area: results, core: differentiator

#### User story
As a **gym goer**, I want to see the exact rep and frame where the problem happened, with the measurement drawn on it, so that I can see the mistake for myself and trust the feedback.

#### Acceptance criteria
- [ ] [unit] The frame is taken from the cited rep at the moment the measurement is at its worst.
- [ ] [unit] The tracked skeleton and the measurement label (e.g. "Torso +14°") are drawn on the frame.
- [ ] [unit] The rep number, timestamp and measurement on the frame equal the stored values.
- [ ] [e2e] Tapping the frame plays the video from the start of that rep.

---

### [US-12] Rep-by-rep breakdown

Labels: user story, role: gym goer, area: results

#### User story
As a **gym goer**, I want a rep-by-rep breakdown of my set, so that I can see whether my form slipped as I got tired.

#### Acceptance criteria
- [ ] [unit] One row is shown per measured rep, in order, and the row count equals the measured rep count.
- [ ] [unit] Each row shows "Clean" or the validated fault(s) on that rep.
- [ ] [unit] If faults appear only in the last third of the reps, a note says form broke down late in the set, likely from fatigue.
- [ ] [e2e] Tapping a rep row jumps the video to that rep.

---

### [US-13] Say what couldn't be measured

Labels: user story, role: gym goer, area: results, core: differentiator

#### User story
As a **gym goer**, I want the app to tell me what it couldn't measure from my camera angle, so that I know it isn't guessing.

#### Acceptance criteria
- [ ] [unit] Checks that need a front view (e.g. knee cave) are listed under "Not measured" when the camera angle is side.
- [ ] [unit] Checks whose joints have pose confidence below 0.5 are listed as not measured, with the reason.
- [ ] [unit] A not-measured check never appears as a fault.
- [ ] [unit] The "Not measured" section is hidden when everything could be measured.

---

### [US-14] Safety issues always come first

Labels: user story, role: gym goer, area: results, core: differentiator

#### User story
As a **gym goer**, I want safety-related faults always shown first, so that I fix anything that could hurt me before anything else.

#### Acceptance criteria
- [ ] [unit] Every fault in the fault list is tagged safety or technique.
- [ ] [unit] When a safety fault and a technique fault are both confirmed, the validator rejects output that doesn't make the safety fault the top fix.
- [ ] [unit] Safety faults show a warning label on the results screen.

---

### [US-15] Recommend a professional if I mention pain

Labels: user story, role: gym goer, area: safety, core: differentiator

#### User story
As a **gym goer**, I want to be told to see a professional if I mention pain, so that I don't rely on an app for a medical problem.

#### Acceptance criteria
- [ ] [unit] The upload form has an optional note field of up to 300 characters.
- [ ] [unit] If the note mentions pain or injury (e.g. "hurts", "pain", "injured"), the results show a message recommending a doctor or physical therapist.
- [ ] [unit] The validator rejects feedback containing diagnosis or injury-prediction language (e.g. "you have", "you will injure", "herniated", "torn").
- [ ] [unit] When the note mentions pain, the validator rejects output missing the professional recommendation.

---

### [US-16] Rate the feedback and say if I tried the cue

Labels: user story, role: gym goer, area: feedback

#### User story
As a **gym goer**, I want to rate how helpful the feedback was and say whether I tried the cue, so that the team can tell whether the app is actually helping.

#### Acceptance criteria
- [ ] [unit] Every results screen asks for a 1–5 helpfulness rating and "Did you try the cue?" (Yes / No / Not yet).
- [ ] [integration] Answers are saved with the analysis and my user ID; resubmitting replaces my previous answer.
- [ ] [integration] Ratings outside 1–5 are rejected with a 422 error.
- [ ] [unit] When I open a new result for the same lift, I'm asked about the previous cue if I haven't answered.

---

### [US-17] Upload history

Labels: user story, role: gym goer, area: history

#### User story
As a **gym goer**, I want to see my past uploads and their feedback, so that I can track whether my form is improving.

#### Acceptance criteria
- [ ] [integration] History lists only my uploads, newest first, with date, lift, rep count and top fix.
- [ ] [integration] Another user's analysis can't be opened by changing its ID in the URL (returns 404).
- [ ] [unit] History can be filtered by lift.
- [ ] [unit] Unanalyzable and fallback results appear in history with their status.
- [ ] [e2e] Tapping an entry opens its full results.

---

### [US-18] Inspect analyses and validator logs

Labels: user story, role: admin, area: admin, core: LLM

#### User story
As an **admin**, I want to see every analysis with its measurements, each AI attempt and each validator error, so that I can find patterns in the AI's mistakes and investigate bad feedback.

#### Acceptance criteria
- [ ] [integration] The admin page lists analyses newest first, showing lift, number of attempts and final status (passed first try, passed after retry, fallback, couldn't analyze).
- [ ] [unit] The list can be filtered by lift and final status.
- [ ] [integration] An analysis detail page shows the video, per-rep measurements, every LLM attempt, every validator error and the final result the user saw.
- [ ] [unit] A summary shows how often each validator error type occurred.
- [ ] [integration] Non-admin users get 403 on all admin pages and endpoints.

---

## Beta backlog

- **US-19 Show processing status while I wait:** As a gym goer, I want to see each analysis step while my video is processed, so that I know the app is working.
- **US-20 Compare a new upload with an older one:** As a gym goer, I want to compare a new upload with an older one of the same lift, so that I can see if I fixed the problem.
- **US-21 Delete my videos and account:** As a gym goer, I want to delete my videos or my whole account, so that I stay in control of my data.
- **US-22 Blind trainer grading:** As an admin, I want to send a sample of analyzed videos to trainers who grade them before seeing our feedback, so that we can measure accuracy without bias.
- **US-23 Hypothesis metrics dashboard:** As an admin, I want a dashboard showing accuracy, helpfulness, cue adoption and 7-day return rate against their targets, so that we can tell if our hypothesis is holding up.
- **US-24 Adjust fault thresholds:** As an admin, I want to change fault thresholds (such as degrees of knee cave) without changing code, so that we can tune accuracy based on trainer feedback.
- **US-25 Manage the fault list:** As an admin, I want to add, edit or disable faults the AI can report, so that feedback stays within what we can measure as we add checks.
- **US-26 Track AI usage and cost:** As an admin, I want to see LLM token usage and cost per analysis, so that we know what the app costs to run.
- **US-27 Usage and moderation:** As an admin, I want to see sign-ups and uploads over time and remove inappropriate uploads, so that the app stays healthy and on-topic.
- **US-28 More lifts:** As a gym goer, I want feedback on more lifts, such as overhead press and Romanian deadlift, so that I can use the app for more of my workout.
