"""US-28: More lifts: overhead press and Romanian deadlift. (UI: frontend/src/components/__tests__/us28-*.test.tsx.)

Acceptance criteria (#30):
1. [unit] [e2e] Both lifts in the picker with filming guidance (backend: the lifts exist and are accepted).
2. [unit] Rep counting: overhead press from the wrists above the shoulders; RDL from the hip hinge angle.
3. [unit] Three side-view faults per lift, one of them safety, checked against hand-calculated values.
4. [integration] The new faults go through the US-25 fault list.
5. [unit] [integration] The validator and correction loop handle the new lifts like the existing ones.
6. [integration] [e2e] Both lifts are analyzed end to end.
7. [unit] [integration] Squat, deadlift and bench press are unchanged.

Synthetic side-view geometry (app/testing/synthetic.py), facing +x, so the expected values can be worked by hand:
- Overhead press: legs straight under the hip, torso TORSO=0.3, arm links 0.15 + 0.15. Wrist offset from the
  shoulder goes from the rack (+0.04, -0.03) to lockout (0, -D), D = 2 * 0.15 * sin(lockout / 2); the elbow comes
  from the two links, so the elbow angle is 2 * asin(d / 0.3) for shoulder-wrist distance d.
- Romanian deadlift: shin forward 0.4 f p, thigh back 0.6 f p (knee angle 180 - f p for knee flexion f), torso
  hinged 70 p forward, so the shoulder-hip-knee angle is 180 - (70 + 0.6 f) at the bottom.
"""
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.comparison import measurement_comparison
from app.faults import FAULTS, METRICS, FaultCatalog, default_faults
from app.lifts import LIFT_LABELS, LIFT_NOUNS, LIFTS
from app.llm.prompt import build_payload
from app.main import create_app
from app.measure import count_reps, detect_lift, height_signal, measure_set
from app.repository import AnalysisRecord
from app.rules import confirm_faults, not_measured_checks
from app.services import build_test_services
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat
from app.validator import build_validation_context, validate
from tests.helpers import coach_output, make_admin, signup, upload_ok

OHP, RDL = "overhead_press", "romanian_deadlift"


def _set(lift, n=5, view="side", **per_rep):
    """make_frames for `lift` with `n` reps; per_rep: field -> {rep number: value}."""
    reps = [RepSpec() for _ in range(n)]
    for name, values in per_rep.items():
        for rep_no, value in values.items():
            setattr(reps[rep_no - 1], name, value)
    return make_frames(SetSpec(lift=lift, reps=reps, view=view))


def _ctx(frames, lift, note=None):
    m = measure_set(frames, lift, fps=30)
    nm = not_measured_checks(m)
    return build_validation_context(m, nm, confirm_faults(m, nm), note), m


def codes(result):
    return [i.code for i in result.issues]


# ---- 1. [unit] [integration] the two lifts exist and are accepted ----

def test_us28_backend_knows_the_two_new_lifts_after_the_existing_three():
    assert LIFTS == ("squat", "deadlift", "bench_press", OHP, RDL)
    assert (LIFT_LABELS[OHP], LIFT_LABELS[RDL]) == ("Overhead Press", "Romanian Deadlift")
    assert (LIFT_NOUNS[OHP], LIFT_NOUNS[RDL]) == ("overhead press", "Romanian deadlift")


@pytest.mark.parametrize("lift,filename", [(OHP, "ohp.mp4"), (RDL, "rdl.mp4")])
def test_us28_uploads_of_the_new_lifts_are_saved_and_analyzed_as_that_lift(client, services, lift, filename):
    lifter, _ = signup(client)
    analysis_id = upload_ok(client, lifter, lift=lift, filename=filename)
    result = client.get(f"/analyses/{analysis_id}", headers=lifter).json()
    assert (result["lift"], result["lift_label"]) == (lift, LIFT_LABELS[lift])
    assert services.llm.requests[-1].payload["lift"] == lift


# ---- 2. [unit] rep counting ----

