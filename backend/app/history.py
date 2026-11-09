"""A lifter's upload history."""
from __future__ import annotations

from app.lifts import LIFT_LABELS
from app.repository import AnalysisRecord

STATUS_LABELS = {
    "passed_first_try": "Analyzed",
    "passed_after_retry": "Analyzed",
    "fallback": "Measurements only",
    "unanalyzable": "Couldn't analyze",
}
JOB_LABELS = {"queued": "Processing", "processing": "Processing", "failed": "Failed"}


def status_label(a: AnalysisRecord) -> str:
    if a.status == "done" and a.final_status:
        return STATUS_LABELS[a.final_status]
    return JOB_LABELS.get(a.status, "Processing")


def history_item(a: AnalysisRecord) -> dict:
    top = (a.result or {}).get("top_fix")
    return {
        "analysis_id": a.id,
        "upload_id": a.upload_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "lift": a.lift,
        "lift_label": LIFT_LABELS[a.lift],
        "rep_count": a.rep_count,
        "top_fix_title": top["title"] if top else None,
        "status": a.status,
        "final_status": a.final_status,
        "status_label": status_label(a),
    }
