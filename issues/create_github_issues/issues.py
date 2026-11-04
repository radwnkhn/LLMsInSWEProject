"""GitHub issues: core Alpha user stories (with testable acceptance criteria) and the Beta backlog.

Each acceptance criterion is tagged with the test type expected to cover it:
[unit], [integration] or [e2e]. One criterion -> at least one automated test.
"""

ALPHA, BETA = "Alpha", "Beta"

DOD = [
    "## Definition of done",
    "- [ ] Tests for every acceptance criterion written first and confirmed failing",
    "- [ ] Code written until all tests pass",
    "- [ ] AI-generated tests reviewed and edge cases added by a team member",
    "- [ ] CI is green",
]

ISSUES = []

def story(role, title, want, benefit, criteria, area, milestone=ALPHA, notes=None, extra_labels=()):
    n = len([i for i in ISSUES if i["kind"] == "story"]) + 1
    key = f"US-{n:02d}"
    article = "an" if role == "admin" else "a"
    body = [
        "## User story",
        f"As {article} **{role}**, I want {want}, so that {benefit}.",
        "",
        "## Acceptance criteria",
        *[f"- [ ] {c}" for c in criteria],
    ]
    if notes:
        body += ["", "## Notes", notes]
    if milestone == ALPHA:
        body += [""] + DOD
    ISSUES.append({
        "kind": "story", "key": key,
        "title": f"[{key}] {title}",
        "labels": ["user story", f"role: {role}", f"area: {area}", *extra_labels],
        "milestone": milestone,
        "body": "\n".join(body),
    })

def chore(title, goal, criteria, area):
    n = len([i for i in ISSUES if i["kind"] == "chore"]) + 1
    key = f"SETUP-{n:02d}"
    body = ["## Goal", goal, "", "## Acceptance criteria", *[f"- [ ] {c}" for c in criteria], ""] + DOD
    ISSUES.append({
        "kind": "chore", "key": key,
        "title": f"[{key}] {title}",
        "labels": ["setup", f"area: {area}"],
        "milestone": ALPHA,
        "body": "\n".join(body),
    })

AI = ("core: LLM",)
DIFF = ("core: differentiator",)

# ======================= ALPHA: setup =======================
chore("Project setup and CI",
    "Set up the codebase so every story can be built test-first.",
    ["[integration] Next.js + Tailwind frontend and FastAPI backend each start with one command, documented in the README.",
     "[integration] `GET /health` on the backend returns 200 with `{\"status\": \"ok\"}`.",
     "[integration] CI runs frontend and backend tests plus a line-coverage report on every pull request.",
     "[unit] Config loads Supabase and LLM keys from environment variables and fails with a clear error if one is missing."],
    "infra")
chore("Database, storage and deployment",
    "Create the data model and deploy the Alpha so test users can reach it.",
    ["[integration] A checked-in migration creates tables for users, uploads, analyses, rep measurements, LLM attempts, validation results and feedback responses.",
     "[integration] Row-level security: a user can read only their own uploads and analyses; an admin can read all.",
     "[integration] Videos and annotated frames are saved to a private Supabase Storage bucket.",
     "[e2e] The frontend (Vercel) and backend (Render) are deployed, and the deployed frontend reaches the backend `/health` endpoint."],
    "infra")

# ======================= ALPHA: gym goer — getting started =======================
story("gym goer", "Sign up and log in",
    "to sign up and log in with my email",
    "my uploads and feedback are saved to my account",
    ["[integration] Signing up with a valid email and a password of 8+ characters creates an account and logs me in.",
     "[integration] Logging in with the wrong password shows \"Incorrect email or password\" and does not log me in.",
     "[integration] Requests to upload or view results without being logged in return 401.",
     "[integration] Every upload and analysis is saved with my user ID.",
     "[e2e] After logging out, visiting my history page redirects to the login page."],
    "accounts")
story("gym goer", "Choose the lift before uploading",
    "to choose whether I'm doing a squat, deadlift or bench press",
    "the feedback is specific to my lift",
    ["[unit] The lift picker offers exactly three options: Squat, Deadlift, Bench Press.",
     "[unit] The upload button stays disabled until a lift is selected.",
     "[integration] The selected lift is saved with the upload and passed to the analysis.",
     "[integration] A request with any other lift value is rejected with a 422 error."],
    "upload")
story("gym goer", "Filming guidance before recording",
    "short filming instructions for my lift before I record",
    "my video can be measured accurately",
    ["[unit] After choosing a lift, the filming guide shows that lift's tips: side view, phone at hip height, whole body and bar in frame.",
     "[unit] The guide shows an example image of correct framing.",
     "[unit] The guide can be dismissed and reopened from the upload screen.",
     "[e2e] The guide fits on a 375px-wide screen without scrolling sideways."],
    "upload")