@pytest.mark.parametrize("n", [1, 3, 6])
def test_us28_overhead_press_reps_counted_from_the_wrists_above_the_shoulders(n):
    assert measure_set(_set(OHP, n), OHP, fps=30).rep_count == n


def test_us28_overhead_press_height_signal_runs_from_the_rack_to_lockout():
    # Rack: wrist 0.03 above the shoulder. Lockout (178°): D = 0.3 sin 89° = 0.2999 above it.
    signal = height_signal(_set(OHP, 1), OHP)
    assert min(signal) == pytest.approx(0.03, abs=0.005)
    assert max(signal) == pytest.approx(0.2999, abs=0.005)


def test_us28_overhead_press_rep_turns_at_lockout():
    frames = _set(OHP, 2)
    for rep in measure_set(frames, OHP, fps=30).reps:
        top = frames[rep.turn_frame].landmarks
        assert top["left_shoulder"].y - top["left_wrist"].y == pytest.approx(0.2999, abs=0.01)


@pytest.mark.parametrize("n", [1, 3, 6])
def test_us28_rdl_reps_counted_from_the_hip_hinge(n):
    assert measure_set(_set(RDL, n), RDL, fps=30).rep_count == n


def test_us28_rdl_hips_barely_drop_so_hip_height_alone_finds_no_reps():
    # Standing hip y = 0.9 - 0.2 - 0.2 = 0.5; at the bottom 0.9 - 0.2 cos 10° - 0.2 cos 15° = 0.510: a 0.01 drop,
    # far below the squat counter's minimum of a quarter thigh (0.05).
    frames = _set(RDL, 3)
    assert count_reps(height_signal(frames, "squat"), rest="high", min_amplitude=0.05) == []
    assert measure_set(frames, RDL, fps=30).rep_count == 3


def test_us28_rdl_rep_turns_at_the_bottom_of_the_hinge():
    frames = _set(RDL, 2)
    for rep in measure_set(frames, RDL, fps=30).reps:
        assert rep.metrics["hip_angle_min_deg"] == pytest.approx(95.0, abs=1.0)   # 180 - (70 + 0.6 * 25)


@pytest.mark.parametrize("lift", [OHP, RDL])
def test_us28_a_final_rep_that_never_finishes_is_not_counted(lift):
    frames = make_frames(SetSpec(lift=lift, reps=[RepSpec(), RepSpec()], trailing_partial=True))
    assert measure_set(frames, lift, fps=30).rep_count == 2


# ---- 3. [unit] faults measured from the side view ----

def test_us28_overhead_press_lockout_and_rack_elbow_angles_match_hand_calculation():
    # Lockout 150° gives D = 0.3 sin 75° = 0.2898 and the elbow back at 150°. Rack d = 0.05: 2 asin(0.05/0.3) = 19.2°.
    reps = measure_set(_set(OHP, 2, ohp_lockout={2: 150.0}), OHP, fps=30).reps
    assert reps[0].metrics["lockout_elbow_angle_deg"] == pytest.approx(178.0, abs=1.0)
    assert reps[1].metrics["lockout_elbow_angle_deg"] == pytest.approx(150.0, abs=1.0)
    assert reps[0].metrics["elbow_angle_min_deg"] == pytest.approx(19.2, abs=1.0)


def test_us28_overhead_press_backward_lean_matches_hand_calculation():
    reps = measure_set(_set(OHP, 2, back_lean={2: 20.0}), OHP, fps=30).reps
    assert reps[0].metrics["torso_lean_back_max_deg"] == pytest.approx(0.0, abs=1.0)
    assert reps[1].metrics["torso_lean_back_max_deg"] == pytest.approx(20.0, abs=1.0)


def test_us28_overhead_press_bar_drift_matches_hand_calculation():
    # Clean: the wrists travel 0.04 back to over the shoulders = 0.2 thigh lengths. Drift 0.12: 0.04 -> 0.12 = 0.4.
    reps = measure_set(_set(OHP, 2, bar_drift={2: 0.12}), OHP, fps=30).reps
    assert reps[0].metrics["bar_drift_ratio"] == pytest.approx(0.20, abs=0.02)
    assert reps[1].metrics["bar_drift_ratio"] == pytest.approx(0.40, abs=0.02)


