"""Plain rules over the measurements: which checks can't be measured, and which faults are confirmed."""
from __future__ import annotations

from dataclasses import dataclass

from app.faults import faults_for
from app.measure import SetMeasurements

VIEW_ORDER = ("side", "front", "angled")
NO_BAR_REASON = "no bar on your back (your hands aren't at your shoulders)"


@dataclass(frozen=True)
class NotMeasured:
    check: str   # fault id
    name: str
    reason: str

    def to_dict(self) -> dict:
        return {"check": self.check, "name": self.name, "reason": self.reason}


def not_measured_checks(m: SetMeasurements) -> list[NotMeasured]:
    out = []
    for fault in faults_for(m.lift):
        if m.camera_angle not in fault.views:
            views = " or ".join(v for v in VIEW_ORDER if v in fault.views)
            out.append(NotMeasured(fault.id, fault.name, f"needs a {views} view"))
            continue
        unclear = [g for g in fault.joints if g in m.low_confidence_groups]
        if unclear:
            out.append(NotMeasured(fault.id, fault.name,
                                   f"{' and '.join(unclear)} not clearly visible (pose confidence below 0.5)"))
            continue
        if fault.metric == "bar_drift_ratio" and not m.holds_bar:
            out.append(NotMeasured(fault.id, fault.name, NO_BAR_REASON))
    return out


def confirm_faults(m: SetMeasurements, not_measured: list[NotMeasured]) -> dict[str, list[int]]:
    """fault id -> reps on which the measurements cross the fault's threshold (measurable faults only)."""
    skip = {c.check for c in not_measured}
    confirmed: dict[str, list[int]] = {}
    for fault in faults_for(m.lift):
        if fault.id in skip:
            continue
        reps = [r.rep for r in m.reps if fault.is_confirmed(r.metrics.get(fault.metric))]
        if reps:
            confirmed[fault.id] = reps
    return confirmed