story("gym goer", "Upload a set video from my phone",
    "to record or pick a video of my set and upload it from my phone",
    "I can get feedback between sets",
    ["[unit] MP4 and MOV files are accepted; other file types are rejected with \"Please upload an MP4 or MOV video\" before uploading.",
     "[unit] Videos longer than 60 seconds or larger than 200 MB are rejected with a message stating the limit.",
     "[unit] Upload progress is shown as a percentage.",
     "[integration] A successful upload stores the video privately and creates an analysis job.",
     "[integration] If the upload fails, an error with a Retry button is shown, and retrying doesn't require choosing the file again."],
    "upload")
story("gym goer", "Tell me when a video can't be analyzed",
    "to be told when my video can't be analyzed, and why",
    "I can refilm instead of getting bad feedback",
    ["[unit] If no person is detected, the result is \"Couldn't analyze: no person found\".",
     "[unit] If key joints (hips, knees, ankles, shoulders) have pose confidence below 0.5 on more than half the frames, the result is \"Couldn't analyze: body not clearly visible\".",
     "[unit] If no complete rep is detected, the result is \"Couldn't analyze: no reps found\".",
     "[integration] For an unanalyzable video, the LLM is never called.",
     "[e2e] The message shows a Refilm button that opens the filming guide."],
    "analysis", extra_labels=DIFF)

# ======================= ALPHA: gym goer — analysis & AI core =======================
story("gym goer", "Measure my reps, angles, depth and bar path",
    "the app to measure my reps, joint angles, depth and bar path from my video",
    "every piece of feedback is based on real numbers from my set",
    ["[unit] Pose estimation (MediaPipe) returns x, y and confidence for each body landmark on every frame.",
     "[unit] Joint angles (knee, hip, torso lean) are computed in degrees from three landmarks, within ±1° of a hand-calculated value on test data.",
     "[unit] Rep counting splits the set into reps from the hip (squat, deadlift) or wrist (bench) height signal; the count matches the true count on the team's labeled test videos.",
     "[unit] Squat depth is marked reached when the hip is below the knee at the bottom of a rep.",
     "[unit] Bar path uses the wrist midpoint (bench, deadlift) or shoulder midpoint (squat), with forward/back drift divided by thigh length.",
     "[unit] Camera angle is classified as side, front or angled from landmark positions.",
     "[integration] Measurements are saved per rep and linked to the analysis."],
    "analysis")
story("gym goer", "AI diagnoses my form and picks the top fix",
    "an AI coach to read my measurements and key video frames, find the underlying fault and pick what I should fix first",
    "I get the advice a coach would give, not just a list of numbers",
    ["[integration] The LLM request includes the selected lift, per-rep measurements, the faults the rules confirmed, checks that couldn't be measured, 3–5 key frames and my optional note.",
     "[unit] The LLM must reply in a strict JSON schema: lift, camera angle, rep count, top fault ID, reps where it happened, supporting measurement, other faults, cue and a short explanation.",
     "[unit] Fault IDs must come from the fixed fault list for that lift.",
     "[unit] Replies that aren't valid JSON are treated as a failed attempt, not a crash.",
     "[unit] The LLM provider (Claude, Gemini or GPT) can be switched in config without code changes.",
     "[integration] With a mocked LLM, a squat video with hips rising early produces `top_fault = hips_rise_early`."],
    "ai", extra_labels=AI)
story("gym goer", "Every claim is checked before I see it",
    "every piece of AI feedback checked against my measurements before it reaches me",
    "I never see a wrong rep count or a fault that didn't happen",
    ["[unit] The validator rejects output that doesn't match the JSON schema.",
     "[unit] It rejects a lift that doesn't match the detected movement (e.g. \"deadlift\" for a bench video).",
     "[unit] It rejects a rep count that differs from the measured count, with the error \"feedback says N reps but M were detected\".",
     "[unit] It rejects any fault not confirmed by the measurements on the reps it cites, e.g. \"knee cave cited on rep 2, but measured valgus is 4° (threshold 10°)\".",
     "[unit] It rejects any number (angle, depth, rep) that doesn't match the measured value.",
     "[unit] It rejects faults that aren't measurable from the camera angle or pose confidence.",
     "[unit] Valid output passes with no errors.",
     "[unit] The validator is plain code with no LLM calls."],
    "ai", extra_labels=AI + DIFF)
