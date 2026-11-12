"""US-25: Manage the fault list. (Admin UI: frontend/src/components/__tests__/us25-*.test.tsx.)

Acceptance criteria (#27):
1. [integration] [e2e] An admin page lists every fault per lift (name, category, safety, measurement, enabled).
2. [unit] [integration] [e2e] An admin can edit a fault's display name and short description.
3. [unit] [integration] [e2e] Disable / re-enable: disabled faults leave the prompt and the validator rejects them.
4. [unit] [integration] [e2e] Adding a fault is only possible for a measurement the app already computes.
5. [integration] Non-admins get 403 on every fault endpoint.
6. [unit] [integration] Changes persist through the repository; new analyses use the saved list.
"""
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import faults
from app.faults import FAULTS
from app.lifts import LIFTS
from app.llm.prompt import build_payload
from app.llm.schema import coach_output_json_schema
from app.main import create_app
from app.measure import measure_set
from app.rules import confirm_faults, not_measured_checks
from app.services import build_test_services
from app.testing import synthetic
from app.testing.fakes import RuleFollowingLLM, ScriptedLLM
from app.validator import build_validation_context, validate
from tests.helpers import coach_output, make_admin, signup, upload_ok

# Every seeded default fault: the Alpha lifts, plus the two US-28 lifts.
ALPHA_FAULTS = [f for lift in FAULTS for f in FAULTS[lift]]
NEW_FAULT = {"lift": "squat", "id": "knees_stay_bent", "name": "Knees stay bent at the bottom", "short_name": "knee bend",
             "category": "technique", "metric": "knee_angle_min_deg", "threshold": 179, "direction": "below"}


def _disabled(lift, fault_id):
    return faults.FaultCatalog(replace(f, enabled=False) if (f.lift, f.id) == (lift, fault_id) else f for f in ALPHA_FAULTS)


@pytest.fixture
def admin(client, services):
    headers, _ = make_admin(client, services)
    return headers


def _result(client, headers, analysis_id):
    r = client.get(f"/analyses/{analysis_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---- 1. [integration] the admin list shows every fault per lift ----

def test_us25_admin_fault_list_shows_every_fault_per_lift(client, admin):
    r = client.get("/admin/faults", headers=admin)
    assert r.status_code == 200, r.text
    lifts = {group["lift"]: group for group in r.json()["lifts"]}
    assert list(lifts) == list(LIFTS)  # every lift, including the US-28 lifts
    assert lifts["bench_press"]["lift_label"] == "Bench Press"
    for lift, group in lifts.items():
        assert [f["id"] for f in group["faults"]] == [f.id for f in FAULTS[lift]]
        for shown, alpha in zip(group["faults"], FAULTS[lift]):
            assert shown["name"] == alpha.name and shown["short_name"] == alpha.short_name
            assert shown["category"] == alpha.category and shown["safety"] == alpha.safety
            assert shown["metric"] == alpha.metric and shown["metric_label"] == alpha.metric_label
            assert shown["enabled"] is True


def test_us25_admin_fault_list_offers_only_measurements_the_app_computes(client, admin):
    lifts = {g["lift"]: g for g in client.get("/admin/faults", headers=admin).json()["lifts"]}
    for lift, group in lifts.items():
        assert [m["metric"] for m in group["metrics"]] == list(faults.METRICS[lift])
        assert all(m["label"] for m in group["metrics"])


# ---- 2. [unit] [integration] edit the display name and short description ----

def test_us25_edit_fault_unit_changes_only_editable_fields():
    knee_cave = FAULTS["squat"][0]
    edited = faults.edit_fault(knee_cave, name="Knees collapse inward", short_name="knee collapse")
    assert (edited.name, edited.short_name) == ("Knees collapse inward", "knee collapse")
    assert replace(edited, name=knee_cave.name, short_name=knee_cave.short_name) == knee_cave
    assert faults.edit_fault(knee_cave, name="  Trimmed  ").name == "Trimmed"


@pytest.mark.parametrize("fields", [{"name": ""}, {"name": "   "}, {"name": "x" * 81}, {"short_name": ""},
                                    {"short_name": "x" * 41}, {"metric": "depth_margin"},
                                    {"category": "safety"}])
def test_us25_edit_fault_unit_rejects_blank_long_or_non_editable_values(fields):
    with pytest.raises(faults.FaultError):
        faults.edit_fault(FAULTS["squat"][0], **fields)


def test_us25_editable_fields_leave_thresholds_to_us24():
    # US-24 made thresholds editable too; US-25's own fields are unchanged.
    assert faults.FAULT_EDITABLE_FIELDS == {"name", "short_name", "enabled", "threshold"}


def test_us25_admin_edits_name_and_short_description(client, admin):
    r = client.patch("/admin/faults/squat/knee_cave", headers=admin,
                     json={"name": "Knees collapse inward", "short_name": "knee collapse"})
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["short_name"]) == ("Knees collapse inward", "knee collapse")
    squat = client.get("/admin/faults", headers=admin).json()["lifts"][0]["faults"]
    assert (squat[0]["name"], squat[0]["short_name"]) == ("Knees collapse inward", "knee collapse")


