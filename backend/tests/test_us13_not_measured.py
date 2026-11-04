"""US-13: Say what couldn't be measured. (Section rendering: frontend/src/components/__tests__/us13-*.test.tsx.)"""
import dataclasses

import numpy as np

from app.measure import measure_set
from app.pipeline import analyze_set
from app.results import build_result_view
from app.rules import confirm_faults, not_measured_checks
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat


def _checks(frames, lift="squat"):
    return {c.check: c for c in not_measured_checks(measure_set(frames, lift, fps=30))}


# ---- [unit] front-view checks are "Not measured" from the side ----

def test_us13_knee_cave_not_measured_from_the_side():
    checks = _checks(squat(3))
    assert checks["knee_cave"].reason == "needs a front view"
    assert checks["knee_cave"].name == "Knees cave inward"


def test_us13_side_view_checks_not_measured_from_the_front():
    checks = _checks(squat(3, view="front"))
    assert checks["hips_rise_early"].reason == "needs a side view"
    assert "knee_cave" not in checks


def test_us13_angled_view_measures_only_view_independent_checks():
    checks = _checks(make_frames(SetSpec(view="angled", reps=[RepSpec(), RepSpec()])))
    assert "knee_cave" in checks and "hips_rise_early" in checks
    assert "insufficient_depth" not in checks


# ---- [unit] checks whose joints have low confidence ----

def test_us13_low_confidence_joints_listed_with_reason():
    frames = make_frames(SetSpec(lift="deadlift", reps=[RepSpec()] * 2, low_confidence={"ears": 0.9}))
    checks = _checks(frames, "deadlift")
    assert checks["rounded_back"].reason == "ears not clearly visible (pose confidence below 0.5)"


def test_us13_several_low_confidence_groups_all_named():
    frames = make_frames(SetSpec(lift="bench_press", reps=[RepSpec()] * 2, low_confidence={"wrists": 0.9, "elbows": 0.9}))
    reason = _checks(frames, "bench_press")["incomplete_lockout"].reason
    assert "elbows" in reason and "wrists" in reason


# ---- [unit] a not-measured check never appears as a fault ----

def test_us13_not_measured_checks_are_never_confirmed():
    for frames, lift in [(squat(3), "squat"), (squat(3, view="front", valgus={1: 20}), "squat"),
                         (make_frames(SetSpec(lift="deadlift", reps=[RepSpec(rounding=40)] * 2, low_confidence={"ears": 0.9})), "deadlift")]:
        m = measure_set(frames, lift, fps=30)
        nm = not_measured_checks(m)
        assert not ({c.check for c in nm} & set(confirm_faults(m, nm)))


def test_us13_result_view_drops_faults_that_were_not_measured():
    from app.llm.schema import FaultCitation, SupportingMeasurement

    outcome = analyze_set(squat(5, torso_bump={4: 25, 5: 25}), "squat", note=None, llm=RuleFollowingLLM(), fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    # Defense in depth: even if an unmeasurable fault slipped into the output, it must not be shown.
    sneaky = outcome.output.model_copy(update={"other_faults": [FaultCitation(
        fault_id="knee_cave", reps=[2], supporting_measurement=SupportingMeasurement(metric="knee_valgus_deg", rep=2, value=15.0))]})
    view = build_result_view(dataclasses.replace(outcome, output=sneaky), note=None)
    assert "knee_cave" not in [f["fault_id"] for f in view["other_faults"]]
    assert all("Knees cave inward" not in r["faults"] for r in view["rep_breakdown"]["rows"])
    assert "knee_cave" in [c["check"] for c in view["not_measured"]]


# ---- [unit] the section is empty (hidden) when everything was measured ----

def test_us13_nothing_listed_when_everything_could_be_measured():
    frames = make_frames(SetSpec(lift="deadlift", reps=[RepSpec()] * 3))
    m = measure_set(frames, "deadlift", fps=30)
    assert not_measured_checks(m) == []
    outcome = analyze_set(frames, "deadlift", note=None, llm=RuleFollowingLLM(), fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    assert build_result_view(outcome, note=None)["not_measured"] == []


# ---- [unit] bar checks are "Not measured" when there's no bar ----
# Found in manual testing: a bodyweight squat (arms held out front) was flagged for bar drift. Without a bar the
# app tracks the shoulders, so the check means nothing.

NO_BAR = "no bar on your back (your hands aren't at your shoulders)"


def _hands_at(frames, forward, down):
    """Puts both hands `forward` and `down` torso lengths from the shoulder midpoint (side view, facing -x)."""
    from app.measure import _mid
    from app.pose import Landmark, PoseFrame

    hand_parts = ("wrist", "pinky", "index", "thumb")
    out = []
    for f in frames:
        sx, sy = _mid(f, "shoulders")
        hx, hy = _mid(f, "hips")
        torso = ((sx - hx) ** 2 + (sy - hy) ** 2) ** 0.5
        lm = dict(f.landmarks)
        for side in ("left", "right"):
            for part in hand_parts:
                old = lm[f"{side}_{part}"]
                lm[f"{side}_{part}"] = Landmark(sx - forward * torso, sy + down * torso, old.confidence)
        out.append(PoseFrame(f.index, f.timestamp, lm))
    return out


def test_us13_bar_drift_not_measured_when_the_arms_are_held_out_front():
    frames = _hands_at(squat(3, bar_drift={2: 0.06}), forward=1.2, down=0.0)
    m = measure_set(frames, "squat", fps=30)
    checks = {c.check: c for c in not_measured_checks(m)}
    assert checks["bar_path_drift"].reason == NO_BAR
    assert "bar_path_drift" not in confirm_faults(m, list(checks.values()))


def test_us13_bar_drift_not_measured_when_the_hands_are_clasped_at_the_chest():
    assert _checks(_hands_at(squat(3), forward=0.6, down=0.4))["bar_path_drift"].reason == NO_BAR


def test_us13_bar_drift_still_measured_for_a_back_squat():
    frames = squat(3, bar_drift={2: 0.06})
    m = measure_set(frames, "squat", fps=30)
    checks = not_measured_checks(m)
    assert "bar_path_drift" not in [c.check for c in checks]
    assert confirm_faults(m, checks)["bar_path_drift"] == [2]


def test_us13_deadlift_and_bench_bar_checks_are_unaffected_by_hand_position():
    # The hands are on the bar in both lifts, wherever they are relative to the shoulders.
    for lift in ("deadlift", "bench_press"):
        frames = make_frames(SetSpec(lift=lift, reps=[RepSpec()] * 3))
        assert "bar_path_drift" not in _checks(frames, lift)