story("gym goer", "Automatic correction and safe fallback",
    "the app to fix the AI's mistakes automatically, and to show only verified numbers if it can't",
    "I always get correct feedback without re-uploading",
    ["[unit] When validation fails, the exact error messages are sent back to the LLM in the retry request.",
     "[unit] The corrected reply is validated again, for at most 3 attempts in total.",
     "[unit] If an attempt passes, its feedback is used and no further attempts are made.",
     "[unit] After 3 failed attempts, the result contains only the verified measurements and rep breakdown, with no AI text.",
     "[integration] Every attempt is logged with attempt number, LLM output, validation errors and token count.",
     "[e2e] A fallback result shows the note \"Coaching feedback isn't available for this video. Here are your measurements.\""],
    "ai", extra_labels=AI + DIFF)

# ======================= ALPHA: gym goer — results =======================
story("gym goer", "Show one top fix and one cue",
    "to see the single most important thing to fix and one cue to try on my next set",
    "I know exactly what to change without being overwhelmed",
    ["[unit] The results screen shows exactly one Top Fix, in plain language (e.g. \"Hips rise before your shoulders\").",
     "[unit] Exactly one cue is shown with the top fix, 12 words or fewer.",
     "[unit] Other validated faults appear only under a collapsed \"See more\" section.",
     "[unit] If no faults pass validation, the screen says \"No major issues found\".",
     "[integration] The top fix and cue shown are exactly the ones in the validated output."],
    "results")
story("gym goer", "Annotated frame showing where the fault happened",
    "to see the exact rep and frame where the problem happened, with the measurement drawn on it",
    "I can see the mistake for myself and trust the feedback",
    ["[unit] The frame is taken from the cited rep at the moment the measurement is at its worst.",
     "[unit] The tracked skeleton and the measurement label (e.g. \"Torso +14°\") are drawn on the frame.",
     "[unit] The rep number, timestamp and measurement on the frame equal the stored values.",
     "[e2e] Tapping the frame plays the video from the start of that rep."],
    "results", extra_labels=DIFF)
story("gym goer", "Rep-by-rep breakdown",
    "a rep-by-rep breakdown of my set",
    "I can see whether my form slipped as I got tired",
    ["[unit] One row is shown per measured rep, in order, and the row count equals the measured rep count.",
     "[unit] Each row shows \"Clean\" or the validated fault(s) on that rep.",
     "[unit] If faults appear only in the last third of the reps, a note says form broke down late in the set, likely from fatigue.",
     "[e2e] Tapping a rep row jumps the video to that rep."],
    "results")
story("gym goer", "Say what couldn't be measured",
    "the app to tell me what it couldn't measure from my camera angle",
    "I know it isn't guessing",
    ["[unit] Checks that need a front view (e.g. knee cave) are listed under \"Not measured\" when the camera angle is side.",
     "[unit] Checks whose joints have pose confidence below 0.5 are listed as not measured, with the reason.",
     "[unit] A not-measured check never appears as a fault.",
     "[unit] The \"Not measured\" section is hidden when everything could be measured."],
    "results", extra_labels=DIFF)
story("gym goer", "Safety issues always come first",
    "safety-related faults always shown first",
    "I fix anything that could hurt me before anything else",
    ["[unit] Every fault in the fault list is tagged safety or technique.",
     "[unit] When a safety fault and a technique fault are both confirmed, the validator rejects output that doesn't make the safety fault the top fix.",
     "[unit] Safety faults show a warning label on the results screen."],
    "results", extra_labels=DIFF)
story("gym goer", "Recommend a professional if I mention pain",
    "to be told to see a professional if I mention pain",
    "I don't rely on an app for a medical problem",
    ["[unit] The upload form has an optional note field of up to 300 characters.",
     "[unit] If the note mentions pain or injury (e.g. \"hurts\", \"pain\", \"injured\"), the results show a message recommending a doctor or physical therapist.",
     "[unit] The validator rejects feedback containing diagnosis or injury-prediction language (e.g. \"you have\", \"you will injure\", \"herniated\", \"torn\").",
     "[unit] When the note mentions pain, the validator rejects output missing the professional recommendation."],
    "safety", extra_labels=DIFF)

# ======================= ALPHA: gym goer — feedback & history =======================
story("gym goer", "Rate the feedback and say if I tried the cue",
    "to rate how helpful the feedback was and say whether I tried the cue",
    "the team can tell whether the app is actually helping",
    ["[unit] Every results screen asks for a 1–5 helpfulness rating and \"Did you try the cue?\" (Yes / No / Not yet).",
     "[integration] Answers are saved with the analysis and my user ID; resubmitting replaces my previous answer.",
     "[integration] Ratings outside 1–5 are rejected with a 422 error.",
     "[unit] When I open a new result for the same lift, I'm asked about the previous cue if I haven't answered."],
    "feedback")
