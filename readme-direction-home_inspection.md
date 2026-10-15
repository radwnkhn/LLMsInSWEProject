# Walkthrough: AI-generated home inspection reports

**Reference startups:** InspectionX, Binsr Inspect

## Overview

Walkthrough lets home inspectors capture photos, videos, and voice notes during an inspection and automatically turns them into a professional report. Every finding in the report links back to the media it came from.

**Target Audience:** Independent home inspectors and small inspection firms.

## 1. Solves One Problem Extremely Well

Inspectors spend 1 to 3 hours writing each report after the inspection. Walkthrough solves one problem: turning what the inspector already captures on site into a finished report, with no typing afterward.

## 2. Customer Access

- Local Charlottesville inspectors, whose contact info is public, for interviews and shadowing inspections.
- InterNACHI and ASHI chapters and online inspector groups.
- Real estate agents we know through family and UVA alumni, who work with inspectors weekly.

## 3. Technical Feasibility

- **Mobile app:** React Native (Expo) with offline capture
- **Web dashboard:** Next.js, React, Tailwind CSS
- **Backend:** Python (FastAPI)
- **Database and storage:** Supabase PostgreSQL and Storage
- **AI:** Multimodal LLM API (Claude, Gemini, or GPT) and Whisper for transcription
- **Reports:** HTML templates rendered to PDF

## 4. Reimagining the Existing Solution

- **Evidence-linked findings:** Tap any sentence to see the photo, video clip, or voice note behind it.
- **Coverage check:** Flags required inspection items with no capture yet, while the inspector is still on site.
- **Data plate reading:** Appliance photos fill in model and manufacture year automatically.
- **Report finished on site:** The draft builds as media uploads, so the inspector signs it in the driveway.

## 5. Essential Use of LLMs / Generative AI

The LLM reads voice note transcripts together with photos and video frames, extracts structured findings, places each in the correct report section, and rewrites informal notes ("no drip leg, TPR corroded") into professional, liability-safe report language. Templates and keyword rules cannot do this.

## 6. LLM Output Validation

No generated finding or report reaches the inspector or client without passing validation. The validator checks that:

- Output matches a strict JSON schema with fixed sections and severity levels.
- Every finding cites real photos, video timestamps, or transcript segments from this inspection.
- Every defect is supported by the inspector's own notes.
- Numbers (ages, measurements, model numbers) match the transcript or data plate exactly.
- Safety items (such as missing GFCI protection) are never downgraded.
- Text makes no code rulings, engineering conclusions, or guarantees.
- All items required by the Standards of Practice are covered.

## 7. Automatic Error Correction

Validation errors are sent back to the LLM, which regenerates. Examples:

- `"finding 6 says 2011, but the data plate says 2009"`
- `"finding 11 says 'does not meet code'; describe the observed condition instead"`

The corrected output is validated again. After three failed attempts, the finding goes to the inspector's review queue with the errors attached. All retries are logged.

## 8. Deployment Feasibility

- **Deployment:** Expo (TestFlight), Vercel, Render, Supabase, hosted LLM API
- **MVP:** Mobile capture, automatic report generation, coverage checklist, source-linked review screen, PDF export, and the validation loop.
- **Pilot:** Three to five local inspectors run Walkthrough alongside their current software, and we compare reports for accuracy and time saved.

## Conclusion

Walkthrough turns photos, videos, and voice notes into a finished inspection report on site, and its validator ensures every sentence is backed by real evidence and safe language.
