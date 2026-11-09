"""US-14: Safety issues always come first. (Warning label: frontend/src/components/__tests__/us14-*.test.tsx.)"""
import numpy as np
import pytest

from app.faults import faults_for
from app.lifts import LIFTS
from app.pipeline import analyze_set
from app.results import build_result_view
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import squat
from app.validator import validate
from tests.helpers import coach_output, context_for


# ---- [unit] every fault is tagged safety or technique ----

@pytest.mark.parametrize("lift", LIFTS)
def test_us14_every_fault_is_tagged_safety_or_technique(lift):
    faults = faults_for(lift)
    assert faults
    assert all(f.category in ("safety", "technique") for f in faults)
    assert any(f.category == "safety" for f in faults), f"{lift} needs at least one safety fault"


def test_us14_known_safety_faults():
    tagged = {(f.lift, f.id): f.category for lift in LIFTS for f in faults_for(lift)}
    assert tagged[("squat", "knee_cave")] == "safety"
    assert tagged[("deadlift", "rounded_back")] == "safety"
    assert tagged[("squat", "insufficient_depth")] == "technique"


# ---- [unit] the validator rejects output that doesn't put the safety fault first ----

@pytest.fixture
def both():
    # Front view: knee cave (safety) on rep 4, shallow depth (technique) on rep 2.
    return context_for(squat(5, view="front", valgus={4: 16}, depth_deg={2: 70}))


def test_us14_both_faults_are_confirmed(both):
    ctx, _ = both
    assert ctx.confirmed == {"knee_cave": [4], "insufficient_depth": [2]}


def test_us14_rejects_technique_fault_on_top_of_a_safety_fault(both):
    ctx, m = both
    out = coach_output(ctx, m, top="insufficient_depth", reps=[2], cue="Sit down until your hips pass your knees",
                       others=[("knee_cave", [4])])
    result = validate(out, ctx)
    assert "knee cave is a safety fault and must be the top fix" in [i.message for i in result.issues]
    assert "safety_order" in [i.code for i in result.issues]


def test_us14_rejects_leaving_out_a_confirmed_safety_fault(both):
    ctx, m = both
    out = coach_output(ctx, m, top="insufficient_depth", reps=[2], cue="Sit down until your hips pass your knees")
    assert "safety_order" in [i.code for i in validate(out, ctx).issues]


def test_us14_accepts_safety_fault_on_top(both):
    ctx, m = both
    out = coach_output(ctx, m, top="knee_cave", reps=[4], cue="Push your knees out over your toes",
                       others=[("insufficient_depth", [2])])
    assert validate(out, ctx).ok


# ---- [unit] safety faults are flagged for a warning label ----

def test_us14_result_view_flags_safety_faults():
    outcome = analyze_set(squat(5, view="front", valgus={4: 16}, depth_deg={2: 70}), "squat", note=None,
                          llm=RuleFollowingLLM(), fps=30, frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    view = build_result_view(outcome, note=None)
    assert view["top_fix"]["fault_id"] == "knee_cave"
    assert view["top_fix"]["safety"] is True
    assert [f["safety"] for f in view["other_faults"]] == [False]
