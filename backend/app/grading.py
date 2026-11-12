"""US-22: blind trainer grading. Which analyses can be sampled for a trainer, and what a trainer may see.

A trainer first records their own top fault for the video, then sees the feedback the lifter was shown and
marks it correct, partly correct or wrong. Nothing here identifies the lifter: no email, note or file name.
"""
from __future__ import annotations

import random
from typing import Iterable, Sequence

from app.faults import FaultCatalog

GRADABLE_STATUSES = ("passed_first_try", "passed_after_retry")  # fallback/unanalyzable have no feedback to grade
MAX_SAMPLE = 50
NO_FAULT = "No major issue"
VERDICTS = {"correct": "Correct", "partly_correct": "Partly correct", "wrong": "Wrong"}
STATUS_LABELS = {"waiting": "To grade", "answered": "Answered", "graded": "Graded"}


def eligible_for_grading(analyses: Iterable, trainer_id: str, already_assigned: set[str], lift: str | None = None) -> list:
    """Finished analyses with validated feedback, not the trainer's own, not already theirs, in input order."""
    return [a for a in analyses
            if a.status == "done" and a.final_status in GRADABLE_STATUSES and a.user_id != trainer_id
            and a.id not in already_assigned and (lift is None or a.lift == lift)]


def sample_for_grading(candidates: Sequence, n: int, rng: random.Random | None = None) -> list:
    """A random sample of n candidates, or all of them when there are fewer."""
    pool = list(candidates)
    return (rng or random).sample(pool, min(n, len(pool)))


def assignment_status(assignment) -> str:
    if assignment.verdict is not None:
        return "graded"
    return "answered" if assignment.answered_at is not None else "waiting"


def fault_choice(fault_id: str | None, lift: str, catalog: FaultCatalog) -> dict:
    """A fault as {"fault_id", "name"}; None is "No major issue"."""
    if fault_id is None:
        return {"fault_id": None, "name": NO_FAULT}
    fault = catalog.get(lift, fault_id)
    return {"fault_id": fault_id, "name": fault.name if fault else fault_id}


def our_top_fault(result: dict | None) -> dict:
    """The top fix the lifter was shown, or "No major issue"."""
    top = (result or {}).get("top_fix")
    return {"fault_id": top["fault_id"], "name": top["title"]} if top else {"fault_id": None, "name": NO_FAULT}


def our_feedback(result: dict | None) -> dict:
    """The coaching the lifter was shown, without their measurements, note or any other detail about them."""
    result = result or {}

    def fault(f):
        return {"fault_id": f["fault_id"], "title": f["title"], "reps": list(f.get("reps", []))}

    return {"top_fix": fault(result["top_fix"]) if result.get("top_fix") else None, "cue": result.get("cue"),
            "explanation": result.get("explanation"), "other_faults": [fault(f) for f in result.get("other_faults", [])],
            "no_major_issues": bool(result.get("no_major_issues"))}