def test_us28_rdl_knee_angle_matches_hand_calculation():
    reps = measure_set(_set(RDL, 2, rdl_knee_flex={2: 55.0}), RDL, fps=30).reps
    assert reps[0].metrics["knee_angle_min_deg"] == pytest.approx(155.0, abs=1.0)   # 180 - 25
    assert reps[1].metrics["knee_angle_min_deg"] == pytest.approx(125.0, abs=1.0)   # 180 - 55


def test_us28_rdl_back_rounding_and_bar_drift_match_hand_calculation():
    reps = measure_set(_set(RDL, 3, rounding={2: 25.0}, bar_drift={3: 0.06}), RDL, fps=30).reps
    assert reps[0].metrics["back_rounding_deg"] == pytest.approx(0.0, abs=1.0)
    assert reps[1].metrics["back_rounding_deg"] == pytest.approx(25.0, abs=1.0)
    assert reps[0].metrics["bar_drift_ratio"] == pytest.approx(0.0, abs=0.02)
    assert reps[2].metrics["bar_drift_ratio"] == pytest.approx(0.30, abs=0.02)      # 0.06 / 0.2


# First guesses, to be tuned with trainer grading (US-22) and threshold editing (US-24); see docs/tdd/us28.md.
NEW_FAULTS = {
    OHP: [("excessive_back_arch", "safety", "torso_lean_back_max_deg", 15.0, "above"),
          ("bar_path_drift", "technique", "bar_drift_ratio", 0.30, "above"),
          ("incomplete_lockout", "technique", "lockout_elbow_angle_deg", 165.0, "below")],
    RDL: [("rounded_back", "safety", "back_rounding_deg", 20.0, "above"),
          ("knees_bend_too_much", "technique", "knee_angle_min_deg", 140.0, "below"),
          ("bar_path_drift", "technique", "bar_drift_ratio", 0.15, "above")],
}


@pytest.mark.parametrize("lift", [OHP, RDL])
def test_us28_each_new_lift_has_three_side_view_faults_with_one_safety_fault_first(lift):
    faults = FAULTS[lift]
    assert [(f.id, f.category, f.metric, f.threshold, f.direction) for f in faults] == NEW_FAULTS[lift]
    assert faults[0].safety and sum(f.safety for f in faults) == 1
    assert all(f.views == frozenset({"side"}) for f in faults)


@pytest.mark.parametrize("lift,faulty,expected", [
    (OHP, {"back_lean": {3: 20.0}}, {"excessive_back_arch": [3]}),
    (OHP, {"ohp_lockout": {4: 150.0, 5: 150.0}}, {"incomplete_lockout": [4, 5]}),
    (OHP, {"bar_drift": {2: 0.12}}, {"bar_path_drift": [2]}),
    (RDL, {"rounding": {1: 25.0}}, {"rounded_back": [1]}),
    (RDL, {"rdl_knee_flex": {2: 55.0, 3: 55.0}}, {"knees_bend_too_much": [2, 3]}),
    (RDL, {"bar_drift": {5: 0.06}}, {"bar_path_drift": [5]}),
    (OHP, {}, {}),
    (RDL, {}, {}),
])
def test_us28_faults_are_confirmed_only_on_the_reps_that_cross_the_threshold(lift, faulty, expected):
    m = measure_set(_set(lift, 5, **faulty), lift, fps=30)
    nm = not_measured_checks(m)
    assert nm == []
    assert confirm_faults(m, nm) == expected


@pytest.mark.parametrize("lift", [OHP, RDL])
def test_us28_new_lift_faults_need_a_side_view(lift):
    m = measure_set(_set(lift, 2, view="angled"), lift, fps=30)
    assert {c.check: c.reason for c in not_measured_checks(m)} == {f.id: "needs a side view" for f in FAULTS[lift]}


