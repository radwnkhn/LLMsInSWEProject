"""Rep-by-rep breakdown of a set."""
from __future__ import annotations

from app.measure import RepMeasurement

FATIGUE_NOTE = "Form broke down late in the set, likely from fatigue."
MIN_REPS_FOR_FATIGUE = 3


def build_rep_breakdown(reps: list[RepMeasurement], faults_by_rep: dict[int, list[str]]) -> dict:
    """One row per rep: "Clean" or its faults. Adds a fatigue note when faults appear only in the last third."""
    rows = [{"rep": r.rep, "start_time": r.start_time, "end_time": r.end_time,
             "faults": list(faults_by_rep.get(r.rep, [])), "clean": not faults_by_rep.get(r.rep)} for r in reps]
    n = len(reps)
    faulty = [row["rep"] for row in rows if not row["clean"]]
    late = n >= MIN_REPS_FOR_FATIGUE and faulty and all(rep > n * 2 / 3 for rep in faulty)
    return {"rows": rows, "fatigue_note": FATIGUE_NOTE if late else None}
