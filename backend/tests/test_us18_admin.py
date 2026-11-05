"""US-18: Inspect analyses and validator logs. (Admin UI: frontend/src/components/__tests__/us18-*.test.tsx.)"""
import pytest
from fastapi.testclient import TestClient

from app.admin import filter_admin_rows, summarize_validation_errors
from app.main import create_app
from app.repository import AdminAnalysisRow, AnalysisRecord
from app.services import build_test_services
from app.testing.fakes import SequenceLLM
from app.validator import ValidationIssue
from tests.helpers import make_admin, signup, upload_ok

ADMIN_ENDPOINTS = ["/admin/analyses", "/admin/analyses/00000000-0000-0000-0000-000000000000", "/admin/validator-errors"]


@pytest.fixture
def seeded():
    """Four analyses: passed first try, passed after retry, fallback, couldn't analyze (newest)."""
    llm = SequenceLLM(["pass", "invalid", "pass", "invalid", "invalid", "invalid"])
    services = build_test_services(llm=llm)
    client = TestClient(create_app(services))
    user, _ = signup(client)
    ids = [upload_ok(client, user), upload_ok(client, user, lift="squat"),
           upload_ok(client, user), upload_ok(client, user, filename="no_person.mp4")]
    admin, _ = make_admin(client, services)
    return client, services, admin, ids


# ---- [integration] list newest first with lift, attempts and final status ----

def test_us18_admin_list_newest_first_with_attempts_and_status(seeded):
    client, _, admin, ids = seeded
    r = client.get("/admin/analyses", headers=admin)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["analysis_id"] for i in items] == list(reversed(ids))
    assert [(i["final_status_label"], i["attempt_count"]) for i in items] == [
        ("Couldn't analyze", 0), ("Fallback", 3), ("Passed after retry", 2), ("Passed first try", 1)]
    assert all(i["lift"] == "squat" and i["user_email"] == "lifter@virginia.edu" for i in items)


# ---- [unit] filter by lift and final status ----

def _row(id_, lift, status):
    return AdminAnalysisRow(analysis=AnalysisRecord(id=id_, upload_id="u", user_id="x", lift=lift, status="done",
                                                    final_status=status), attempt_count=1, user_email="x@y.edu")


def test_us18_filter_rows_by_lift_and_status():
    rows = [_row("1", "squat", "fallback"), _row("2", "deadlift", "fallback"), _row("3", "squat", "passed_first_try")]
    assert [r.analysis.id for r in filter_admin_rows(rows, lift="squat")] == ["1", "3"]
    assert [r.analysis.id for r in filter_admin_rows(rows, final_status="fallback")] == ["1", "2"]
    assert [r.analysis.id for r in filter_admin_rows(rows, lift="squat", final_status="fallback")] == ["1"]
    assert filter_admin_rows(rows) == rows


def test_us18_api_filters(seeded):
    client, _, admin, ids = seeded
    items = client.get("/admin/analyses?final_status=fallback", headers=admin).json()["items"]
    assert [i["analysis_id"] for i in items] == [ids[2]]
    assert client.get("/admin/analyses?lift=deadlift", headers=admin).json()["items"] == []
    assert client.get("/admin/analyses?final_status=bogus", headers=admin).status_code == 422


# ---- [integration] detail page ----

def test_us18_detail_shows_video_measurements_attempts_errors_and_final_result(seeded):
    client, services, admin, ids = seeded
    d = client.get(f"/admin/analyses/{ids[1]}", headers=admin).json()
    assert "token=" in d["video_url"]
    assert [m["rep"] for m in d["measurements"]] == [1, 2, 3, 4, 5]
    assert [a["attempt_number"] for a in d["attempts"]] == [1, 2]
    assert d["attempts"][0]["output_text"] == "this is not JSON"
    assert d["attempts"][0]["errors"][0]["code"] == "invalid_json"
    assert d["attempts"][1]["errors"] == [] and d["attempts"][1]["passed"] is True
    assert d["attempts"][1]["input_tokens"] > 0
    assert d["result"] == services.repo.get_analysis(ids[1]).result
    assert d["result"]["top_fix"]["fault_id"] == "hips_rise_early"


def test_us18_detail_unknown_id_404(seeded):
    client, _, admin, _ = seeded
    assert client.get("/admin/analyses/00000000-0000-0000-0000-000000000000", headers=admin).status_code == 404


# ---- [unit] summary of validator error types ----

def test_us18_summarize_validation_errors():
    issues = [ValidationIssue("rep_count", "a"), ValidationIssue("rep_count", "b"), ValidationIssue("invalid_json", "c")]
    assert summarize_validation_errors(issues) == {"rep_count": 2, "invalid_json": 1}
    assert summarize_validation_errors([]) == {}


def test_us18_summary_sorted_most_common_first():
    issues = [ValidationIssue("a", ""), ValidationIssue("b", ""), ValidationIssue("b", "")]
    assert list(summarize_validation_errors(issues)) == ["b", "a"]


def test_us18_summary_endpoint(seeded):
    client, _, admin, _ = seeded
    counts = client.get("/admin/validator-errors", headers=admin).json()["counts"]
    assert counts == {"invalid_json": 4}


# ---- [integration] non-admins get 403 ----

@pytest.mark.parametrize("path", ADMIN_ENDPOINTS)
def test_us18_non_admin_gets_403(client, path):
    headers, _ = signup(client)
    assert client.get(path, headers=headers).status_code == 403


@pytest.mark.parametrize("path", ADMIN_ENDPOINTS)
def test_us18_anonymous_gets_401(client, path):
    assert client.get(path).status_code == 401
