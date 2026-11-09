"""US-08: Every claim is checked before I see it."""
import ast
import inspect
import socket

import pytest

import app.validator as validator_module
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat
from app.validator import validate
from tests.helpers import coach_output, context_for


def codes(result):
    return [i.code for i in result.issues]


def messages(result):
    return [i.message for i in result.issues]


@pytest.fixture
def squat_ctx():
    return context_for(squat(5, torso_bump={4: 25, 5: 25}))


# ---- [unit] schema ----

@pytest.mark.parametrize("mutate", [
    lambda o: o.pop("rep_count"),
    lambda o: o.update(rep_count="five"),
    lambda o: o.update(top_fault_id=7),
    lambda o: o.update(other_faults="none"),
])
def test_us08_rejects_output_that_breaks_the_schema(squat_ctx, mutate):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    mutate(out)
    result = validate(out, ctx)
    assert not result.ok
    assert codes(result) == ["schema"]


def test_us08_accepts_raw_json_text(squat_ctx):
    import json

    ctx, m = squat_ctx
    assert validate(json.dumps(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])), ctx).ok


# ---- [unit] lift must match the detected movement ----

def test_us08_rejects_wrong_lift_for_bench_video():
    frames = make_frames(SetSpec(lift="bench_press", reps=[RepSpec() for _ in range(3)]))
    ctx, m = context_for(frames, lift="bench_press")
    out = coach_output(ctx, m)
    out["lift"] = "deadlift"
    result = validate(out, ctx)
    assert "lift_mismatch" in codes(result)
    assert "feedback says deadlift but the video shows a bench press" in messages(result)


def test_us08_detected_movement_wins_over_the_selected_lift():
    # The lifter picked squat but filmed a bench set: the feedback must describe what's in the video.
    frames = make_frames(SetSpec(lift="bench_press", reps=[RepSpec() for _ in range(3)]))
    ctx, m = context_for(frames, lift="squat")
    out = coach_output(ctx, m)
    out["lift"] = "squat"
    assert "lift_mismatch" in codes(validate(out, ctx))


@pytest.mark.parametrize("chosen,filmed", [("squat", "deadlift"), ("deadlift", "squat")])
def test_us08_selected_standing_lift_is_kept_when_detection_disagrees(chosen, filmed):
    # Found in manual testing: a bodyweight squat with the arms held out front has the wrists at hip height,
    # which the detector reads as a deadlift, and the validator then forced the feedback to say "deadlift".
    # Telling squat from deadlift by wrist position is unreliable (goblet, front and bodyweight squats), so
    # only lying down vs standing overrides the lift the lifter picked.
    frames = make_frames(SetSpec(lift=filmed, reps=[RepSpec() for _ in range(3)]))
    ctx, m = context_for(frames, lift=chosen)
    assert ctx.lift == chosen
    out = coach_output(ctx, m)
    assert out["lift"] == chosen
    assert "lift_mismatch" not in codes(validate(out, ctx))


# ---- [unit] rep count ----

