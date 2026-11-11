"""US-27: Usage and moderation. (Admin UI: frontend/src/components/__tests__/us27-*.test.tsx.)

Acceptance criteria (#29):
1. [unit] [integration] [e2e] Sign-ups and uploads per day for a chosen date range, with totals.
2. [integration] [e2e] Upload list: date, lift, owner, status; filter by date and lift; links to its analysis.
3. [integration] [e2e] Remove an upload with a reason (off-topic, inappropriate, other): media deleted with the US-21
   deletion logic, gone from the owner's history, and a moderation log records who, when and why.
4. [integration] [e2e] The owner sees "This upload was removed by a moderator" instead of a broken page.
5. [unit] [e2e] Removal needs confirmation; the API rejects unconfirmed removals and invalid reasons.
6. [integration] Non-admins get 403 on the usage page, upload list, removal and moderation log.

In-memory repository, storage and auth only; no Supabase calls.
"""
import importlib
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import build_test_services
from tests.helpers import make_admin, signup, upload_ok

REMOVED = "This upload was removed by a moderator"


@pytest.fixture
def moderation():
    """app.moderation, imported per test so each test reports its own failure before the module exists."""
    return importlib.import_module("app.moderation")


@pytest.fixture
def admin(client, services):
    headers, _ = make_admin(client, services)
    return headers


def _at(day, hour=12):
    return datetime(2026, 11, day, hour, tzinfo=timezone.utc)


def _remove(client, headers, upload_id, reason="off_topic", **extra):
    return client.post(f"/admin/uploads/{upload_id}/remove", headers=headers,
                       json={"confirmed": True, "reason": reason, **extra})


def _upload_id(services, analysis_id):
    return services.repo.get_analysis(analysis_id).upload_id


def _backdate(services, analysis_id, when):
    """Moves an upload (and its analysis) to another time, for date-range tests."""
    upload_id = _upload_id(services, analysis_id)
    services.repo.uploads[upload_id] = replace(services.repo.uploads[upload_id], created_at=when)
    services.repo.analyses[analysis_id] = replace(services.repo.analyses[analysis_id], created_at=when)


# ---- 1. [unit] [integration] sign-ups and uploads per day ----

def test_us27_daily_usage_unit_counts_each_utc_day_including_empty_days(moderation):
    signups = [_at(1, 0), _at(1, 23), _at(3, 9)]
    uploads = [_at(1, 8), _at(2, 23), _at(2, 0), _at(3, 1), _at(3, 2)]
    report = moderation.daily_usage(signups, uploads, date(2026, 11, 1), date(2026, 11, 4))
    assert report["days"] == [
        {"date": "2026-11-01", "signups": 2, "uploads": 1},
        {"date": "2026-11-02", "signups": 0, "uploads": 2},
        {"date": "2026-11-03", "signups": 1, "uploads": 2},
        {"date": "2026-11-04", "signups": 0, "uploads": 0},
    ]
    assert report["totals"] == {"signups": 3, "uploads": 5}


def test_us27_daily_usage_unit_ignores_times_outside_the_range(moderation):
    report = moderation.daily_usage([datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc), _at(2, 0)],
                                    [datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)],
                                    date(2026, 11, 1), date(2026, 11, 2))
    assert report["totals"] == {"signups": 1, "uploads": 0}


def test_us27_admin_usage_reports_signups_and_uploads_per_day(client, services, admin):
    lifter, lifter_id = signup(client, "a@virginia.edu")
    signup(client, "b@virginia.edu")
    first, second = upload_ok(client, lifter), upload_ok(client, lifter)
    _backdate(services, first, _at(2, 10))
    services.repo.users[lifter_id] = replace(services.repo.users[lifter_id], created_at=_at(1, 9))

    r = client.get("/admin/usage?start=2026-11-01&end=2026-11-03", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["start"], body["end"]) == ("2026-11-01", "2026-11-03")
    assert [(d["date"], d["signups"], d["uploads"]) for d in body["days"]] == [
        ("2026-11-01", 1, 0), ("2026-11-02", 0, 1), ("2026-11-03", 0, 0)]
    assert body["totals"] == {"signups": 1, "uploads": 1}
    assert body["removals"] == 0
    assert second


