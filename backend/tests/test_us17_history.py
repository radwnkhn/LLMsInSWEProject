"""US-17: Upload history. (Filter UI: frontend/src/components/__tests__/us17-*.test.tsx; tap-through: frontend/e2e/us17-history.spec.ts.)"""
import uuid

from fastapi.testclient import TestClient

from app.history import STATUS_LABELS, history_item
from app.main import create_app
from app.services import build_test_services
from app.testing.fakes import SequenceLLM
from tests.helpers import signup, upload_ok


# ---- [integration] only my uploads, newest first, with date, lift, rep count and top fix ----

def test_us17_history_lists_only_my_uploads_newest_first(client):
    a, _ = signup(client, "a@virginia.edu")
    b, _ = signup(client, "b@virginia.edu")
    first = upload_ok(client, a, lift="squat")
    upload_ok(client, b)
    second = upload_ok(client, a, lift="deadlift", filename="deadlift.mp4")
    items = client.get("/history", headers=a).json()["items"]
    assert [i["analysis_id"] for i in items] == [second, first]
    top = items[1]
    assert top["lift"] == "squat" and top["lift_label"] == "Squat"
    assert top["rep_count"] == 5
    assert top["top_fix_title"] == "Hips rise before your shoulders"
    assert top["created_at"]


def test_us17_empty_history(client):
    headers, _ = signup(client)
    assert client.get("/history", headers=headers).json()["items"] == []


# ---- [integration] another user's analysis can't be opened by changing the ID ----

def test_us17_other_users_analysis_returns_404(client):
    a, _ = signup(client, "a@virginia.edu")
    b, _ = signup(client, "b@virginia.edu")
    analysis_id = upload_ok(client, a)
    assert client.get(f"/analyses/{analysis_id}", headers=b).status_code == 404
    assert client.get(f"/analyses/{analysis_id}", headers=a).status_code == 200


def test_us17_unknown_or_malformed_ids_return_404(client):
    headers, _ = signup(client)
    assert client.get(f"/analyses/{uuid.uuid4()}", headers=headers).status_code == 404
    assert client.get("/analyses/not-a-uuid", headers=headers).status_code == 404


# ---- [unit] filter by lift ----

def test_us17_history_filtered_by_lift(client):
    headers, _ = signup(client)
    upload_ok(client, headers, lift="squat")
    upload_ok(client, headers, lift="deadlift", filename="deadlift.mp4")
    items = client.get("/history?lift=deadlift", headers=headers).json()["items"]
    assert [i["lift"] for i in items] == ["deadlift"]


def test_us17_history_filter_rejects_unknown_lift(client):
    headers, _ = signup(client)
    assert client.get("/history?lift=curl", headers=headers).status_code == 422


def test_us17_repository_filter_by_lift(client, services):
    headers, user_id = signup(client)
    upload_ok(client, headers, lift="squat")
    upload_ok(client, headers, lift="bench_press", filename="bench.mp4")
    assert [a.lift for a in services.repo.list_analyses_for_user(user_id, lift="bench_press")] == ["bench_press"]
    assert len(services.repo.list_analyses_for_user(user_id)) == 2


# ---- [unit] unanalyzable and fallback results show their status ----

def test_us17_status_labels():
    assert STATUS_LABELS["unanalyzable"] == "Couldn't analyze"
    assert STATUS_LABELS["fallback"] == "Measurements only"
    assert STATUS_LABELS["passed_first_try"] == STATUS_LABELS["passed_after_retry"] == "Analyzed"


def test_us17_unanalyzable_and_fallback_results_appear_with_status():
    services = build_test_services(llm=SequenceLLM(["invalid"] * 3))
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    upload_ok(client, headers, filename="no_person.mp4")
    upload_ok(client, headers)
    items = client.get("/history", headers=headers).json()["items"]
    assert [(i["final_status"], i["status_label"]) for i in items] == [
        ("fallback", "Measurements only"), ("unanalyzable", "Couldn't analyze")]
    assert items[0]["top_fix_title"] is None


def test_us17_history_item_while_processing():
    from app.repository import AnalysisRecord

    record = AnalysisRecord(id="a1", upload_id="u1", user_id="x", lift="squat", status="processing")
    item = history_item(record)
    assert item["status_label"] == "Processing"
    assert item["rep_count"] is None
