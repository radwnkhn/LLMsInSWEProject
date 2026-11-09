"""US-12: Rep-by-rep breakdown. (Tap-to-seek: frontend/e2e/us12-reps.spec.ts.)"""
import numpy as np
import pytest

from app.breakdown import FATIGUE_NOTE, build_rep_breakdown
from app.measure import measure_set
from app.pipeline import analyze_set
from app.results import build_result_view
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import squat

HIPS = "Hips rise before your shoulders"


def _reps(n):
    return measure_set(squat(n), "squat", fps=30).reps


# ---- [unit] one row per rep, in order ----

@pytest.mark.parametrize("n", [1, 3, 6])
def test_us12_one_row_per_measured_rep_in_order(n):
    rows = build_rep_breakdown(_reps(n), {})["rows"]
    assert len(rows) == n
    assert [r["rep"] for r in rows] == list(range(1, n + 1))
    assert all(r["start_time"] < r["end_time"] for r in rows)


# ---- [unit] each row is "Clean" or its validated faults ----

def test_us12_rows_show_clean_or_their_faults():
    rows = build_rep_breakdown(_reps(3), {2: [HIPS, "Squat isn't reaching depth"]})["rows"]
    assert rows[0]["clean"] is True and rows[0]["faults"] == []
    assert rows[1]["clean"] is False and rows[1]["faults"] == [HIPS, "Squat isn't reaching depth"]
    assert rows[2]["clean"] is True


def test_us12_breakdown_uses_validated_faults():
    outcome = analyze_set(squat(5, torso_bump={4: 25, 5: 25}), "squat", note=None, llm=RuleFollowingLLM(), fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    rows = build_result_view(outcome, note=None)["rep_breakdown"]["rows"]
    assert [r["clean"] for r in rows[:3]] == [True, True, True]
    assert HIPS in rows[3]["faults"] and HIPS in rows[4]["faults"]


# ---- [unit] fatigue note when faults appear only in the last third ----

def test_us12_fatigue_note_when_faults_only_in_last_third():
    assert FATIGUE_NOTE == "Form broke down late in the set, likely from fatigue."
    assert build_rep_breakdown(_reps(6), {5: [HIPS], 6: [HIPS]})["fatigue_note"] == FATIGUE_NOTE
    assert build_rep_breakdown(_reps(5), {5: [HIPS]})["fatigue_note"] == FATIGUE_NOTE


def test_us12_no_fatigue_note_when_a_fault_appears_earlier():
    assert build_rep_breakdown(_reps(6), {2: [HIPS], 6: [HIPS]})["fatigue_note"] is None
    assert build_rep_breakdown(_reps(6), {4: [HIPS], 6: [HIPS]})["fatigue_note"] is None


def test_us12_no_fatigue_note_for_a_clean_set():
    assert build_rep_breakdown(_reps(6), {})["fatigue_note"] is None


def test_us12_no_fatigue_note_for_sets_too_short_to_tell():
    assert build_rep_breakdown(_reps(2), {2: [HIPS]})["fatigue_note"] is None