@pytest.mark.parametrize("body", [{"name": ""}, {"short_name": " "}, {"name": "x" * 81},
                                  {"metric": "depth_margin"}, {}])
def test_us25_admin_edit_rejects_blank_long_or_non_editable_values(client, admin, body):
    r = client.patch("/admin/faults/squat/knee_cave", headers=admin, json=body)
    assert r.status_code == 422, r.text
    squat = client.get("/admin/faults", headers=admin).json()["lifts"][0]["faults"]
    assert squat[0]["name"] == "Knees cave inward" and squat[0]["threshold"] == 10


@pytest.mark.parametrize("path", ["/admin/faults/squat/elbow_flare", "/admin/faults/curl/knee_cave"])
def test_us25_admin_edit_of_unknown_fault_returns_404(client, admin, path):
    assert client.patch("/admin/faults/squat/knee_cave", headers=admin, json={"name": "Anything"}).status_code == 200
    assert client.patch(path, headers=admin, json={"name": "Anything"}).status_code == 404


def test_us25_edited_name_appears_in_new_results(client, services, admin):
    client.patch("/admin/faults/squat/hips_rise_early", headers=admin, json={"name": "Hips shoot up first"})
    lifter, _ = signup(client)
    result = _result(client, lifter, upload_ok(client, lifter))
    assert result["top_fix"]["fault_id"] == "hips_rise_early"
    assert result["top_fix"]["title"] == "Hips shoot up first"


# ---- 3. [unit] [integration] disable and re-enable ----

def test_us25_disabled_fault_unit_is_left_out_of_prompt_schema_and_checks():
    m = measure_set(synthetic.squat(5, torso_bump={4: 25, 5: 25}), "squat", fps=30)
    catalog = _disabled("squat", "hips_rise_early")
    nm = not_measured_checks(m, catalog)
    confirmed = confirm_faults(m, nm, catalog)
    assert "hips_rise_early" not in confirmed
    assert "hips_rise_early" not in {c.check for c in nm}
    payload = build_payload(m, nm, confirmed, None, [], catalog)
    assert "hips_rise_early" not in [f["id"] for f in payload["fault_list"]]
    assert [f["id"] for f in payload["fault_list"]] == ["knee_cave", "insufficient_depth", "excessive_forward_lean",
                                                       "bar_path_drift"]
    schema = coach_output_json_schema("squat", catalog)
    assert "hips_rise_early" not in schema["properties"]["top_fault_id"]["anyOf"][0]["enum"]
    assert "hips_rise_early" not in schema["properties"]["other_faults"]["items"]["properties"]["fault_id"]["enum"]


def test_us25_validator_unit_rejects_a_reply_that_cites_a_disabled_fault():
    frames = synthetic.squat(5, torso_bump={4: 25, 5: 25})
    m = measure_set(frames, "squat", fps=30)
    enabled_ctx = build_validation_context(m, not_measured_checks(m), confirm_faults(m, not_measured_checks(m)), None)
    reply = coach_output(enabled_ctx, m, top="hips_rise_early", reps=[4, 5])
    assert validate(reply, enabled_ctx).ok

    catalog = _disabled("squat", "hips_rise_early")
    nm = not_measured_checks(m, catalog)
    ctx = build_validation_context(m, nm, confirm_faults(m, nm, catalog), None, catalog)
    result = validate(reply, ctx)
    assert [i.code for i in result.issues] == ["fault_disabled"]
    assert "hips rising early" in result.messages[0] and "disabled" in result.messages[0]


def test_us25_validator_still_reports_unknown_faults_separately():
    m = measure_set(synthetic.squat(3), "squat", fps=30)
    catalog = _disabled("squat", "hips_rise_early")
    ctx = build_validation_context(m, not_measured_checks(m, catalog), {}, None, catalog)
    reply = coach_output(ctx, m)
    reply.update(top_fault_id="made_up", fault_reps=[1], cue="Brace", supporting_measurement={"metric": "x", "rep": 1, "value": 1})
    assert [i.code for i in validate(reply, ctx).issues] == ["unknown_fault"]