@pytest.mark.parametrize("lift", [OHP, RDL])
def test_us28_metric_registry_matches_the_measurements_of_the_new_lifts(lift):
    computed = set(measure_set(_set(lift, 1), lift, fps=30).reps[0].metrics)
    assert set(METRICS[lift]) == computed
    for f in FAULTS[lift]:
        spec = METRICS[lift][f.metric]
        assert (spec.label, spec.unit, spec.views, spec.joints) == (f.metric_label, f.unit, f.views, f.joints)


def test_us28_comparisons_show_leg_angles_for_the_rdl_and_the_elbow_for_the_press():
    rdl = AnalysisRecord(id="a", upload_id="u", user_id="x", lift=RDL, camera_angle="side", result={})
    ohp = AnalysisRecord(id="b", upload_id="v", user_id="x", lift=OHP, camera_angle="side", result={})
    rdl_rows = {r["metric"] for r in measurement_comparison(rdl, rdl, [], [])}
    ohp_rows = {r["metric"] for r in measurement_comparison(ohp, ohp, [], [])}
    assert {"knee_angle_min_deg", "hip_angle_min_deg", "back_rounding_deg"} <= rdl_rows
    assert {"elbow_angle_min_deg", "lockout_elbow_angle_deg", "torso_lean_back_max_deg"} <= ohp_rows


# ---- 4. [integration] the new faults go through the US-25 fault list ----

def test_us28_admin_fault_list_shows_the_new_lifts_and_their_faults(client, services):
    admin, _ = make_admin(client, services)
    lifts = {g["lift"]: g for g in client.get("/admin/faults", headers=admin).json()["lifts"]}
    assert list(lifts) == list(LIFTS)
    for lift in (OHP, RDL):
        assert [f["id"] for f in lifts[lift]["faults"]] == [f[0] for f in NEW_FAULTS[lift]]
        assert lifts[lift]["lift_label"] == LIFT_LABELS[lift]
        assert [m["metric"] for m in lifts[lift]["metrics"]] == list(METRICS[lift])


def test_us28_disabling_a_new_fault_removes_it_from_the_prompt_and_the_validator_rejects_it():
    services = build_test_services()
    client = TestClient(create_app(services))
    admin, _ = make_admin(client, services)
    assert client.patch(f"/admin/faults/{RDL}/knees_bend_too_much", headers=admin,
                        json={"enabled": False}).status_code == 200
    lifter, _ = signup(client, "l@virginia.edu")
    upload_ok(client, lifter, lift=RDL, filename="rdl.mp4")
    payload = services.llm.requests[-1].payload
    assert "knees_bend_too_much" not in [f["id"] for f in payload["fault_list"]]

    frames = _set(RDL, 3, rdl_knee_flex={2: 55.0})
    m = measure_set(frames, RDL, fps=30)
    catalog = FaultCatalog(services.repo.list_faults())
    nm = not_measured_checks(m, catalog)
    ctx = build_validation_context(m, nm, confirm_faults(m, nm, catalog), None, catalog)
    enabled_ctx, _ = _ctx(frames, RDL)
    reply = coach_output(enabled_ctx, m, top="knees_bend_too_much", reps=[2], cue="Keep a soft knee and push the hips back")
    assert validate(reply, enabled_ctx).ok
    assert "fault_disabled" in codes(validate(reply, ctx))


def test_us28_migration_seeds_the_new_faults_and_allows_the_new_lifts():
    from tests.test_setup02_database import MIGRATIONS

    sql = "\n".join(p.read_text() for p in MIGRATIONS)
    for lift in (OHP, RDL):
        for fault in FAULTS[lift]:
            assert f"'{lift}', '{fault.id}'" in sql, fault.id
    us28 = [p for p in MIGRATIONS if "us28" in p.name]
    assert len(us28) == 1
    text = us28[0].read_text()
    for table in ("uploads", "analyses", "faults", "moderation_log"):
        assert f"alter table public.{table}" in text
    assert "'overhead_press'" in text and "'romanian_deadlift'" in text


# ---- 5. [unit] [integration] validator and correction loop ----