def test_us27_admin_usage_defaults_to_the_last_30_days(client, services, admin):
    signup(client, "a@virginia.edu")
    body = client.get("/admin/usage", headers=admin).json()
    today = datetime.now(timezone.utc).date()
    assert (body["start"], body["end"]) == (str(today - timedelta(days=29)), str(today))
    assert len(body["days"]) == 30
    assert body["totals"]["signups"] == 2  # the lifter and the admin signed up today


@pytest.mark.parametrize("query", ["start=2026-11-10&end=2026-11-01", "start=Nov 1&end=2026-11-10",
                                   "start=2026-11-01&end=2026-13-01"])
def test_us27_admin_usage_rejects_invalid_ranges(client, admin, query):
    assert client.get(f"/admin/usage?{query}", headers=admin).status_code == 422


# ---- 2. [integration] upload list, filters and links ----

def test_us27_upload_list_shows_date_lift_owner_status_and_its_analysis(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    squat = upload_ok(client, lifter)
    bench = upload_ok(client, lifter, lift="bench_press", filename="bench.mp4")
    items = client.get("/admin/uploads", headers=admin).json()["items"]
    assert [i["analysis_id"] for i in items] == [bench, squat]          # newest first
    top = items[0]
    assert top["upload_id"] == _upload_id(services, bench)
    assert (top["lift"], top["lift_label"], top["user_email"]) == ("bench_press", "Bench Press", "a@virginia.edu")
    assert top["status_label"] == "Analyzed" and top["created_at"]
    assert top["filename"] == "bench.mp4"


def test_us27_upload_list_links_to_the_latest_analysis_after_a_retry(client, services, admin):
    services.video.fail_on_poses = True
    lifter, _ = signup(client, "a@virginia.edu")
    failed = upload_ok(client, lifter)
    services.video.fail_on_poses = False
    retried = client.post(f"/analyses/{failed}/retry", headers=lifter).json()["analysis_id"]
    items = client.get("/admin/uploads", headers=admin).json()["items"]
    assert len(items) == 1 and items[0]["analysis_id"] == retried


def test_us27_upload_list_filters_by_lift_and_date(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    old_squat, new_squat = upload_ok(client, lifter), upload_ok(client, lifter)
    bench = upload_ok(client, lifter, lift="bench_press", filename="bench.mp4")
    _backdate(services, old_squat, _at(1))
    ids = lambda q: [i["analysis_id"] for i in client.get(f"/admin/uploads?{q}", headers=admin).json()["items"]]
    assert ids("lift=squat") == [new_squat, old_squat]
    assert ids("lift=bench_press") == [bench]
    assert ids("start=2026-11-01&end=2026-11-01") == [old_squat]
    assert ids("start=2026-11-01&end=2026-11-01&lift=bench_press") == []
    assert client.get("/admin/uploads?lift=curl", headers=admin).status_code == 422
    assert client.get("/admin/uploads?start=2026-11-05&end=2026-11-01", headers=admin).status_code == 422


# ---- 3. [integration] removal deletes media, hides it from history and logs it ----

def test_us27_removal_deletes_media_hides_history_and_logs_who_when_why(client, services, admin):
    lifter, lifter_id = signup(client, "a@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    upload = services.repo.get_upload(_upload_id(services, analysis_id))
    frame = services.repo.get_analysis(analysis_id).frame_path
    assert upload.video_path in services.storage.objects and frame in services.storage.objects

    r = _remove(client, admin, upload.id, reason="inappropriate")
    assert r.status_code == 200, r.text
    entry = r.json()
    assert upload.video_path not in services.storage.objects and frame not in services.storage.objects
    assert client.get("/history", headers=lifter).json()["items"] == []
    assert services.repo.get_upload(upload.id) is None

    log = client.get("/admin/moderation-log", headers=admin).json()["items"]
    assert log == [entry]
    assert entry["upload_id"] == upload.id and entry["analysis_ids"] == [analysis_id]
    assert (entry["reason"], entry["reason_label"]) == ("inappropriate", "Inappropriate")
    assert entry["removed_by_email"] == "coach@virginia.edu" and entry["owner_email"] == "a@virginia.edu"
    assert entry["lift"] == "squat" and entry["note"] is None
    removed_at = datetime.fromisoformat(entry["removed_at"])
    assert abs(removed_at - datetime.now(timezone.utc)) < timedelta(minutes=1)
    assert lifter_id


def test_us27_removal_deletes_every_retry_and_its_frames(client, services, admin):
    services.video.fail_on_poses = True
    lifter, lifter_id = signup(client, "a@virginia.edu")
    failed = upload_ok(client, lifter)
    services.video.fail_on_poses = False
    retried = client.post(f"/analyses/{failed}/retry", headers=lifter).json()["analysis_id"]
    upload_id = _upload_id(services, failed)
    entry = _remove(client, admin, upload_id).json()
    assert sorted(entry["analysis_ids"]) == sorted([failed, retried])
    assert services.storage.list_paths(f"frames/{lifter_id}/") == []
    assert services.storage.list_paths(f"{lifter_id}/") == []


def test_us27_removal_and_owner_deletion_share_the_us21_deletion_logic(client, services, admin, monkeypatch):
    import app.main

    calls = []
    real = app.main.delete_upload_with_media

    def spy(repo, storage, upload, analyses):
        calls.append(upload.id)
        return real(repo, storage, upload, analyses)

    monkeypatch.setattr(app.main, "delete_upload_with_media", spy)
    lifter, _ = signup(client, "a@virginia.edu")
    mine, flagged = upload_ok(client, lifter), upload_ok(client, lifter)
    assert client.request("DELETE", f"/uploads/{_upload_id(services, mine)}", headers=lifter,
                          json={"confirmed": True}).status_code == 204
    assert _remove(client, admin, _upload_id(services, flagged)).status_code == 200
    assert len(calls) == 2


def test_us27_other_reason_keeps_an_optional_short_note(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    entry = _remove(client, admin, _upload_id(services, upload_ok(client, lifter)), reason="other",
                    note="  Not a lift  ").json()
    assert (entry["reason_label"], entry["note"]) == ("Other", "Not a lift")


def test_us27_uploads_still_processing_cannot_be_removed_yet(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    services.repo.update_analysis(analysis_id, status="processing")
    upload_id = _upload_id(services, analysis_id)
    r = _remove(client, admin, upload_id)
    assert r.status_code == 409
    assert services.repo.get_upload(upload_id) is not None
    assert client.get("/admin/moderation-log", headers=admin).json()["items"] == []


def test_us27_failed_media_deletion_leaves_no_log_entry(client, services, admin, monkeypatch):
    lifter, _ = signup(client, "a@virginia.edu")
    upload_id = _upload_id(services, upload_ok(client, lifter))

    def broken(paths):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(services.storage, "delete", broken)
    assert _remove(client, admin, upload_id).status_code == 502
    assert services.repo.get_upload(upload_id) is not None
    assert client.get("/admin/moderation-log", headers=admin).json()["items"] == []


def test_us27_removing_an_unknown_upload_returns_404(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    assert _remove(client, admin, _upload_id(services, upload_ok(client, lifter))).status_code == 200
    assert _remove(client, admin, "00000000-0000-0000-0000-000000000000").status_code == 404


def test_us27_removed_uploads_leave_usage_and_count_as_removals(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    keep, flagged = upload_ok(client, lifter), upload_ok(client, lifter)
    _remove(client, admin, _upload_id(services, flagged))
    body = client.get("/admin/usage", headers=admin).json()
    assert body["totals"]["uploads"] == 1 and body["removals"] == 1
    assert [i["analysis_id"] for i in client.get("/admin/uploads", headers=admin).json()["items"]] == [keep]


def test_us27_moderation_log_survives_the_owner_deleting_their_account(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    _remove(client, admin, _upload_id(services, upload_ok(client, lifter)))
    assert client.request("DELETE", "/account", headers=lifter, json={"confirmed": True}).status_code == 204
    log = client.get("/admin/moderation-log", headers=admin).json()["items"]
    assert len(log) == 1 and log[0]["owner_email"] is None and log[0]["removed_by_email"] == "coach@virginia.edu"


def test_us27_migration_creates_the_moderation_log():
    from tests.test_setup02_database import MIGRATIONS

    sql = "\n".join(p.read_text() for p in MIGRATIONS).lower()
    assert "create table if not exists public.moderation_log" in sql
    assert "alter table public.moderation_log enable row level security" in sql
    assert "on delete set null" in sql.split("public.moderation_log", 1)[1]


# ---- 4. [integration] the owner sees that a moderator removed it ----

def test_us27_owner_sees_removed_by_a_moderator_instead_of_a_broken_page(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    _remove(client, admin, _upload_id(services, analysis_id), reason="off_topic")
    r = client.get(f"/analyses/{analysis_id}", headers=lifter)
    assert r.status_code == 410
    assert REMOVED in r.json()["detail"] and "Off-topic" in r.json()["detail"]


def test_us27_others_still_get_not_found_for_a_removed_upload(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    other, _ = signup(client, "b@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    assert _remove(client, admin, _upload_id(services, analysis_id)).status_code == 200
    assert client.get(f"/analyses/{analysis_id}", headers=other).status_code == 404
    assert client.get(f"/analyses/{analysis_id}", headers=lifter).status_code == 410


def test_us27_comparing_with_a_removed_upload_explains_the_removal(client, services, admin):
    lifter, _ = signup(client, "a@virginia.edu")
    kept, removed = upload_ok(client, lifter), upload_ok(client, lifter)
    _remove(client, admin, _upload_id(services, removed))
    r = client.get(f"/comparisons?first_id={kept}&second_id={removed}", headers=lifter)
    assert r.status_code == 410 and REMOVED in r.json()["detail"]


# ---- 5. [unit] confirmation and a valid reason are required ----

def test_us27_reasons_unit_are_a_short_fixed_list(moderation):
    assert moderation.REMOVAL_REASONS == {"off_topic": "Off-topic", "inappropriate": "Inappropriate", "other": "Other"}


@pytest.mark.parametrize("body", [{"reason": "off_topic"}, {"confirmed": False, "reason": "off_topic"},
                                  {"confirmed": "yes", "reason": "off_topic"}, {"confirmed": True},
                                  {"confirmed": True, "reason": "spam"}, {"confirmed": True, "reason": ""},
                                  {"confirmed": True, "reason": "other", "note": "x" * 201}])
def test_us27_removal_needs_confirmation_and_a_valid_reason(client, services, admin, body):
    lifter, _ = signup(client, "a@virginia.edu")
    upload_id = _upload_id(services, upload_ok(client, lifter))
    r = client.post(f"/admin/uploads/{upload_id}/remove", headers=admin, json=body)
    assert r.status_code == 422, r.text
    assert services.repo.get_upload(upload_id) is not None


# ---- 6. [integration] non-admins get 403 ----

@pytest.mark.parametrize("method,path", [("get", "/admin/usage"), ("get", "/admin/uploads"),
                                         ("get", "/admin/moderation-log"), ("post", "remove")])
def test_us27_non_admin_gets_403(client, services, method, path):
    lifter, _ = signup(client, "a@virginia.edu")
    upload_id = _upload_id(services, upload_ok(client, lifter))
    if path == "remove":
        path = f"/admin/uploads/{upload_id}/remove"
    kwargs = {"json": {"confirmed": True, "reason": "off_topic"}} if method == "post" else {}
    assert getattr(client, method)(path, headers=lifter, **kwargs).status_code == 403
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert services.repo.get_upload(upload_id) is not None