story("gym goer", "Upload history",
    "to see my past uploads and their feedback",
    "I can track whether my form is improving",
    ["[integration] History lists only my uploads, newest first, with date, lift, rep count and top fix.",
     "[integration] Another user's analysis can't be opened by changing its ID in the URL (returns 404).",
     "[unit] History can be filtered by lift.",
     "[unit] Unanalyzable and fallback results appear in history with their status.",
     "[e2e] Tapping an entry opens its full results."],
    "history")

# ======================= ALPHA: admin =======================
story("admin", "Inspect analyses and validator logs",
    "to see every analysis with its measurements, each AI attempt and each validator error",
    "I can find patterns in the AI's mistakes and investigate bad feedback",
    ["[integration] The admin page lists analyses newest first, showing lift, number of attempts and final status (passed first try, passed after retry, fallback, couldn't analyze).",
     "[unit] The list can be filtered by lift and final status.",
     "[integration] An analysis detail page shows the video, per-rep measurements, every LLM attempt, every validator error and the final result the user saw.",
     "[unit] A summary shows how often each validator error type occurred.",
     "[integration] Non-admin users get 403 on all admin pages and endpoints."],
    "admin", extra_labels=AI)

# ======================= BETA backlog =======================
story("gym goer", "Show processing status while I wait",
    "to see each analysis step while my video is processed",
    "I know the app is working",
    ["Steps shown: Uploading → Measuring → Writing feedback → Checking, updating without a refresh.",
     "When analysis finishes, results open automatically.",
     "If analysis fails, an error with Retry is shown instead of an endless spinner."],
    "results", milestone=BETA)
story("gym goer", "Compare a new upload with an older one",
    "to compare a new upload with an older one of the same lift",
    "I can see if I fixed the problem",
    ["Two uploads of the same lift can be shown side by side with key measurements.",
     "The comparison shows whether the earlier top fault appears in the newer upload.",
     "Uploads of different lifts can't be compared."],
    "history", milestone=BETA)
story("gym goer", "Delete my videos and account",
    "to delete my videos or my whole account",
    "I stay in control of my data",
    ["I can delete an upload after confirming, which removes its video, frames, measurements and AI output.",
     "I can delete my account and all its data from settings.",
     "Deleted data no longer appears anywhere in the app."],
    "accounts", milestone=BETA)
story("admin", "Blind trainer grading",
    "to send a sample of analyzed videos to trainers who grade them before seeing our feedback",
    "we can measure accuracy without bias",
    ["I can assign a random sample of N analyses to a trainer account.",
     "Trainers record their own top fault before seeing ours, then mark ours correct, partly correct or wrong.",
     "Trainers can't see users' names or emails."],
    "grading", milestone=BETA)
story("admin", "Hypothesis metrics dashboard",
    "a dashboard showing accuracy, helpfulness, cue adoption and 7-day return rate against their targets",
    "we can tell if our hypothesis is holding up",
    ["Shows trainer agreement (target ≥80%, fail <60%), ratings of 4–5 (≥70%, <50%), cue tried (≥60%, <40%) and 7-day return (≥50%, <30%).",
     "Each metric shows how many data points it's based on.",
     "Metrics can be filtered by date range."],
    "admin", milestone=BETA)
story("admin", "Adjust fault thresholds",
    "to change fault thresholds (such as degrees of knee cave) without changing code",
    "we can tune accuracy based on trainer feedback",
    ["Thresholds are stored in the database and edited on an admin page.",
     "Changes apply only to new analyses and are logged with who, when, and old and new values.",
     "Invalid values are rejected."],
    "admin", milestone=BETA)
story("admin", "Manage the fault list",
    "to add, edit or disable faults the AI can report",
    "feedback stays within what we can measure as we add checks",
    ["Each fault has an ID, name, lift, safety/technique tag, required camera angle and confirming measurement.",
     "Disabled faults can't be reported in new analyses."],
    "admin", milestone=BETA)
story("admin", "Track AI usage and cost",
    "to see LLM token usage and cost per analysis",
    "we know what the app costs to run",
    ["Shows total and average cost per analysis by day, including retries.",
     "Warns when 80% of a monthly budget is reached."],
    "admin", milestone=BETA)
story("admin", "Usage and moderation",
    "to see sign-ups and uploads over time and remove inappropriate uploads",
    "the app stays healthy and on-topic",
    ["Shows daily sign-ups, uploads and active users for the last 7 days, 30 days and all time.",
     "An admin can remove an upload with a reason; removals are logged and excluded from metrics."],
    "admin", milestone=BETA)
story("gym goer", "More lifts",
    "feedback on more lifts, such as overhead press and Romanian deadlift",
    "I can use the app for more of my workout",
    ["Each new lift has its own filming guide, measurements, fault list and labeled test videos before release."],
    "analysis", milestone=BETA)
