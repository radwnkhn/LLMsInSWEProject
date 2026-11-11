"""US-20: summaries and fault comparisons from saved measurements, without new AI calls."""
from __future__ import annotations

import math

from app.faults import DEFAULT_CATALOG, FaultCatalog
from app.repository import AnalysisRecord
from app.results import PASSED

COMPARABLE_STATUSES = (*PASSED, "fallback")


def _measured(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _blocked_metrics(a: AnalysisRecord, catalog: FaultCatalog) -> set[str]:
    result = a.result or {}
    skipped = {check["check"] for check in result.get("not_measured", [])}
    return {fault.metric for fault in catalog.all_for(a.lift)
            if fault.id in skipped or a.camera_angle not in fault.views}


def measurement_comparison(older: AnalysisRecord, newer: AnalysisRecord, older_reps, newer_reps,
                           catalog: FaultCatalog | None = None) -> list[dict]:
    # Disabled faults stay in the table: earlier results can still cite them (US-25).
    catalog = catalog or DEFAULT_CATALOG
    # Minimum/maximum describe the stored per-rep quantity; they do not score improvement.
    definitions = {}
    if older.lift in ("squat", "deadlift", "romanian_deadlift"):
        definitions.update(knee_angle_min_deg=("Knee angle", "°", "Minimum"),
                           hip_angle_min_deg=("Hip angle", "°", "Minimum"))
    else:
        definitions["elbow_angle_min_deg"] = ("Elbow angle", "°", "Minimum")
    for fault in catalog.all_for(older.lift):
        definitions[fault.metric] = (fault.metric_label.capitalize(), fault.unit or "thigh lengths",
                                     "Maximum" if fault.direction == "above" else "Minimum")

    blocked_old, blocked_new = _blocked_metrics(older, catalog), _blocked_metrics(newer, catalog)

    def aggregate(metric, reps, blocked, operation):
        if metric in blocked:
            return None
        values = [r.metrics.get(metric) for r in reps if _measured(r.metrics.get(metric))]
        return (max(values) if operation == "Maximum" else min(values)) if values else None

    rows = [{"metric": "rep_count", "label": "Reps", "unit": "reps", "aggregation": "Count",
             "older": older.rep_count, "newer": newer.rep_count}]
    for metric, (label, unit, operation) in definitions.items():
        rows.append({"metric": metric, "label": label, "unit": unit, "aggregation": operation,
                     "older": aggregate(metric, older_reps, blocked_old, operation),
                     "newer": aggregate(metric, newer_reps, blocked_new, operation)})
    return rows


def compare_earlier_fault(older: AnalysisRecord, newer: AnalysisRecord, newer_reps,
                          catalog: FaultCatalog | None = None) -> dict:
    catalog = catalog or DEFAULT_CATALOG
    top = (older.result or {}).get("top_fix")
    fault = catalog.get(older.lift, top["fault_id"]) if top else None
    view = {"fault_id": fault.id if fault else None, "title": fault.name if fault else None,
            "status": "unavailable", "older_reps": list(top.get("reps", [])) if top else [], "newer_reps": []}
    if older.final_status not in PASSED:
        return view
    if not top:
        return {**view, "status": "no_previous_fault"}
    if not fault:
        return view
    if fault.metric in _blocked_metrics(newer, catalog):
        return {**view, "status": "not_measured"}
    values = [(r.rep, r.metrics.get(fault.metric)) for r in newer_reps]
    confirmed = [rep for rep, value in values if _measured(value) and fault.is_confirmed(value)]
    if confirmed:
        return {**view, "status": "still_present", "newer_reps": confirmed}
    if not values or any(not _measured(value) for _, value in values):
        return {**view, "status": "not_measured"}
    return {**view, "status": "not_detected"}