def test_us25_disabled_fault_in_a_reply_starts_the_correction_loop():
    cites_disabled = {"lift": "squat", "camera_angle": "side", "rep_count": 5, "top_fault_id": "hips_rise_early",
                      "fault_reps": [4], "supporting_measurement": None, "other_faults": [],
                      "cue": "Drive your chest up", "explanation": "Hips rose early."}
    clean = {**cites_disabled, "top_fault_id": None, "fault_reps": [], "cue": "", "explanation": "Solid set."}
    llm = ScriptedLLM([json.dumps(cites_disabled), json.dumps(clean)])
    services = build_test_services(llm=llm)
    client = TestClient(create_app(services))
    admin, _ = make_admin(client, services)
    assert client.patch("/admin/faults/squat/hips_rise_early", headers=admin,
                        json={"enabled": False}).json()["enabled"] is False
    lifter, _ = signup(client)
    analysis_id = upload_ok(client, lifter)
    assert _result(client, lifter, analysis_id)["final_status"] == "passed_after_retry"
    attempts = client.get(f"/admin/analyses/{analysis_id}", headers=admin).json()["attempts"]
    assert "fault_disabled" in [e["code"] for e in attempts[0]["errors"]]
    assert attempts[1]["passed"] is True
    retry_text = llm.requests[1].messages[-1].content
    assert "disabled" in retry_text
    assert "hips_rise_early" not in [f["id"] for f in llm.requests[0].payload["fault_list"]]


def test_us25_disabled_then_reenabled_fault_is_reported_again(client, services, admin):
    lifter, _ = signup(client)
    client.patch("/admin/faults/squat/hips_rise_early", headers=admin, json={"enabled": False})
    disabled = _result(client, lifter, upload_ok(client, lifter))
    # The same set still shows its other confirmed faults, just not the disabled one.
    assert disabled["final_status"] == "passed_first_try"
    cited = [disabled["top_fix"]["fault_id"], *(f["fault_id"] for f in disabled["other_faults"])]
    assert "hips_rise_early" not in cited
    assert all("Hips rise before your shoulders" not in row["faults"] for row in disabled["rep_breakdown"]["rows"])

    r = client.patch("/admin/faults/squat/hips_rise_early", headers=admin, json={"enabled": True})
    assert r.json()["enabled"] is True
    enabled = _result(client, lifter, upload_ok(client, lifter))
    assert enabled["top_fix"]["fault_id"] == "hips_rise_early"


def test_us25_earlier_results_still_show_a_fault_disabled_later(client, admin):
    lifter, _ = signup(client)
    first = upload_ok(client, lifter)
    r = client.patch("/admin/faults/squat/hips_rise_early", headers=admin, json={"enabled": False})
    assert r.status_code == 200, r.text
    assert _result(client, lifter, first)["top_fix"]["fault_id"] == "hips_rise_early"
    second = upload_ok(client, lifter)
    comparison = client.get(f"/comparisons?first_id={first}&second_id={second}", headers=lifter)
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["fault_comparison"]["status"] == "still_present"


# ---- 4. [unit] [integration] add a fault only for an existing measurement ----

def test_us25_metric_registry_matches_what_the_measurement_code_computes():
    sets = {"squat": synthetic.squat(3), "deadlift": synthetic.make_frames(synthetic.SetSpec(lift="deadlift")),
            "bench_press": synthetic.make_frames(synthetic.SetSpec(lift="bench_press"))}
    for lift, frames in sets.items():
        computed = set(measure_set(frames, lift, fps=30).reps[0].metrics)
        assert set(faults.METRICS[lift]) == computed, lift
    for fault in ALPHA_FAULTS:
        spec = faults.METRICS[fault.lift][fault.metric]
        assert (spec.label, spec.unit, spec.views, spec.joints) == (fault.metric_label, fault.unit, fault.views,
                                                                    fault.joints)


def test_us25_new_fault_unit_takes_views_joints_and_unit_from_its_measurement():
    fault = faults.new_fault(**NEW_FAULT)
    spec = faults.METRICS["squat"]["knee_angle_min_deg"]
    assert (fault.views, fault.joints, fault.unit, fault.metric_label) == (spec.views, spec.joints, spec.unit, spec.label)
    assert fault.enabled and not fault.safety
    assert fault.is_confirmed(120) and not fault.is_confirmed(179.5)
    assert fault.format_value(120) == "120°"


@pytest.mark.parametrize("change", [{"metric": "how much it hurts"}, {"metric": "elbow_angle_min_deg"},
                                    {"lift": "curl"}, {"id": "Has Spaces"}, {"id": ""}, {"category": "style"},
                                    {"direction": "sideways"}, {"name": ""}, {"short_name": "x" * 41},
                                    {"threshold": float("nan")}, {"threshold": float("inf")}])
