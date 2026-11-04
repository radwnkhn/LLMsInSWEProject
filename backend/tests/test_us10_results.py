"""US-10: Show one top fix and one cue. (Screen rendering: frontend/src/components/__tests__/us10-*.test.tsx.)"""
import json

import numpy as np

from app.pipeline import analyze_set
from app.results import build_result_view
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import squat
from app.validator import validate
from tests.helpers import coach_output, context_for, signup, upload_ok


def _view(frames, note=None):
    outcome = analyze_set(frames, "squat", note=note, llm=RuleFollowingLLM(), fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    return build_result_view(outcome, note=note)


# ---- [unit] exactly one top fix in plain language ----

def test_us10_one_top_fix_in_plain_language():
    view = _view(squat(5, torso_bump={4: 25, 5: 25}))
    assert isinstance(view["top_fix"], dict)
    assert view["top_fix"]["fault_id"] == "hips_rise_early"
    assert view["top_fix"]["title"] == "Hips rise before your shoulders"
    assert "_" not in view["top_fix"]["title"]


# ---- [unit] exactly one cue, 12 words or fewer ----

def test_us10_one_cue_is_returned_with_the_top_fix():
    view = _view(squat(5, torso_bump={4: 25, 5: 25}))
    assert isinstance(view["cue"], str) and view["cue"]
    assert len(view["cue"].split()) <= 12


def test_us10_validator_rejects_cue_longer_than_12_words():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}))
    thirteen = "Keep your chest up and drive your upper back into the bar now"
    assert len(thirteen.split()) == 13
    result = validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], cue=thirteen), ctx)
    assert "cue_too_long" in [i.code for i in result.issues]
    twelve = "Keep your chest up and drive your upper back into the bar"
    assert validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], cue=twelve), ctx).ok


def test_us10_validator_requires_a_cue_with_a_top_fix():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}))
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["cue"] = "  "
    assert "missing_cue" in [i.code for i in validate(out, ctx).issues]


# ---- [unit] other validated faults go under "See more" ----

def test_us10_other_faults_are_separate_from_the_top_fix():
    view = _view(squat(5, torso_bump={4: 25, 5: 25}, depth_deg={1: 70}))
    others = [f["fault_id"] for f in view["other_faults"]]
    assert "insufficient_depth" in others
    assert view["top_fix"]["fault_id"] not in others
    assert all(set(f) >= {"fault_id", "title", "reps", "safety"} for f in view["other_faults"])


# ---- [unit] "No major issues found" ----

def test_us10_no_major_issues_when_nothing_passes():
    view = _view(squat(4))
    assert view["top_fix"] is None
    assert view["no_major_issues"] is True
    assert view["other_faults"] == []


def test_us10_faults_found_means_issues():
    assert _view(squat(5, torso_bump={4: 25, 5: 25}))["no_major_issues"] is False


# ---- [integration] what's shown is exactly the validated output ----

def test_us10_shown_fix_and_cue_equal_the_validated_output(client, services):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    result = client.get(f"/analyses/{analysis_id}", headers=headers).json()
    final = json.loads(services.repo.list_llm_attempts(analysis_id)[-1].output_text)
    assert result["top_fix"]["fault_id"] == final["top_fault_id"]
    assert result["cue"] == final["cue"]
    assert result["top_fix"]["reps"] == final["fault_reps"]