def test_us28_validator_accepts_a_correct_reply_and_rejects_a_wrong_rep_count_for_each_new_lift():
    for lift, faulty, top, reps in [(OHP, {"ohp_lockout": {4: 150.0}}, "incomplete_lockout", [4]),
                                    (RDL, {"rdl_knee_flex": {2: 55.0}}, "knees_bend_too_much", [2])]:
        ctx, m = _ctx(_set(lift, 5, **faulty), lift)
        good = coach_output(ctx, m, top=top, reps=reps, cue="Finish strong on every rep")
        assert validate(good, ctx).ok, validate(good, ctx).messages
        assert "rep_count" in codes(validate({**good, "rep_count": 4}, ctx))


def test_us28_validator_rejects_a_new_lift_fault_on_a_rep_where_it_wasnt_measured():
    ctx, m = _ctx(_set(RDL, 3, rdl_knee_flex={2: 55.0}), RDL)
    reply = coach_output(ctx, m, top="knees_bend_too_much", reps=[2], cue="Keep a soft knee and push the hips back")
    reply["fault_reps"] = [1, 2]
    assert "fault_not_confirmed" in codes(validate(reply, ctx))


def test_us28_validator_puts_the_new_safety_faults_first():
    ctx, m = _ctx(_set(OHP, 5, back_lean={3: 20.0}, ohp_lockout={4: 150.0}), OHP)
    assert set(ctx.confirmed) == {"excessive_back_arch", "incomplete_lockout"}
    lockout_first = coach_output(ctx, m, top="incomplete_lockout", reps=[4], others=[("excessive_back_arch", [3])],
                                 cue="Lock your elbows at the top")
    assert "safety_order" in codes(validate(lockout_first, ctx))
    arch_first = coach_output(ctx, m, top="excessive_back_arch", reps=[3], others=[("incomplete_lockout", [4])],
                              cue="Squeeze your glutes and keep your ribs down")
    assert validate(arch_first, ctx).ok, validate(arch_first, ctx).messages


def test_us28_validator_rejects_feedback_that_names_the_wrong_lift():
    ctx, m = _ctx(_set(RDL, 3), RDL)
    reply = coach_output(ctx, m)
    assert validate(reply, ctx).ok
    reply["lift"] = "deadlift"
    result = validate(reply, ctx)
    assert "lift_mismatch" in codes(result)
    assert "feedback says deadlift but the video shows a Romanian deadlift" in result.messages


@pytest.mark.parametrize("chosen", ["squat", "deadlift", "bench_press", RDL])
def test_us28_an_overhead_press_uploaded_as_another_lift_is_analyzed_as_an_overhead_press(chosen):
    frames = _set(OHP, 3)
    assert detect_lift(frames) == OHP
    ctx, m = _ctx(frames, chosen)
    assert ctx.lift == OHP
    reply = coach_output(ctx, m)
    reply["lift"] = chosen
    result = validate(reply, ctx)
    assert "lift_mismatch" in codes(result)
    assert any(msg.endswith("but the video shows an overhead press") for msg in result.messages)


@pytest.mark.parametrize("chosen,filmed", [(RDL, "deadlift"), ("deadlift", RDL)])
def test_us28_rdl_and_deadlift_keep_the_selected_lift_because_pose_alone_cant_tell_them_apart(chosen, filmed):
    ctx, _ = _ctx(_set(filmed, 3), chosen)
    assert ctx.lift == chosen


def test_us28_correction_loop_fixes_a_wrong_lift_reply_for_a_new_lift():
    class WrongLiftFirst(RuleFollowingLLM):
        def complete(self, request):
            reply = super().complete(request)
            if len(self.requests) > 1:
                return reply
            return replace(reply, text=json.dumps({**json.loads(reply.text), "lift": "deadlift"}))

    services = build_test_services(llm=WrongLiftFirst())
    client = TestClient(create_app(services))
    lifter, _ = signup(client)
    admin, _ = make_admin(client, services)
    analysis_id = upload_ok(client, lifter, lift=RDL, filename="rdl.mp4")
    assert client.get(f"/analyses/{analysis_id}", headers=lifter).json()["final_status"] == "passed_after_retry"
    attempts = client.get(f"/admin/analyses/{analysis_id}", headers=admin).json()["attempts"]
    assert [e["code"] for e in attempts[0]["errors"]] == ["lift_mismatch"]
    assert "Romanian deadlift" in services.llm.requests[1].messages[-1].content


