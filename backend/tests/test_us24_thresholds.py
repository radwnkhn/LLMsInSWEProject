"""US-24: Adjust fault thresholds. (Admin UI: frontend/src/components/__tests__/us24-thresholds.test.tsx.)

Acceptance criteria (#26):
1. [unit] [integration] [e2e] An admin changes a fault's threshold on the fault list page; it is saved in the
   fault list in the database.
2. [unit] [integration] A changed threshold applies only to analyses started after the change.
3. [integration] [e2e] Every change is logged with who, when, and the old and new values; the log is shown.
4. [unit] [integration] [e2e] Invalid values are rejected and nothing is saved or logged.
5. [integration] Non-admins get 403 when changing a threshold and on the change log.

In-memory repository, storage and auth only; the default synthetic squat confirms "hips rise early" on reps 4
and 5 (torso lean increase 29°) and not on reps 1-3 (about 5°), against the default 10° threshold.
"""
from dataclasses import replace

import pytest

from app import faults
from app.faults import FAULTS, FaultCatalog
from app.measure import measure_set
from app.rules import confirm_faults, not_measured_checks
from app.testing.synthetic import scenario_frames
from tests.helpers import make_admin, signup, upload_ok

KNEE_CAVE, HIPS = FAULTS["squat"][0], FAULTS["squat"][1]
DEPTH = FAULTS["squat"][2]
BAR_DRIFT = FAULTS["squat"][4]


@pytest.fixture
def admin(client, services):
    headers, _ = make_admin(client, services)
    return headers


def _squat_faults(client, headers):
    return client.get("/admin/faults", headers=headers).json()["lifts"][0]["faults"]


def _threshold(client, headers, fault_id):
    return next(f["threshold"] for f in _squat_faults(client, headers) if f["id"] == fault_id)


def _set(client, headers, fault_id, value, lift="squat"):
    return client.patch(f"/admin/faults/{lift}/{fault_id}", headers=headers, json={"threshold": value})


