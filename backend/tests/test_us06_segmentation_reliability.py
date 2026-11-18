"""US-06 regression: exercise evidence, rather than a whole-clip hip range, defines squat reps."""
import math
from dataclasses import replace

import numpy as np
import pytest

from app.measure import count_reps, height_signal, measure_set
from app.pipeline import analyze_set
from app.testing.fakes import RuleFollowingLLM, SpyLLM
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat, standing_still
from app.validator import build_validation_context, validate
from tests.helpers import coach_output
from tests.segmentation_sequences import forward_bend, join, red_team_hypothesis, walking


def test_us06_two_squats_and_a_bend_with_an_occluded_hip_error_count_exactly_two():
    frames = red_team_hypothesis()
    measured = measure_set(frames, "squat", 30)
    assert measured.rep_count == 2
    squat_end = len(make_frames(SetSpec(reps=[RepSpec(depth_deg=45), RepSpec(depth_deg=45)])))
    assert all(rep.end_frame < squat_end for rep in measured.reps)


@pytest.mark.parametrize("before", [True, False])
def test_us06_walking_before_or_after_is_excluded(before):
    frames = join(walking(), squat(2)) if before else join(squat(2), walking())
    m = measure_set(frames, "squat", 30)
    assert m.rep_count == 2
    if before:
        assert m.reps[0].start_frame >= len(walking())
    else:
        assert m.reps[-1].end_frame < len(squat(2))


def test_us06_five_squats_and_standing_pauses_remain_five_complete_reps():
    assert measure_set(squat(5), "squat", 30).rep_count == 5
    paused = join(squat(1), standing_still(150), squat(1), standing_still(90), squat(3))
    m = measure_set(paused, "squat", 30)
    assert m.rep_count == 5
    assert m.reps[1].start_frame >= len(squat(1)) + 150


def test_us06_a_forward_bend_with_pose_error_does_not_become_a_squat():
    llm = SpyLLM()
    outcome = analyze_set(forward_bend(occluded_hip_error=True), "squat", None, llm, 30)
    assert outcome.measurements.rep_count == 0
    assert outcome.final_status == "unanalyzable"
    assert llm.calls == 0


def test_us06_incomplete_final_squat_is_not_counted():
    frames = make_frames(SetSpec(reps=[RepSpec(), RepSpec()], trailing_partial=True))
    assert measure_set(frames, "squat", 30).rep_count == 2


def test_us06_long_tracking_gap_through_a_rep_does_not_generate_coaching():
    frames = squat(1)
    for i in range(20, 41):
        frames[i] = replace(frames[i], landmarks=None)
    llm = SpyLLM()
    result = analyze_set(frames, "squat", None, llm, 30)
    assert result.final_status == "unanalyzable"
    assert llm.calls == 0
    assert result.unanalyzable_reason


def test_us06_tracking_lost_at_end_cannot_silently_hide_the_last_rep():
    frames = squat(2)
    for i in range(75, len(frames)):
        frames[i].landmarks = None
    llm = SpyLLM()
    outcome = analyze_set(frames, "squat", None, llm, 30)
    assert outcome.final_status == "unanalyzable"
    assert llm.calls == 0


def test_us06_sudden_camera_scale_change_during_a_rep_is_rejected():
    frames = squat(2)
    for i in range(24, len(frames)):
        frames[i] = replace(frames[i], landmarks={name: replace(point, x=0.5+(point.x-0.5)*0.5,
                              y=0.5+(point.y-0.5)*0.5) for name, point in frames[i].landmarks.items()})
    llm = SpyLLM()
    result = analyze_set(frames, "squat", None, llm, 30)
    assert result.final_status == "unanalyzable"
    assert llm.calls == 0


def test_us06_low_confidence_coordinates_do_not_pollute_the_height_signal():
    frames = squat(1)
    baseline = height_signal(frames, "squat").copy()
    for f in frames:
        f.landmarks["right_hip"] = replace(f.landmarks["right_hip"], y=0.99, confidence=0.01)
    signal = height_signal(frames, "squat")
    assert np.max(np.abs(signal - baseline)) < 0.01


def test_us06_low_confidence_knees_do_not_create_angle_measurements():
    frames = make_frames(SetSpec(reps=[RepSpec(), RepSpec()], low_confidence={"knees": 1}))
    m = measure_set(frames, "squat", 30)
    assert all(rep.metrics["knee_angle_min_deg"] is None for rep in m.reps)


def test_us06_validator_rejects_a_self_consistent_reply_when_segmentation_is_unreliable():
    m = measure_set(squat(1), "squat", 30)
    m.segmentation_reliable = False
    m.segmentation_notes = ["Tracking was lost during the movement"]
    ctx = build_validation_context(m, [], {}, None)
    result = validate(coach_output(ctx, m, top=None), ctx)
    assert not result.ok
    assert "unreliable_measurements" in {issue.code for issue in result.issues}


def test_us06_missing_landmark_keys_and_nonfinite_points_cannot_fabricate_metrics():
    frames = squat(2)
    for f in frames:
        del f.landmarks["right_hip"]
        f.landmarks["left_knee"] = replace(f.landmarks["left_knee"], x=float("nan"))
    outcome = analyze_set(frames, "squat", None, SpyLLM(), 30)
    assert outcome.final_status == "unanalyzable"
    assert all(r.metrics["knee_angle_min_deg"] is None for r in outcome.measurements.reps)


def test_us06_bend_frames_cannot_supply_squat_form_feedback_or_annotation():
    frames = red_team_hypothesis()
    outcome = analyze_set(frames, "squat", None, RuleFollowingLLM(), 30)
    assert outcome.final_status in ("passed_first_try", "passed_after_retry")
    assert outcome.measurements.rep_count == 2
    cutoff = len(make_frames(SetSpec(reps=[RepSpec(depth_deg=45), RepSpec(depth_deg=45)])))
    assert all(i < cutoff for i in outcome.key_frame_indices)
    assert outcome.annotation is None or outcome.annotation.frame_index < cutoff


@pytest.mark.parametrize("broken", ["overlap", "turn", "evidence", "time", "time_overlap", "metric"])
def test_us06_validator_independently_checks_interval_and_evidence_consistency(broken):
    m = measure_set(squat(2), "squat", 30)
    if broken == "overlap":
        m.reps[1].start_frame = m.reps[0].start_frame
    elif broken == "turn":
        m.reps[0].turn_frame = m.reps[0].end_frame + 1
    elif broken == "evidence":
        m.reps[0].worst_frames["depth_margin"] = m.reps[0].end_frame + 1
    elif broken == "time_overlap":
        m.reps[1].start_time = m.reps[0].start_time
    elif broken == "metric":
        m.reps[0].metrics["knee_angle_min_deg"] = float("inf")
    else:
        m.reps[0].end_time = float("nan")
    ctx = build_validation_context(m, [], {}, None)
    result = validate(coach_output(ctx, m), ctx)
    assert not result.ok
    assert any(i.code == "unreliable_measurements" for i in result.issues)


@pytest.mark.parametrize("lift", ["deadlift", "bench_press", "overhead_press", "romanian_deadlift"])
def test_us06_other_supported_lifts_keep_their_own_segmentation(lift):
    frames = make_frames(SetSpec(lift=lift, reps=[RepSpec() for _ in range(3)]))
    assert measure_set(frames, lift, 30).rep_count == 3
