# FormCheck: AI feedback on your lifting form

**Reference category:** Camera-based fitness apps (e.g., Kemtai, Onyx)

## Overview

FormCheck lets lifters upload a video of a set and get specific feedback on their form: what to fix first and a cue to try on the next set. Every critique is backed by measurements taken from the video.

**Target Audience:** Beginner and intermediate lifters, especially college students who train without a coach.

## 1. Solves One Problem Extremely Well

Most people who lift alone don't know if their form is right, and trainers are expensive. FormCheck answers one question: "What should I fix on this lift?" It starts with the squat, deadlift, and bench press.

## 2. Customer Access

- UVA students who lift daily at the AFC, North Grounds, and Slaughter Rec.
- The UVA powerlifting and weightlifting clubs and club sports teams.
- Campus rec trainers who can review and grade our feedback.
- Ourselves, since we lift and can test on our own sets.

## 3. Technical Feasibility

- **Frontend:** Next.js, React, Tailwind CSS (mobile-first web app)
- **Backend:** Python (FastAPI)
- **Pose estimation:** MediaPipe Pose or MoveNet
- **Measurements:** NumPy for joint angles, depth, bar path, and rep counts
- **Database and storage:** Supabase PostgreSQL and Storage
- **AI:** Multimodal LLM API (Claude, Gemini, or GPT)

## 4. Reimagining the Existing Solution

- **Feedback you can see:** Each issue shows the exact rep and frame with the measurement overlaid.
- **One priority at a time:** One main fix and one cue, the way a coach works.
- **Rep-by-rep breakdown:** Shows when form broke down, such as on the last reps from fatigue.
- **Honest about limits:** If the camera angle makes something unmeasurable, the app says so instead of guessing.

## 5. Essential Use of LLMs / Generative AI

The LLM identifies the lift and camera angle, interprets video frames together with pose measurements to diagnose the underlying fault (for example, "hips rising before the shoulders"), decides what to fix first, and writes clear coaching feedback with a fitting cue. Fixed angle rules can flag numbers but cannot diagnose, prioritize, or coach.

## 6. LLM Output Validation

No generated feedback reaches the user without passing validation. The validator checks that:

- Output matches a strict JSON schema with fixed lift and fault lists.
- The identified lift matches the detected movement pattern.
- Every reported fault is confirmed by the measurements on the reps it cites.
- Rep counts, angles, and other numbers match the measured data exactly.
- Faults are only reported when the camera angle and pose confidence allow reliable measurement.
- Safety faults are always the top priority.
- Feedback contains no medical diagnoses or injury predictions, and recommends a professional if the user mentions pain.

## 7. Automatic Error Correction

Validation errors are sent back to the LLM, which regenerates. Examples:

- `"feedback says 6 reps but 5 were detected"`
- `"knee cave cited on rep 2, but measured valgus is 4° (threshold 10°)"`

The corrected output is validated again. After three failed attempts, the user gets only the verified measurements and rep breakdown. All retries are logged.

## 8. Deployment Feasibility

- **Deployment:** Vercel, Render, Supabase, hosted LLM API (web app, so no app store review)
- **MVP:** Video upload with filming guidance, pose analysis for three lifts, prioritized feedback with annotated frames, upload history, and the validation loop.
- **Pilot:** 20 to 30 campus lifters, with trainers grading our feedback for accuracy.

## Conclusion

FormCheck gives lifters who train alone a coach's eye: the generative model diagnoses and coaches, and the validator ensures every critique is backed by the video.