def _changes(client, headers):
    r = client.get("/admin/faults/threshold-changes", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _faults_shown(view):
    return ([view["top_fix"]["fault_id"]] if view["top_fix"] else []) + [f["fault_id"] for f in view["other_faults"]]


# ---- 1. [unit] [integration] change a threshold and save it ----

def test_us24_threshold_is_an_editable_field():
    assert "threshold" in faults.FAULT_EDITABLE_FIELDS
    assert {"name", "short_name", "enabled"} <= faults.FAULT_EDITABLE_FIELDS


def test_us24_edit_fault_unit_changes_only_the_threshold():
    edited = faults.edit_fault(KNEE_CAVE, threshold=12)
    assert edited.threshold == 12.0 and isinstance(edited.threshold, float)
    assert replace(edited, threshold=KNEE_CAVE.threshold) == KNEE_CAVE


def test_us24_a_new_threshold_changes_which_values_are_confirmed():
    raised = faults.edit_fault(KNEE_CAVE, threshold=15)
    assert KNEE_CAVE.is_confirmed(12) and not raised.is_confirmed(12)
    assert raised.is_confirmed(16)
    lowered = faults.edit_fault(DEPTH, threshold=-0.1)          # "below": hips must clear the knee by 0.1 thigh
    assert DEPTH.is_confirmed(-0.05) and not lowered.is_confirmed(-0.05)


def test_us24_admin_changes_a_threshold_and_it_is_saved(client, admin, services):
    r = _set(client, admin, "knee_cave", 12.5)
    assert r.status_code == 200, r.text
    assert r.json()["threshold"] == 12.5 and r.json()["name"] == KNEE_CAVE.name
    assert _threshold(client, admin, "knee_cave") == 12.5
    assert services.repo.get_fault("squat", "knee_cave").threshold == 12.5


def test_us24_fault_list_shows_each_faults_allowed_range(client, admin):
    by_id = {f["id"]: f for f in _squat_faults(client, admin)}
    assert (by_id["knee_cave"]["threshold_min"], by_id["knee_cave"]["threshold_max"]) == (0, 180)
    assert (by_id["insufficient_depth"]["threshold_min"], by_id["insufficient_depth"]["threshold_max"]) == (-1, 1)
    assert (by_id["bar_path_drift"]["threshold_min"], by_id["bar_path_drift"]["threshold_max"]) == (0, 2)


def test_us24_threshold_and_name_can_change_together(client, admin):
    r = client.patch("/admin/faults/squat/knee_cave", headers=admin, json={"threshold": 14, "name": "Knees collapse"})
    assert r.status_code == 200, r.text
    assert (r.json()["threshold"], r.json()["name"]) == (14, "Knees collapse")


@pytest.mark.parametrize("lift,fault_id", [("deadlift", "rounded_back"), ("overhead_press", "excessive_back_arch"),
                                           ("bench_press", "uneven_press")])
def test_us24_thresholds_of_every_lift_can_change(client, admin, lift, fault_id):
    r = _set(client, admin, fault_id, 0.5 if fault_id == "uneven_press" else 25, lift=lift)
    assert r.status_code == 200, r.text


# ---- 2. [unit] [integration] only new analyses use the new value ----

def test_us24_unit_confirm_faults_follows_the_catalog_threshold():
    m = measure_set(scenario_frames("set.mp4"), "squat", fps=30)
    nm = not_measured_checks(m)
    assert confirm_faults(m, nm)["hips_rise_early"] == [4, 5]
    lowered = FaultCatalog([faults.edit_fault(f, threshold=4) if f.id == "hips_rise_early" and f.lift == "squat" else f
                            for f in faults.default_faults()])
    assert confirm_faults(m, not_measured_checks(m, lowered), lowered)["hips_rise_early"] == [1, 2, 3, 4, 5]


def test_us24_new_analyses_use_the_new_threshold_and_earlier_results_keep_theirs(client, admin):
    lifter, _ = signup(client)
    before = upload_ok(client, lifter)
    old_view = client.get(f"/analyses/{before}", headers=lifter).json()
    assert old_view["top_fix"]["fault_id"] == "hips_rise_early" and old_view["top_fix"]["reps"] == [4, 5]

    assert _set(client, admin, "hips_rise_early", 4).status_code == 200    # now every rep crosses it
    after = upload_ok(client, lifter)
    new_view = client.get(f"/analyses/{after}", headers=lifter).json()
    shown = {f["fault_id"]: f["reps"] for f in [new_view["top_fix"], *new_view["other_faults"]] if f}
    assert shown["hips_rise_early"] == [1, 2, 3, 4, 5]

    again = client.get(f"/analyses/{before}", headers=lifter).json()
    assert again["top_fix"] == old_view["top_fix"] and again["rep_breakdown"] == old_view["rep_breakdown"]


def test_us24_raising_a_threshold_stops_a_fault_being_reported_on_new_analyses(client, admin):
    lifter, _ = signup(client)
    assert _set(client, admin, "hips_rise_early", 30).status_code == 200   # above the 29° on reps 4 and 5
    view = client.get(f"/analyses/{upload_ok(client, lifter)}", headers=lifter).json()
    assert "hips_rise_early" not in _faults_shown(view)
    assert all("Hips rise before your shoulders" not in r["faults"] for r in view["rep_breakdown"]["rows"])


def test_us24_the_ai_is_told_the_new_threshold(client, admin, services):
    lifter, _ = signup(client)
    _set(client, admin, "hips_rise_early", 4)
    upload_ok(client, lifter)
    payload = services.llm.requests[-1].payload
    [hips] = [f for f in payload["fault_list"] if f["id"] == "hips_rise_early"]
    assert hips["threshold"] == 4


# ---- 3. [integration] every change is logged ----

def test_us24_each_change_is_logged_with_who_when_and_old_and_new_values(client, services):
    headers, admin_id = make_admin(client, services, "coach@virginia.edu")
    _set(client, headers, "knee_cave", 12)
    _set(client, headers, "knee_cave", 8)
    first, second = reversed(_changes(client, headers))          # newest first
    assert (first["lift"], first["fault_id"], first["old_threshold"], first["new_threshold"]) == ("squat", "knee_cave", 10, 12)
    assert (second["old_threshold"], second["new_threshold"]) == (12, 8)
    assert first["changed_by_email"] == "coach@virginia.edu"
    assert first["changed_at"] and second["changed_at"] >= first["changed_at"]
    assert (first["fault_name"], first["lift_label"], first["unit"]) == ("Knees cave inward", "Squat", "°")


def test_us24_changes_by_two_admins_are_told_apart(client, services):
    one, _ = make_admin(client, services, "coach@virginia.edu")
    two, _ = make_admin(client, services, "head.coach@virginia.edu")
    _set(client, one, "knee_cave", 12)
    _set(client, two, "bar_path_drift", 0.3)
    assert [c["changed_by_email"] for c in _changes(client, one)] == ["head.coach@virginia.edu", "coach@virginia.edu"]


def test_us24_name_or_enabled_changes_and_unchanged_values_are_not_logged(client, admin):
    client.patch("/admin/faults/squat/knee_cave", headers=admin, json={"name": "Knees collapse"})
    client.patch("/admin/faults/squat/knee_cave", headers=admin, json={"enabled": False})
    assert _set(client, admin, "knee_cave", 10).status_code == 200    # the current value again
    assert _changes(client, admin) == []


def test_us24_change_log_starts_empty(client, admin):
    assert _changes(client, admin) == []


# ---- 4. [unit] [integration] invalid values are rejected ----

@pytest.mark.parametrize("value", ["12", True, None, float("nan"), float("inf"), -1, 180.5, [12]])
def test_us24_edit_fault_unit_rejects_non_numeric_non_finite_or_out_of_range_angles(value):
    assert faults.edit_fault(KNEE_CAVE, threshold=12).threshold == 12     # a valid value is accepted
    with pytest.raises(faults.FaultError):
        faults.edit_fault(KNEE_CAVE, threshold=value)


@pytest.mark.parametrize("fault,value", [(DEPTH, -1.5), (DEPTH, 1.01), (BAR_DRIFT, -0.01), (BAR_DRIFT, 2.5)])
def test_us24_edit_fault_unit_rejects_out_of_range_ratios(fault, value):
    with pytest.raises(faults.FaultError, match="between"):
        faults.edit_fault(fault, threshold=value)


@pytest.mark.parametrize("fault,low,high", [(KNEE_CAVE, 0, 180), (DEPTH, -1, 1), (BAR_DRIFT, 0, 2)])
def test_us24_range_edges_are_allowed(fault, low, high):
    assert faults.threshold_range(fault) == (low, high)
    assert faults.edit_fault(fault, threshold=low).threshold == low
    assert faults.edit_fault(fault, threshold=high).threshold == high


def test_us24_new_faults_get_the_same_range_check():
    base = dict(lift="squat", id="knees_stay_bent", name="Knees stay bent", short_name="knee bend",
                category="technique", metric="knee_angle_min_deg", direction="below")
    assert faults.new_fault(**base, threshold=179).threshold == 179
    with pytest.raises(faults.FaultError, match="between"):
        faults.new_fault(**base, threshold=200)


@pytest.mark.parametrize("value", ["twelve", "12", None, True, -5, 181, [12], {"value": 12}])
def test_us24_admin_threshold_change_rejects_invalid_values_and_saves_nothing(client, admin, value):
    r = _set(client, admin, "knee_cave", value)
    assert r.status_code == 422, r.text
    assert _threshold(client, admin, "knee_cave") == 10
    assert _changes(client, admin) == []


def test_us24_rejection_explains_the_allowed_range(client, admin):
    r = _set(client, admin, "bar_path_drift", 3)
    assert r.status_code == 422
    assert "between 0 and 2" in r.json()["detail"]


def test_us24_threshold_change_of_unknown_fault_returns_404(client, admin):
    assert _set(client, admin, "no_such_fault", 12).status_code == 404
    assert _set(client, admin, "knee_cave", 12, lift="curl").status_code == 404


# ---- 5. [integration] admins only ----

def test_us24_non_admins_get_403_and_nothing_changes(client, admin):
    lifter, _ = signup(client, "lifter2@virginia.edu")
    assert _set(client, lifter, "knee_cave", 12).status_code == 403
    assert client.get("/admin/faults/threshold-changes", headers=lifter).status_code == 403
    assert _threshold(client, admin, "knee_cave") == 10
    assert _changes(client, admin) == []


def test_us24_signed_out_requests_get_401(client):
    assert client.patch("/admin/faults/squat/knee_cave", json={"threshold": 12}).status_code == 401
    assert client.get("/admin/faults/threshold-changes").status_code == 401
