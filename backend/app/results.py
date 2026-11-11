"""What the results screen shows, built only from measurements and validated output."""
from __future__ import annotations

from app.breakdown import build_rep_breakdown
from app.lifts import LIFT_LABELS
from app.pipeline import AnalysisOutcome
from app.safety import mentions_pain

FALLBACK_NOTE = "Coaching feedback isn't available for this video. Here are your measurements."
PROFESSIONAL_MESSAGE = ("You mentioned pain or an injury. Please see a doctor or physical therapist "
                        "before you keep training this lift.")
PASSED = ("passed_first_try", "passed_after_retry")


def _fault_view(fault, reps) -> dict:
    return {"fault_id": fault.id, "title": fault.name, "category": fault.category, "safety": fault.safety,
            "reps": list(reps)}


def build_result_view(outcome: AnalysisOutcome, note: str | None) -> dict:
    m = outcome.measurements
    lift = m.analysis_lift
    status = outcome.final_status
    view = {
        "final_status": status,
        "lift": m.lift,
        "lift_label": LIFT_LABELS[m.lift],
        "camera_angle": m.camera_angle if status != "unanalyzable" else None,
        "rep_count": m.rep_count,
        "unanalyzable_reason": outcome.unanalyzable_reason,
        "top_fix": None,
        "cue": None,
        "explanation": None,
        "no_major_issues": False,
        "other_faults": [],
        "not_measured": [c.to_dict() for c in outcome.not_measured],
        "rep_breakdown": None,
        "measurements": [r.to_view() for r in m.reps] if status != "unanalyzable" else [],
        "annotated_frame": None,
        "professional_message": PROFESSIONAL_MESSAGE if mentions_pain(note) else None,
        "fallback_note": FALLBACK_NOTE if status == "fallback" else None,
    }
    if status == "unanalyzable":
        return view

    unmeasured = {c.check for c in outcome.not_measured}
    catalog = outcome.catalog  # the fault list the analysis ran with
    faults_by_rep: dict[int, list[str]] = {}

    def mark(fault, reps):
        for r in reps:
            faults_by_rep.setdefault(r, []).append(fault.name)

    out = outcome.output if status in PASSED else None
    if out:
        top = catalog.get(lift, out.top_fault_id) if out.top_fault_id else None
        if top and top.id not in unmeasured:
            view["top_fix"] = _fault_view(top, out.fault_reps)
            view["cue"] = out.cue
            mark(top, out.fault_reps)
        view["explanation"] = out.explanation
        for c in out.other_faults:
            fault = catalog.get(lift, c.fault_id)
            if fault and fault.id not in unmeasured:
                view["other_faults"].append(_fault_view(fault, c.reps))
                mark(fault, c.reps)
        view["no_major_issues"] = view["top_fix"] is None and not view["other_faults"]
        if outcome.annotation and view["top_fix"]:
            view["annotated_frame"] = outcome.annotation.to_dict()
    else:
        # Fallback: no AI text, only what the measurements themselves confirm.
        for fault_id, reps in outcome.confirmed.items():
            mark(catalog.get(lift, fault_id), reps)

    view["rep_breakdown"] = build_rep_breakdown(m.reps, faults_by_rep)
    return view
