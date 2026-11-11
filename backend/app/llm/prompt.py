"""Builds the coaching request: measurements, confirmed faults, unmeasured checks, key frames and the note."""
from __future__ import annotations

import json

import cv2
import numpy as np

from app.faults import FaultCatalog, faults_for
from app.lifts import LIFT_NOUNS
from app.llm.client import KeyFrame, LLMMessage, LLMRequest
from app.llm.schema import coach_output_json_schema
from app.measure import SetMeasurements
from app.rules import NotMeasured

MIN_KEY_FRAMES, MAX_KEY_FRAMES = 3, 5

SYSTEM_PROMPT = """You are an experienced strength coach reviewing one set of a squat, deadlift or bench press.
You get measurements computed from the video, the faults those measurements confirm, the checks that
couldn't be measured, a few key frames and the lifter's optional note.

Rules:
- Reply with one JSON object that matches the given schema. No prose outside the JSON.
- Report analysis_lift as the lift, and the measured camera angle and rep count, exactly.
- Only cite faults from the fault list, on reps where the measurements confirm them. Never cite a check
  listed as not measured.
- Pick the single most important fault as the top fault. Safety faults always come first.
- supporting_measurement must be the fault's metric on one of the cited reps, copied from the measurements.
- Any angle or rep number you write must come from the measurements.
- The cue is one short, physical instruction for the next set: 12 words or fewer.
- Never diagnose, name injuries or predict injuries ("you have", "you will injure", "torn", "herniated").
- If the lifter's note mentions pain or injury, set professional_recommendation to advice to see a doctor
  or physical therapist. Otherwise set it to null.
- If no fault is confirmed, set top_fault_id to null, fault_reps to [], supporting_measurement to null,
  other_faults to [] and cue to "".
"""


def select_key_frames(m: SetMeasurements, confirmed: dict[str, list[int]], frame_indices: list[int],
                      catalog: FaultCatalog | None = None) -> list[tuple[int, int | None]]:
    """3-5 (frame index, rep) pairs: worst moments of confirmed faults first, then the bottom of each rep."""
    picks: list[tuple[int, int | None]] = []

    def add(index, rep):
        if index not in [p[0] for p in picks] and len(picks) < MAX_KEY_FRAMES:
            picks.append((index, rep))

    metric_of = {f.id: f.metric for f in faults_for(m.lift, catalog)}
    for fault_id, reps in confirmed.items():
        for rep in reps:
            worst = m.reps[rep - 1].worst_frames.get(metric_of[fault_id])
            if worst is not None:
                add(worst, rep)
    for r in m.reps:
        add(r.turn_frame, r.rep)
    for r in m.reps:
        add(r.start_frame, r.rep)
        add(r.end_frame, r.rep)
    if len(picks) < MIN_KEY_FRAMES and frame_indices:
        for k in np.linspace(0, len(frame_indices) - 1, MAX_KEY_FRAMES).astype(int):
            if len(picks) >= MIN_KEY_FRAMES:
                break
            add(frame_indices[k], None)
    return sorted(picks)


def encode_jpeg(image: np.ndarray, max_width: int = 768) -> bytes:
    h, w = image.shape[:2]
    if w > max_width:
        image = cv2.resize(image, (max_width, int(h * max_width / w)))
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("could not encode frame as JPEG")
    return buf.tobytes()


def build_payload(m: SetMeasurements, not_measured: list[NotMeasured], confirmed: dict[str, list[int]],
                  note: str | None, key_frames: list[KeyFrame], catalog: FaultCatalog | None = None) -> dict:
    return {
        "lift": m.lift,
        "analysis_lift": m.analysis_lift,
        "camera_angle": m.camera_angle,
        "rep_count": m.rep_count,
        "reps": [r.to_view() for r in m.reps],
        "confirmed_faults": confirmed,
        "not_measured": [c.to_dict() for c in not_measured],
        "note": note or None,
        "fault_list": [{"id": f.id, "name": f.name, "category": f.category, "metric": f.metric,
                        "threshold": f.threshold, "direction": f.direction} for f in faults_for(m.lift, catalog)],
        "key_frames": [{"frame_index": k.frame_index, "timestamp": round(k.timestamp, 2), "rep": k.rep} for k in key_frames],
    }


def build_llm_request(m: SetMeasurements, not_measured: list[NotMeasured], confirmed: dict[str, list[int]],
                      note: str | None, key_frames: list[KeyFrame], catalog: FaultCatalog | None = None) -> LLMRequest:
    payload = build_payload(m, not_measured, confirmed, note, key_frames, catalog)
    text = (
        f"The lifter selected: {LIFT_NOUNS[m.lift]}. The images are the key frames listed in key_frames, in order.\n\n"
        f"MEASUREMENTS AND CHECKS (JSON):\n{json.dumps(payload)}\n\n"
        f"Reply with JSON matching this schema:\n{json.dumps(coach_output_json_schema(m.analysis_lift, catalog))}"
    )
    return LLMRequest(system=SYSTEM_PROMPT, messages=[LLMMessage("user", text)], images=key_frames, payload=payload)


def build_retry_request(request: LLMRequest, previous_reply: str, errors: list[str]) -> LLMRequest:
    """Same request plus the failed reply and the exact validation errors."""
    feedback = ("Your reply failed validation. Fix every problem below and reply with the corrected JSON only.\n"
                + "\n".join(f"- {e}" for e in errors))
    return LLMRequest(system=request.system, images=request.images, payload=request.payload,
                      messages=[*request.messages, LLMMessage("assistant", previous_reply), LLMMessage("user", feedback)])