def test_us08_rejects_wrong_rep_count(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["rep_count"] = 6
    result = validate(out, ctx)
    assert "feedback says 6 reps but 5 were detected" in messages(result)


def test_us08_rejects_wrong_camera_angle(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["camera_angle"] = "front"
    assert "camera_angle_mismatch" in codes(validate(out, ctx))


# ---- [unit] faults must be confirmed by the measurements on the cited reps ----

def test_us08_rejects_fault_not_confirmed_on_cited_rep():
    ctx, m = context_for(squat(5, view="front", valgus={2: 4, 4: 16}))
    out = coach_output(ctx, m, top="knee_cave", reps=[4], cue="Push your knees out over your toes")
    out["fault_reps"] = [2, 4]
    result = validate(out, ctx)
    assert "knee cave cited on rep 2, but measured valgus is 4° (threshold 10°)" in messages(result)


def test_us08_accepts_fault_confirmed_on_every_cited_rep():
    ctx, m = context_for(squat(5, view="front", valgus={2: 4, 4: 16}))
    out = coach_output(ctx, m, top="knee_cave", reps=[4], cue="Push your knees out over your toes")
    assert validate(out, ctx).ok


def test_us08_rejects_fault_in_other_faults_too(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["other_faults"] = [{"fault_id": "excessive_forward_lean", "reps": [1],
                            "supporting_measurement": {"metric": "torso_lean_max_deg", "rep": 1,
                                                       "value": m.reps[0].metrics["torso_lean_max_deg"]}}]
    assert "fault_not_confirmed" in codes(validate(out, ctx))


def test_us08_rejects_rep_that_does_not_exist(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["fault_reps"] = [4, 5, 9]
    result = validate(out, ctx)
    assert "rep 9 cited for hips rising early, but only 5 reps were detected" in messages(result)


def test_us08_rejects_top_fault_without_reps(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["fault_reps"] = []
    assert not validate(out, ctx).ok


# ---- [unit] numbers must match the measured values ----

def test_us08_rejects_supporting_number_that_does_not_match(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    real = out["supporting_measurement"]["value"]
    out["supporting_measurement"]["value"] = real + 5
    result = validate(out, ctx)
    assert "number_mismatch" in codes(result)
    assert any(f"{real:.1f}" in msg for msg in messages(result))


def test_us08_allows_rounding_of_measured_numbers(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["supporting_measurement"]["value"] = round(out["supporting_measurement"]["value"])
    assert validate(out, ctx).ok


def test_us08_rejects_supporting_measurement_from_wrong_metric_or_rep(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["supporting_measurement"]["metric"] = "knee_angle_min_deg"
    assert "number_mismatch" in codes(validate(out, ctx))
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["supporting_measurement"]["rep"] = 1
    assert "number_mismatch" in codes(validate(out, ctx))


def test_us08_rejects_degrees_in_text_that_were_not_measured(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5],
                       explanation="Your torso tipped forward by 147° as you stood up.")
    result = validate(out, ctx)
    assert "number_mismatch" in codes(result)
    assert any("147°" in msg for msg in messages(result))


def test_us08_accepts_degrees_in_text_that_were_measured(squat_ctx):
    ctx, m = squat_ctx
    value = m.reps[3].metrics["torso_lean_increase_deg"]
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5],
                       explanation=f"On rep 4 your torso tipped forward by {value:.0f}° as you stood up.")
    assert validate(out, ctx).ok


def test_us08_rejects_rep_numbers_in_text_that_do_not_exist(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], explanation="By rep 7 your hips shot up.")
    assert "number_mismatch" in codes(validate(out, ctx))


def test_us08_rejects_rep_total_in_text_that_does_not_match(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], explanation="Across all 6 reps your hips rose early.")
    assert "number_mismatch" in codes(validate(out, ctx))


# ---- [unit] faults that can't be measured from this camera angle or pose confidence ----

def test_us08_rejects_fault_that_needs_a_different_camera_angle(squat_ctx):
    ctx, m = squat_ctx  # filmed from the side
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["other_faults"] = [{"fault_id": "knee_cave", "reps": [2],
                            "supporting_measurement": {"metric": "knee_valgus_deg", "rep": 2, "value": 12.0}}]
    result = validate(out, ctx)
    assert "knee cave can't be measured: needs a front view" in messages(result)


def test_us08_rejects_fault_whose_joints_had_low_confidence():
    frames = make_frames(SetSpec(lift="deadlift", reps=[RepSpec(rounding=30) for _ in range(3)],
                                 low_confidence={"ears": 0.9}))
    ctx, m = context_for(frames, lift="deadlift")
    out = coach_output(ctx, m)
    out.update(top_fault_id="rounded_back", fault_reps=[1], cue="Brace and keep your chest up",
               supporting_measurement={"metric": "back_rounding_deg", "rep": 1, "value": 30.0})
    result = validate(out, ctx)
    assert "rounded back can't be measured: ears not clearly visible (pose confidence below 0.5)" in messages(result)


# ---- [unit] valid output passes ----

def test_us08_valid_output_passes_with_no_errors(squat_ctx):
    ctx, m = squat_ctx
    result = validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5]), ctx)
    assert result.ok
    assert result.issues == []
    assert result.output.top_fault_id == "hips_rise_early"


def test_us08_clean_set_with_no_faults_passes():
    ctx, m = context_for(squat(4))
    assert validate(coach_output(ctx, m), ctx).ok


def test_us08_all_problems_reported_together(squat_ctx):
    ctx, m = squat_ctx
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["rep_count"] = 6
    out["fault_reps"] = [1, 4, 5]
    assert {"rep_count", "fault_not_confirmed"} <= set(codes(validate(out, ctx)))


# ---- [unit] the validator is plain code with no LLM calls ----

def test_us08_validator_imports_no_llm_or_network_code():
    tree = ast.parse(inspect.getsource(validator_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    forbidden = ("httpx", "requests", "anthropic", "openai", "google", "app.llm.client", "app.llm.providers", "socket")
    assert not [m for m in imported if m.startswith(forbidden)]


def test_us08_validator_works_with_the_network_blocked(squat_ctx, monkeypatch):
    ctx, m = squat_ctx

    def blocked(*args, **kwargs):
        raise AssertionError("validator tried to open a network connection")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    assert validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5]), ctx).ok
