"""US-20: compare owned uploads using saved, measurable evidence only."""
import uuid

import pytest

from app.measure import RepMeasurement
from tests.helpers import signup, upload_ok


def compare(client, headers, first, second):
    return client.get("/comparisons", params={"first_id": first, "second_id": second}, headers=headers)


def pair(client):
    headers, _ = signup(client)
    older = upload_ok(client, headers, filename="set.mp4")
    newer = upload_ok(client, headers, filename="clean.mp4")
    return headers, older, newer


def test_us20_same_lift_uploads_show_saved_videos_and_key_measurements_in_chronological_order(client, services):
    headers, older, newer = pair(client)
    calls = services.llm.calls
    response = compare(client, headers, newer, older)
    assert response.status_code == 200
    data = response.json()
    assert data["older"]["analysis_id"] == older and data["newer"]["analysis_id"] == newer
    assert data["older"]["video_url"] and data["newer"]["video_url"]
    metrics = {row["metric"]: row for row in data["metrics"]}
    old_values = [r.metrics["torso_lean_increase_deg"] for r in services.repo.list_rep_measurements(older)]
    new_values = [r.metrics["torso_lean_increase_deg"] for r in services.repo.list_rep_measurements(newer)]
    assert metrics["torso_lean_increase_deg"]["older"] == max(old_values)
    assert metrics["torso_lean_increase_deg"]["newer"] == max(new_values)
    assert metrics["rep_count"]["older"] == metrics["rep_count"]["newer"] == 5
    assert metrics["torso_lean_increase_deg"]["unit"] == "°"
    assert services.llm.calls == calls, "Comparison must not generate new AI claims"


def test_us20_earlier_fault_is_not_detected_when_new_measurements_no_longer_confirm_it(client):
    headers, older, newer = pair(client)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    assert response.json()["fault_comparison"] == {
        "fault_id": "hips_rise_early", "title": "Hips rise before your shoulders",
        "status": "not_detected", "older_reps": [4, 5], "newer_reps": [],
    }


def test_us20_earlier_fault_is_still_present_even_when_it_is_not_the_new_top_fix(client, services):
    headers, older, newer = pair(client)
    reps = services.repo.list_rep_measurements(newer)
    reps[0].metrics["torso_lean_increase_deg"] = 14
    services.repo.save_rep_measurements(newer, reps)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    assert response.json()["fault_comparison"]["status"] == "still_present"
    assert response.json()["fault_comparison"]["newer_reps"] == [1]


@pytest.mark.parametrize("reason", ["camera", "confidence", "missing_rep", "all_missing"])
def test_us20_unmeasurable_faults_are_never_reported_as_fixed(client, services, reason):
    headers, older, newer = pair(client)
    a = services.repo.get_analysis(newer)
    if reason == "camera":
        services.repo.update_analysis(newer, camera_angle="front")
    elif reason == "confidence":
        result = dict(a.result)
        result["not_measured"] = [{"check": "hips_rise_early", "name": "Hips rising early", "reason": "hips not visible"}]
        services.repo.update_analysis(newer, result=result)
    else:
        reps = services.repo.list_rep_measurements(newer)
        for rep in reps if reason == "all_missing" else reps[:1]:
            rep.metrics["torso_lean_increase_deg"] = None
        services.repo.save_rep_measurements(newer, reps)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    assert response.json()["fault_comparison"]["status"] == "not_measured"


def test_us20_measurements_only_results_can_be_compared_without_inventing_coaching(client, services):
    headers, older, newer = pair(client)
    services.repo.update_analysis(newer, final_status="fallback")
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    assert response.json()["fault_comparison"]["status"] == "not_detected"
    services.repo.update_analysis(older, final_status="fallback")
    assert compare(client, headers, older, newer).json()["fault_comparison"]["status"] == "unavailable"


def test_us20_no_earlier_top_fault_is_reported_explicitly(client):
    headers, _ = signup(client)
    older = upload_ok(client, headers, filename="clean.mp4")
    newer = upload_ok(client, headers)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    assert response.json()["fault_comparison"]["status"] == "no_previous_fault"


@pytest.mark.parametrize("lift, filename", [("deadlift", "deadlift.mp4"), ("bench_press", "bench.mp4")])
def test_us20_lift_specific_measurements_are_available_for_other_lifts(client, lift, filename):
    headers, _ = signup(client)
    older = upload_ok(client, headers, lift=lift, filename=filename)
    newer = upload_ok(client, headers, lift=lift, filename=filename)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    metrics = {row["metric"] for row in response.json()["metrics"]}
    assert "bar_drift_ratio" in metrics
    assert ("back_rounding_deg" if lift == "deadlift" else "lockout_elbow_angle_deg") in metrics


def test_us20_different_lifts_are_rejected_even_for_the_same_owner(client):
    headers, _ = signup(client)
    squat = upload_ok(client, headers)
    deadlift = upload_ok(client, headers, lift="deadlift", filename="deadlift.mp4")
    response = compare(client, headers, squat, deadlift)
    assert response.status_code == 422
    assert "same lift" in response.json()["detail"]


def test_us20_detected_lift_mismatch_cannot_silently_compare_different_movements(client, services):
    headers, older, newer = pair(client)
    a = services.repo.get_analysis(newer)
    services.repo.update_analysis(newer, result={**a.result, "lift": "bench_press"})
    assert compare(client, headers, older, newer).status_code == 422


@pytest.mark.parametrize("status, final_status", [("queued", None), ("processing", None), ("failed", None), ("done", "unanalyzable")])
def test_us20_unfinished_failed_and_unanalyzable_uploads_cannot_be_compared(client, services, status, final_status):
    headers, older, newer = pair(client)
    services.repo.update_analysis(newer, status=status, final_status=final_status)
    assert compare(client, headers, older, newer).status_code == 409


def test_us20_same_analysis_and_same_upload_retry_are_not_two_uploads(client, services):
    headers, older, _ = pair(client)
    assert compare(client, headers, older, older).status_code == 422
    a = services.repo.get_analysis(older)
    retry = str(uuid.uuid4())
    services.repo.create_analysis(retry, a.upload_id, a.user_id, a.lift)
    services.repo.update_analysis(retry, status="done", final_status="passed_first_try", result=a.result)
    assert compare(client, headers, older, retry).status_code == 422


def test_us20_both_uploads_must_be_owned_and_no_private_urls_are_disclosed(client):
    headers, older, newer = pair(client)
    other, _ = signup(client, "other@virginia.edu")
    own = upload_ok(client, other)
    assert compare(client, {}, older, newer).status_code == 401
    for first, second in [(older, own), (own, older), (own, "missing"), ("missing", own)]:
        response = compare(client, other, first, second)
        assert response.status_code == 404
        assert "video_url" not in response.text


def test_us20_rep_order_missing_values_and_zero_are_preserved(client, services):
    headers, older, newer = pair(client)
    reps = [RepMeasurement(rep=i, start_frame=i, turn_frame=i, end_frame=i, start_time=i, end_time=i,
                           metrics={"torso_lean_increase_deg": value, "bar_drift_ratio": 0})
            for i, value in [(1, 0), (2, 10)]]
    services.repo.save_rep_measurements(newer, reps)
    response = compare(client, headers, older, newer)
    assert response.status_code == 200
    data = response.json()
    assert data["fault_comparison"]["status"] == "not_detected", "Exactly 10° is not above the threshold"
    metrics = {row["metric"]: row for row in data["metrics"]}
    assert metrics["bar_drift_ratio"]["newer"] == 0
    assert metrics["hip_angle_min_deg"]["newer"] is None
