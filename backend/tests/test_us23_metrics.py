"""US-23: Hypothesis metrics dashboard. (Admin UI: frontend/src/components/__tests__/us23-metrics.test.tsx.)

Acceptance criteria (#25):
1. [unit] [integration] [e2e] Four metrics against target and fail line: trainer agreement (>=80%, <60%), helpful ratings
   (>=70%, <50%), cue tried (>=60%, <40%) and 7-day return (>=50%, <30%).
2. [unit] Each is On target, Below target or Failing, or No data with nothing to count.
3. [unit] [integration] [e2e] Each shows how many data points it is based on.
4. [unit] [integration] [e2e] Date range filter (inclusive UTC dates, last 30 days by default); bad ranges rejected.
5. [integration] Non-admins get 403.

In-memory repository, storage and auth only; no Supabase calls.
"""
import importlib
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.helpers import make_admin, make_trainer, signup, upload_ok

NOW = datetime.now(timezone.utc)


@pytest.fixture
def metrics():
    """app.metrics, imported per test so each test reports its own failure before the module exists."""
    return importlib.import_module("app.metrics")


@pytest.fixture
def admin(client, services):
    headers, _ = make_admin(client, services)
    return headers


def _dashboard(client, headers, **params):
    r = client.get("/admin/metrics", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return {m["key"]: m for m in r.json()["metrics"]}, r.json()


def _backdate(services, analysis_id, when):
    """Moves an upload (and its analysis) to another time, for date-range and return tests."""
    upload_id = services.repo.get_analysis(analysis_id).upload_id
    services.repo.uploads[upload_id] = replace(services.repo.uploads[upload_id], created_at=when)
    services.repo.analyses[analysis_id] = replace(services.repo.analyses[analysis_id], created_at=when)


def _rate(client, headers, analysis_id, **body):
    r = client.post(f"/analyses/{analysis_id}/feedback", headers=headers, json=body)
    assert r.status_code == 200, r.text


# ---- 1, 2, 3. [unit] the metric calculations ----

def test_us23_unit_targets_and_fail_lines(metrics):
    assert [(k, t.target, t.fail_below) for k, t in metrics.TARGETS.items()] == [
        ("trainer_agreement", 0.8, 0.6), ("helpful_ratings", 0.7, 0.5), ("cue_tried", 0.6, 0.4),
        ("seven_day_return", 0.5, 0.3)]


@pytest.mark.parametrize("value,expected", [(None, "no_data"), (0.8, "on_target"), (1.0, "on_target"),
                                            (0.79, "below_target"), (0.6, "below_target"), (0.59, "failing"),
                                            (0.0, "failing")])
def test_us23_unit_status_from_value_target_and_fail_line(metrics, value, expected):
    assert metrics.status(value, target=0.8, fail_below=0.6) == expected


def test_us23_unit_status_labels(metrics):
    assert metrics.STATUS_LABELS == {"on_target": "On target", "below_target": "Below target", "failing": "Failing",
                                     "no_data": "No data"}


def test_us23_unit_trainer_agreement_counts_correct_of_graded(metrics):
    assert metrics.trainer_agreement(["correct", "correct", "partly_correct", "wrong"]) == (2, 4)
    assert metrics.trainer_agreement([]) == (0, 0)


def test_us23_unit_helpful_ratings_counts_4_and_5(metrics):
    assert metrics.helpful_ratings([5, 4, 3, 2, 1, None]) == (2, 5)


def test_us23_unit_cue_tried_counts_yes_of_yes_and_no(metrics):
    assert metrics.cue_tried(["yes", "yes", "no", "not_yet", None]) == (2, 3)


def _t(days_ago, hours=0):
    return NOW - timedelta(days=days_ago, hours=hours)


def test_us23_unit_seven_day_return(metrics):
    since, until = _t(30), NOW + timedelta(seconds=1)
    uploads = [
        ("returned", _t(20)), ("returned", _t(14)),              # back after 6 days
        ("on_the_day", _t(20)), ("on_the_day", _t(13)),          # back after exactly 7 days
        ("too_late", _t(20)), ("too_late", _t(12, 23)),          # 7 days and 1 hour: too late
        ("once", _t(20)),
        ("pending", _t(3)), ("pending", _t(2)),                  # first upload under 7 days ago: still waiting
        ("earlier", _t(40)), ("earlier", _t(20)),                # first upload before the range: not in it
    ]
    assert metrics.seven_day_return(uploads, since, until, now=NOW) == (2, 4, 1)


def test_us23_unit_share_and_basis(metrics):
    [agreement, *_] = metrics.build_metrics(verdicts=["correct", "wrong", "correct"], ratings=[], tried=[],
                                            uploads=[], since=_t(30), until=NOW, now=NOW)
    assert agreement["key"] == "trainer_agreement" and agreement["label"] == "Trainer agreement"
    assert agreement["value"] == pytest.approx(2 / 3)
    assert (agreement["hits"], agreement["count"], agreement["basis"]) == (2, 3, "3 graded sets")
    assert (agreement["status"], agreement["status_label"]) == ("below_target", "Below target")
    assert (agreement["target"], agreement["fail_below"]) == (0.8, 0.6)


def test_us23_unit_no_data_has_no_value_and_a_zero_count(metrics):
    for m in metrics.build_metrics(verdicts=[], ratings=[], tried=[], uploads=[], since=_t(30), until=NOW, now=NOW):
        assert (m["value"], m["count"], m["status"], m["status_label"]) == (None, 0, "no_data", "No data")


def test_us23_unit_basis_uses_singular_for_one(metrics):
    by_key = {m["key"]: m for m in metrics.build_metrics(verdicts=["correct"], ratings=[5], tried=["yes"],
                                                         uploads=[("a", _t(10))], since=_t(30), until=NOW, now=NOW)}
    assert [by_key[k]["basis"] for k in metrics.TARGETS] == ["1 graded set", "1 rating", "1 answer", "1 lifter"]


# ---- 1, 3. [integration] the dashboard endpoint ----

def test_us23_dashboard_lists_the_four_metrics_in_order_with_targets(client, admin):
    shown, body = _dashboard(client, admin)
    assert list(shown) == ["trainer_agreement", "helpful_ratings", "cue_tried", "seven_day_return"]
    assert [(m["target"], m["fail_below"]) for m in shown.values()] == [(0.8, 0.6), (0.7, 0.5), (0.6, 0.4), (0.5, 0.3)]
    assert all(m["status"] == "no_data" and m["count"] == 0 for m in shown.values())
    assert body["pending_returns"] == 0


def test_us23_trainer_agreement_comes_from_graded_assignments(client, services, admin):
    lifter, _ = signup(client)
    for _ in range(4):
        upload_ok(client, lifter)
    trainer, trainer_id = make_trainer(client, services)
    client.post("/admin/grading/assignments", headers=admin, json={"trainer_id": trainer_id, "count": 4})
    items = client.get("/trainer/assignments", headers=trainer).json()["items"]
    for item, verdict in zip(items, ["correct", "correct", "partly_correct", None]):
        aid = item["assignment_id"]
        client.post(f"/trainer/assignments/{aid}/answer", headers=trainer, json={"fault_id": None})
        if verdict:
            client.post(f"/trainer/assignments/{aid}/verdict", headers=trainer, json={"verdict": verdict})
    agreement = _dashboard(client, admin)[0]["trainer_agreement"]
    assert (agreement["hits"], agreement["count"]) == (2, 3)                       # the ungraded one isn't counted
    assert agreement["value"] == pytest.approx(2 / 3) and agreement["status"] == "below_target"


def test_us23_helpful_ratings_and_cue_tried_come_from_lifter_feedback(client, admin):
    lifter, _ = signup(client)
    ids = [upload_ok(client, lifter) for _ in range(4)]
    for aid, rating, tried in zip(ids, [5, 4, 4, 1], ["yes", "no", "not_yet", None]):
        _rate(client, lifter, aid, rating=rating, **({"tried_cue": tried} if tried else {}))
    shown, _ = _dashboard(client, admin)
    ratings, cue = shown["helpful_ratings"], shown["cue_tried"]
    assert (ratings["hits"], ratings["count"], ratings["status"]) == (3, 4, "on_target")    # 75%
    assert (cue["hits"], cue["count"], cue["status"]) == (1, 2, "below_target")             # 50%
    assert (ratings["basis"], cue["basis"]) == ("4 ratings", "2 answers")


def test_us23_seven_day_return_counts_lifters_whose_first_week_is_over(client, services, admin):
    back, _ = signup(client, "back@virginia.edu")
    first = upload_ok(client, back)
    second = upload_ok(client, back)
    _backdate(services, first, NOW - timedelta(days=12))
    _backdate(services, second, NOW - timedelta(days=8))
    once, _ = signup(client, "once@virginia.edu")
    _backdate(services, upload_ok(client, once), NOW - timedelta(days=10))
    new, _ = signup(client, "new@virginia.edu")
    upload_ok(client, new)                                                          # today: still waiting
    shown, body = _dashboard(client, admin)
    ret = shown["seven_day_return"]
    assert (ret["hits"], ret["count"], ret["status"], ret["basis"]) == (1, 2, "on_target", "2 lifters")
    assert body["pending_returns"] == 1


# ---- 4. [integration] date range ----

def test_us23_default_range_is_the_last_30_days(client, admin):
    _, body = _dashboard(client, admin)
    today = datetime.now(timezone.utc).date()
    assert (body["start"], body["end"]) == ((today - timedelta(days=29)).isoformat(), today.isoformat())


def test_us23_range_counts_only_analyses_created_in_it(client, services, admin):
    lifter, _ = signup(client)
    old, recent = upload_ok(client, lifter), upload_ok(client, lifter)
    _rate(client, lifter, old, rating=1)
    _rate(client, lifter, recent, rating=5)
    _backdate(services, old, datetime(2026, 10, 1, 23, 30, tzinfo=timezone.utc))
    assert _dashboard(client, admin)[0]["helpful_ratings"]["count"] == 1               # default: only the recent one
    shown, body = _dashboard(client, admin, start="2026-10-01", end="2026-10-01")
    assert (body["start"], body["end"]) == ("2026-10-01", "2026-10-01")
    assert (shown["helpful_ratings"]["hits"], shown["helpful_ratings"]["count"]) == (0, 1)
    assert _dashboard(client, admin, start="2026-10-02", end="2026-10-02")[0]["helpful_ratings"]["count"] == 0


@pytest.mark.parametrize("params", [{"start": "2026-13-01"}, {"end": "yesterday"}, {"start": "2026-11-10", "end": "2026-11-01"}])
def test_us23_invalid_or_reversed_ranges_are_rejected(client, admin, params):
    assert client.get("/admin/metrics", headers=admin, params=params).status_code == 422


# ---- 5. [integration] admins only ----

def test_us23_non_admins_get_403(client, services):
    lifter, _ = signup(client)
    trainer, _ = make_trainer(client, services)
    assert client.get("/admin/metrics", headers=lifter).status_code == 403
    assert client.get("/admin/metrics", headers=trainer).status_code == 403
    assert client.get("/admin/metrics").status_code == 401