def test_us25_new_fault_unit_rejects_unmeasurable_or_invalid_input(change):
    with pytest.raises(faults.FaultError):
        faults.new_fault(**{**NEW_FAULT, **change})


def test_us25_admin_adds_a_fault_on_an_existing_measurement(client, admin):
    r = client.post("/admin/faults", headers=admin, json=NEW_FAULT)
    assert r.status_code == 201, r.text
    assert r.json()["metric_label"] == faults.METRICS["squat"]["knee_angle_min_deg"].label
    squat = client.get("/admin/faults", headers=admin).json()["lifts"][0]["faults"]
    assert squat[-1]["id"] == "knees_stay_bent" and squat[-1]["enabled"] is True


@pytest.mark.parametrize("change,status", [({"metric": "how much it hurts"}, 422), ({"metric": "elbow_angle_min_deg"}, 422),
                                           ({"lift": "curl"}, 422), ({"id": "knee_cave"}, 409),
                                           ({"category": "style"}, 422), ({"id": "Bad Id!"}, 422),
                                           ({"threshold": "deep"}, 422)])
def test_us25_admin_add_rejects_unmeasurable_unknown_or_duplicate_faults(client, admin, change, status):
    r = client.post("/admin/faults", headers=admin, json={**NEW_FAULT, **change})
    assert r.status_code == status, r.text
    squat = client.get("/admin/faults", headers=admin).json()["lifts"][0]["faults"]
    assert [f["id"] for f in squat] == [f.id for f in FAULTS["squat"]]


def test_us25_added_fault_is_offered_to_the_llm_and_reported(client, services, admin):
    client.post("/admin/faults", headers=admin, json=NEW_FAULT)
    lifter, _ = signup(client)
    result = _result(client, lifter, upload_ok(client, lifter, filename="clean.mp4"))
    payload = services.llm.requests[-1].payload
    assert "knees_stay_bent" in [f["id"] for f in payload["fault_list"]]
    assert result["final_status"] == "passed_first_try"
    assert result["top_fix"]["fault_id"] == "knees_stay_bent"
    assert result["top_fix"]["title"] == "Knees stay bent at the bottom"
    assert result["annotated_frame"]["metric"] == "knee_angle_min_deg"


# ---- 5. [integration] non-admins get 403 ----

FAULT_REQUESTS = [("get", "/admin/faults", None), ("patch", "/admin/faults/squat/knee_cave", {"enabled": False}),
                  ("post", "/admin/faults", NEW_FAULT)]


@pytest.mark.parametrize("method,path,body", FAULT_REQUESTS)
def test_us25_non_admin_gets_403_on_fault_endpoints(client, services, method, path, body):
    lifter, _ = signup(client)
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, headers=lifter, **kwargs).status_code == 403
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert services.repo.list_faults() == ALPHA_FAULTS


# ---- 6. [unit] [integration] changes persist; new analyses use the saved list ----

def test_us25_default_catalog_keeps_alpha_behavior():
    catalog = faults.FaultCatalog(ALPHA_FAULTS)
    for lift in FAULTS:
        assert catalog.faults_for(lift) == FAULTS[lift]
    m = measure_set(synthetic.squat(5, torso_bump={4: 25, 5: 25}), "squat", fps=30)
    nm = not_measured_checks(m)
    assert build_payload(m, nm, confirm_faults(m, nm), None, []) == build_payload(m, nm, confirm_faults(m, nm), None, [],
                                                                                  catalog)


def test_us25_analysis_uses_the_fault_list_saved_when_it_started(services, client, admin):
    class DisablesMidway(RuleFollowingLLM):
        def complete(self, request):
            services.repo.update_fault("squat", "hips_rise_early", enabled=False)
            return super().complete(request)

    services.llm = DisablesMidway()
    lifter, _ = signup(client)
    result = _result(client, lifter, upload_ok(client, lifter))
    assert result["final_status"] == "passed_first_try"
    assert result["top_fix"]["fault_id"] == "hips_rise_early"
    assert services.repo.get_fault("squat", "hips_rise_early").enabled is False


# ---- browser-test support: test mode needs an admin account to reach the fault list ----

def test_us25_test_mode_makes_only_reserved_domain_signups_admins():
    from app.services import services_from_env

    services = services_from_env({"ALIBI_TEST_MODE": "1"})
    assert services.auth.sign_up("coach@admin.test", "squat1234").user.is_admin is True
    assert services.auth.sign_up("lifter@virginia.edu", "squat1234").user.is_admin is False
    assert services.auth.sign_up("coach@admin.test.virginia.edu", "squat1234").user.is_admin is False
    assert build_test_services().auth.sign_up("coach@admin.test", "squat1234").user.is_admin is False
