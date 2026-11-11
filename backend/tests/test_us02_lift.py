"""US-02: Choose the lift before uploading. (Picker UI tests: frontend/src/components/__tests__/us02-*.test.tsx.)"""
import pytest

from app.lifts import LIFT_LABELS, LIFTS
from tests.helpers import signup, upload, upload_ok


def test_us02_backend_knows_the_supported_lifts():
    # US-28 added overhead press and Romanian deadlift after the original three ("exactly three" before US-28).
    assert LIFTS[:3] == ("squat", "deadlift", "bench_press")
    assert [LIFT_LABELS[l] for l in LIFTS] == ["Squat", "Deadlift", "Bench Press", "Overhead Press", "Romanian Deadlift"]


# ---- [integration] the selected lift is saved with the upload and passed to the analysis ----

@pytest.mark.parametrize("lift,filename", [("squat", "set.mp4"), ("deadlift", "deadlift.mp4"), ("bench_press", "bench.mp4")])
def test_us02_selected_lift_saved_and_passed_to_analysis(client, services, lift, filename):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers, lift=lift, filename=filename)
    analysis = services.repo.get_analysis(analysis_id)
    assert analysis.lift == lift
    assert services.repo.get_upload(analysis.upload_id).lift == lift
    assert services.llm.requests[-1].payload["lift"] == lift
    assert client.get(f"/analyses/{analysis_id}", headers=headers).json()["lift"] == lift


# ---- [integration] any other lift value is rejected with 422 ----

@pytest.mark.parametrize("lift", ["front_squat", "", "Squat", "SQUAT", "bench", "squat ", "Overhead Press"])
def test_us02_other_lift_values_rejected(client, services, lift):
    headers, _ = signup(client)
    r = upload(client, headers, lift=lift)
    assert r.status_code == 422
    assert services.storage.objects == {}


def test_us02_missing_lift_rejected(client):
    headers, _ = signup(client)
    r = client.post("/uploads", headers=headers, files={"file": ("set.mp4", b"x", "video/mp4")})
    assert r.status_code == 422