# ---- 6. [integration] both lifts analyzed end to end ----

@pytest.mark.parametrize("lift,filename,top,label,reps", [
    (OHP, "ohp.mp4", "incomplete_lockout", "Elbow 150°", [4, 5]),
    (RDL, "rdl.mp4", "knees_bend_too_much", "Knee 125°", [2, 3]),
])
def test_us28_new_lifts_get_a_top_fix_cue_annotated_frame_and_rep_breakdown(client, lift, filename, top, label, reps):
    lifter, _ = signup(client)
    result = client.get(f"/analyses/{upload_ok(client, lifter, lift=lift, filename=filename)}", headers=lifter).json()
    assert result["final_status"] == "passed_first_try"
    assert result["top_fix"]["fault_id"] == top and result["top_fix"]["reps"] == reps
    assert result["cue"]
    assert result["annotated_frame"]["label"] == label and result["annotated_frame"]["image_url"]
    rows = result["rep_breakdown"]["rows"]
    assert len(rows) == 5 and [r["rep"] for r in rows if not r["clean"]] == reps
    assert result["camera_angle"] == "side" and result["not_measured"] == []


# ---- 7. [unit] [integration] squat, deadlift and bench press are unchanged ----

EXISTING = {
    "squat": [("knee_cave", 10), ("hips_rise_early", 10), ("insufficient_depth", 0), ("excessive_forward_lean", 55),
              ("bar_path_drift", 0.25)],
    "deadlift": [("rounded_back", 20), ("hips_rise_early", 10), ("bar_path_drift", 0.15), ("incomplete_lockout", 165)],
    "bench_press": [("elbow_flare", 75), ("bar_path_drift", 0.25), ("incomplete_lockout", 160), ("uneven_press", 0.1)],
}


def test_us28_existing_lifts_keep_their_faults_and_thresholds():
    assert {lift: [(f.id, f.threshold) for f in FAULTS[lift]] for lift in EXISTING} == EXISTING
    assert [f.lift for f in default_faults()][:13] == ["squat"] * 5 + ["deadlift"] * 4 + ["bench_press"] * 4


@pytest.mark.parametrize("lift", ["squat", "deadlift", "bench_press"])
def test_us28_existing_lifts_measure_and_detect_as_before(lift):
    frames = make_frames(SetSpec(lift=lift, reps=[RepSpec() for _ in range(3)]))
    m = measure_set(frames, lift, fps=30)
    assert m.rep_count == 3 and detect_lift(frames) == lift and m.analysis_lift == lift
    expected = {"squat": {"knee_angle_min_deg", "hip_angle_min_deg", "torso_lean_max_deg", "torso_lean_increase_deg",
                          "depth_margin", "bar_drift_ratio", "knee_valgus_deg"},
                "deadlift": {"knee_angle_min_deg", "hip_angle_min_deg", "torso_lean_max_deg", "torso_lean_increase_deg",
                             "back_rounding_deg", "lockout_hip_angle_deg", "bar_drift_ratio"},
                "bench_press": {"elbow_angle_min_deg", "lockout_elbow_angle_deg", "bar_drift_ratio", "elbow_flare_deg",
                                "wrist_height_diff_ratio"}}[lift]
    assert set(m.reps[0].metrics) == expected


def test_us28_the_squat_prompt_payload_is_unchanged_by_the_new_lifts():
    m = measure_set(squat(5, torso_bump={4: 25, 5: 25}), "squat", fps=30)
    nm = not_measured_checks(m)
    payload = build_payload(m, nm, confirm_faults(m, nm), None, [])
    assert [f["id"] for f in payload["fault_list"]] == [f.id for f in FAULTS["squat"]]
    assert payload["lift"] == "squat"
