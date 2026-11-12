"""US-22: Blind trainer grading. (UI: frontend/src/components/__tests__/us22-grading.test.tsx.)

Acceptance criteria (#24):
1. [unit] [integration] [e2e] An admin assigns a random sample of N analyses (1 to 50) to a trainer, optionally for one
   lift. Only finished analyses with validated feedback are sampled, never one the trainer already has or their own.
   Fewer available: all are assigned; none: the admin is told.
2. [integration] [e2e] The trainer records their own top fault (or "No major issue") before our feedback is shown,
   then marks ours correct, partly correct or wrong. Their own answer can't change once ours has been shown.
3. [integration] [e2e] Trainer pages and endpoints never include the lifter's email, note or file name.
4. [integration] [e2e] The admin grading list shows trainer, status, the trainer's top fault, ours and the grade.
5. [integration] Trainer endpoints are for trainers and their own assignments only (another trainer's: 404).
   Non-admins get 403 on assigning, the trainer list and the admin grading list.

In-memory repository, storage and auth only; no Supabase calls. The default synthetic squat's validated feedback
has "Hips rise before your shoulders" as the top fix.
"""
import importlib
import json
import random

import pytest

from app.testing.fakes import FailingLLM
from tests.helpers import make_admin, make_trainer, signup, upload_ok

HIPS = "hips_rise_early"
LIFTER_EMAIL = "lifter@virginia.edu"


@pytest.fixture
def grading():
    """app.grading, imported per test so each test reports its own failure before the module exists."""
    return importlib.import_module("app.grading")


@pytest.fixture
def admin(client, services):
    headers, _ = make_admin(client, services)
    return headers


@pytest.fixture
def trainer(client, services):
    return make_trainer(client, services, "trainer@virginia.edu")


@pytest.fixture
def lifter(client):
    headers, _ = signup(client, LIFTER_EMAIL)
    return headers


def _assign(client, admin, trainer_id, count=1, **extra):
    return client.post("/admin/grading/assignments", headers=admin, json={"trainer_id": trainer_id, "count": count, **extra})


def _assigned(client, admin, trainer_id, count=1, **extra):
    r = _assign(client, admin, trainer_id, count, **extra)
    assert r.status_code == 201, r.text
    return r.json()


def _mine(client, trainer_headers):
    r = client.get("/trainer/assignments", headers=trainer_headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _open(client, trainer_headers, assignment_id):
    return client.get(f"/trainer/assignments/{assignment_id}", headers=trainer_headers)


def _answer(client, trainer_headers, assignment_id, fault_id):
    return client.post(f"/trainer/assignments/{assignment_id}/answer", headers=trainer_headers, json={"fault_id": fault_id})


def _grade(client, trainer_headers, assignment_id, verdict):
    return client.post(f"/trainer/assignments/{assignment_id}/verdict", headers=trainer_headers, json={"verdict": verdict})


def _one_assignment(client, admin, trainer, lifter):
    upload_ok(client, lifter)
    _assigned(client, admin, trainer[1])
    [item] = _mine(client, trainer[0])
    return item["assignment_id"]


# ---- 1. [unit] sampling rules ----

def _analysis(id, user="lifter", status="done", final="passed_first_try", lift="squat"):
    from app.repository import AnalysisRecord

    return AnalysisRecord(id=id, upload_id=f"u-{id}", user_id=user, lift=lift, status=status, final_status=final)


def test_us22_unit_only_finished_validated_analyses_are_eligible(grading):
    analyses = [_analysis("a"), _analysis("b", final="passed_after_retry"), _analysis("c", final="fallback"),
                _analysis("d", final="unanalyzable"), _analysis("e", status="processing", final=None),
                _analysis("f", status="failed", final=None)]
    assert [a.id for a in grading.eligible_for_grading(analyses, trainer_id="t", already_assigned=set())] == ["a", "b"]


def test_us22_unit_eligibility_skips_already_assigned_own_and_other_lifts(grading):
    analyses = [_analysis("a"), _analysis("b"), _analysis("c", user="t"), _analysis("d", lift="deadlift")]
    eligible = grading.eligible_for_grading(analyses, trainer_id="t", already_assigned={"b"})
    assert [a.id for a in eligible] == ["a", "d"]
    assert [a.id for a in grading.eligible_for_grading(analyses, "t", set(), lift="deadlift")] == ["d"]


def test_us22_unit_sample_is_random_distinct_and_capped(grading):
    pool = [_analysis(str(i)) for i in range(20)]
    first = grading.sample_for_grading(pool, 5, random.Random(1))
    second = grading.sample_for_grading(pool, 5, random.Random(2))
    assert len(first) == 5 and len({a.id for a in first}) == 5
    assert {a.id for a in first} != {a.id for a in second}
    assert grading.sample_for_grading(pool, 5, random.Random(1)) == first     # seeded: repeatable
    assert len(grading.sample_for_grading(pool[:3], 5, random.Random(1))) == 3
    assert grading.sample_for_grading([], 5, random.Random(1)) == []


def test_us22_unit_verdicts_are_correct_partly_correct_or_wrong(grading):
    assert grading.VERDICTS == {"correct": "Correct", "partly_correct": "Partly correct", "wrong": "Wrong"}


# ---- 1. [integration] assigning a sample ----

def test_us22_admin_lists_trainer_accounts(client, admin, trainer):
    signup(client, "someone@virginia.edu")
    r = client.get("/admin/trainers", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [{"id": trainer[1], "email": "trainer@virginia.edu"}]


def test_us22_admin_assigns_a_sample_of_n_analyses(client, admin, trainer, lifter):
    for _ in range(5):
        upload_ok(client, lifter)
    body = _assigned(client, admin, trainer[1], count=3)
    assert (body["requested"], body["assigned"]) == (3, 3)
    assert len(_mine(client, trainer[0])) == 3
    assert len({i["analysis_id"] for i in body["items"]}) == 3


def test_us22_repeat_assignments_never_repeat_an_analysis(client, admin, trainer, lifter):
    for _ in range(4):
        upload_ok(client, lifter)
    first = {i["analysis_id"] for i in _assigned(client, admin, trainer[1], count=2)["items"]}
    second = {i["analysis_id"] for i in _assigned(client, admin, trainer[1], count=5)["items"]}
    assert len(first) == 2 and len(second) == 2 and not first & second


def test_us22_fewer_available_assigns_all_and_none_available_is_explained(client, admin, trainer, lifter):
    upload_ok(client, lifter)
    upload_ok(client, lifter)
    body = _assigned(client, admin, trainer[1], count=10)
    assert (body["requested"], body["assigned"]) == (10, 2)
    r = _assign(client, admin, trainer[1], count=1)
    assert r.status_code == 409
    assert "No analyses are left to assign" in r.json()["detail"]


def test_us22_fallback_and_unanalyzable_analyses_are_never_sampled(client, services, admin, trainer, lifter):
    upload_ok(client, lifter, filename="no_person.mp4")             # unanalyzable
    services.llm = FailingLLM()
    upload_ok(client, lifter)                                        # fallback: no AI feedback
    r = _assign(client, admin, trainer[1], count=5)
    assert r.status_code == 409


def test_us22_sample_can_be_limited_to_one_lift(client, admin, trainer, lifter):
    upload_ok(client, lifter)
    upload_ok(client, lifter, filename="deadlift.mp4", lift="deadlift")
    body = _assigned(client, admin, trainer[1], count=5, lift="deadlift")
    assert [i["lift"] for i in body["items"]] == ["deadlift"]


@pytest.mark.parametrize("count", [0, 51, -1, 2.5, "3", None])
def test_us22_count_must_be_1_to_50(client, admin, trainer, lifter, count):
    upload_ok(client, lifter)
    assert _assign(client, admin, trainer[1], count=count).status_code == 422
    assert _mine(client, trainer[0]) == []


def test_us22_only_trainer_accounts_can_be_assigned(client, admin, lifter):
    _, someone = signup(client, "someone@virginia.edu")
    upload_ok(client, lifter)
    assert _assign(client, admin, someone).status_code == 422
    assert _assign(client, admin, "00000000-0000-4000-8000-000000000000").status_code == 422
    assert _assign(client, admin, someone, lift="curl").status_code == 422


# ---- 2. [integration] blind first, then grade ----

def test_us22_trainer_sees_the_video_but_not_our_feedback_before_answering(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    r = _open(client, trainer[0], aid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["video_url"] and body["lift"] == "squat" and body["status"] == "waiting"
    assert body["our_feedback"] is None and body["trainer_answer"] is None
    text = json.dumps({k: v for k, v in body.items() if k != "fault_options"})   # options list every fault by design
    for hidden in ("top_fix", "cue", "explanation", "other_faults", "rep_count", "Hips rise", HIPS):
        assert hidden not in text, hidden


def test_us22_fault_options_are_the_lifts_enabled_faults_plus_no_major_issue(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    options = _open(client, trainer[0], aid).json()["fault_options"]
    assert [o["fault_id"] for o in options] == ["knee_cave", HIPS, "insufficient_depth", "excessive_forward_lean",
                                                "bar_path_drift", None]
    assert options[-1]["name"] == "No major issue"


def test_us22_answering_reveals_our_feedback(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    r = _answer(client, trainer[0], aid, "excessive_forward_lean")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "answered"
    assert body["trainer_answer"] == {"fault_id": "excessive_forward_lean", "name": "Chest drops too far forward"}
    ours = body["our_feedback"]
    assert ours["top_fix"]["fault_id"] == HIPS and ours["top_fix"]["title"] == "Hips rise before your shoulders"
    assert ours["cue"] and ours["explanation"] is not None
    assert _open(client, trainer[0], aid).json()["our_feedback"] == ours


def test_us22_trainer_can_answer_no_major_issue(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    body = _answer(client, trainer[0], aid, None).json()
    assert body["trainer_answer"] == {"fault_id": None, "name": "No major issue"}
    assert body["our_feedback"] is not None


def test_us22_answer_must_be_one_of_the_lifts_faults(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    for bad in ["elbow_flare", "made_up", 7]:
        assert _answer(client, trainer[0], aid, bad).status_code == 422
    assert client.post(f"/trainer/assignments/{aid}/answer", headers=trainer[0], json={}).status_code == 422
    assert _open(client, trainer[0], aid).json()["our_feedback"] is None


def test_us22_answer_cant_change_once_our_feedback_is_shown(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    _answer(client, trainer[0], aid, "knee_cave")
    r = _answer(client, trainer[0], aid, HIPS)
    assert r.status_code == 409
    assert _open(client, trainer[0], aid).json()["trainer_answer"]["fault_id"] == "knee_cave"


def test_us22_grading_needs_the_trainers_own_answer_first(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    r = _grade(client, trainer[0], aid, "correct")
    assert r.status_code == 409
    assert "own top fault first" in r.json()["detail"]


@pytest.mark.parametrize("verdict,label", [("correct", "Correct"), ("partly_correct", "Partly correct"), ("wrong", "Wrong")])
def test_us22_trainer_marks_our_feedback(client, admin, trainer, lifter, verdict, label):
    aid = _one_assignment(client, admin, trainer, lifter)
    _answer(client, trainer[0], aid, HIPS)
    r = _grade(client, trainer[0], aid, verdict)
    assert r.status_code == 200, r.text
    assert (r.json()["verdict"], r.json()["verdict_label"], r.json()["status"]) == (verdict, label, "graded")
    assert _mine(client, trainer[0])[0]["status"] == "graded"


def test_us22_invalid_verdicts_are_rejected(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    _answer(client, trainer[0], aid, HIPS)
    for bad in ["right", "", None, 1]:
        assert _grade(client, trainer[0], aid, bad).status_code == 422
    assert _open(client, trainer[0], aid).json()["verdict"] is None


def test_us22_no_major_issues_feedback_can_be_graded(client, admin, trainer, lifter):
    upload_ok(client, lifter, filename="clean.mp4")
    _assigned(client, admin, trainer[1])
    [item] = _mine(client, trainer[0])
    ours = _answer(client, trainer[0], item["assignment_id"], None).json()["our_feedback"]
    assert ours["top_fix"] is None and ours["no_major_issues"] is True
    assert _grade(client, trainer[0], item["assignment_id"], "correct").status_code == 200


def test_us22_trainer_list_shows_lift_and_status_newest_first(client, admin, trainer, lifter):
    upload_ok(client, lifter)
    _assigned(client, admin, trainer[1])
    upload_ok(client, lifter, filename="bench.mp4", lift="bench_press")
    _assigned(client, admin, trainer[1], lift="bench_press")
    items = _mine(client, trainer[0])
    assert [(i["lift"], i["lift_label"], i["status"], i["status_label"]) for i in items] == [
        ("bench_press", "Bench Press", "waiting", "To grade"), ("squat", "Squat", "waiting", "To grade")]


# ---- 3. [integration] no names or emails ----

def test_us22_trainer_responses_never_include_the_lifters_email_note_or_file_name(client, admin, trainer):
    lifter, lifter_id = signup(client, "jordan.smith@virginia.edu")
    upload_ok(client, lifter, filename="jordan_smith_squat.mp4", note="Jordan here, my knees felt odd")
    _assigned(client, admin, trainer[1])
    [item] = _mine(client, trainer[0])
    aid = item["assignment_id"]
    bodies = [client.get("/trainer/assignments", headers=trainer[0]).json(), _open(client, trainer[0], aid).json(),
              _answer(client, trainer[0], aid, HIPS).json(), _grade(client, trainer[0], aid, "wrong").json()]
    for body in bodies:
        assert "video_url" not in body or body.pop("video_url").count("jordan") == 0   # a storage path, no names
        text = json.dumps(body)
        for private in ("jordan", "Jordan", "virginia.edu", "knees felt odd", "user_email", "note", "filename", lifter_id):
            assert private not in text, (private, text)


def test_us22_trainers_cant_open_the_lifters_results_or_admin_pages(client, admin, trainer, lifter):
    upload_ok(client, lifter)
    body = _assigned(client, admin, trainer[1])
    analysis_id = body["items"][0]["analysis_id"]
    assert client.get(f"/analyses/{analysis_id}", headers=trainer[0]).status_code == 404
    assert client.get(f"/admin/analyses/{analysis_id}", headers=trainer[0]).status_code == 403
    assert client.get("/admin/grading/assignments", headers=trainer[0]).status_code == 403


# ---- 4. [integration] the admin's view of every assignment ----

def test_us22_admin_list_shows_trainer_status_both_faults_and_grade(client, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    [waiting] = client.get("/admin/grading/assignments", headers=admin).json()["items"]
    assert (waiting["trainer_email"], waiting["status"], waiting["status_label"]) == ("trainer@virginia.edu", "waiting", "To grade")
    assert waiting["trainer_answer"] is None and waiting["verdict"] is None
    assert waiting["our_fault"] == {"fault_id": HIPS, "name": "Hips rise before your shoulders"}
    _answer(client, trainer[0], aid, "excessive_forward_lean")
    _grade(client, trainer[0], aid, "partly_correct")
    r = client.get("/admin/grading/assignments", headers=admin)
    assert r.status_code == 200, r.text
    [graded] = r.json()["items"]
    assert graded["trainer_answer"] == {"fault_id": "excessive_forward_lean", "name": "Chest drops too far forward"}
    assert (graded["verdict"], graded["verdict_label"], graded["status_label"]) == ("partly_correct", "Partly correct", "Graded")
    assert graded["lift_label"] == "Squat" and graded["assigned_at"] and graded["graded_at"]


def test_us22_admin_list_shows_no_major_issue_for_clean_feedback(client, admin, trainer, lifter):
    upload_ok(client, lifter, filename="clean.mp4")
    _assigned(client, admin, trainer[1])
    [row] = client.get("/admin/grading/assignments", headers=admin).json()["items"]
    assert row["our_fault"] == {"fault_id": None, "name": "No major issue"}


def test_us22_deleting_an_upload_removes_its_assignments(client, services, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    upload_id = next(iter(services.repo.uploads))
    assert client.request("DELETE", f"/uploads/{upload_id}", headers=lifter, json={"confirmed": True}).status_code == 204
    assert _mine(client, trainer[0]) == []
    assert _open(client, trainer[0], aid).status_code == 404
    assert client.get("/admin/grading/assignments", headers=admin).json()["items"] == []


# ---- 5. [integration] who can do what ----

def test_us22_another_trainers_assignment_is_not_found(client, services, admin, trainer, lifter):
    aid = _one_assignment(client, admin, trainer, lifter)
    other, _ = make_trainer(client, services, "other.trainer@virginia.edu")
    assert _open(client, other, aid).status_code == 404
    assert _answer(client, other, aid, HIPS).status_code == 404
    assert _grade(client, other, aid, "correct").status_code == 404
    assert _mine(client, other) == []


@pytest.mark.parametrize("who", ["lifter", "admin"])
def test_us22_non_trainers_get_403_on_trainer_endpoints(client, admin, trainer, lifter, who):
    aid = _one_assignment(client, admin, trainer, lifter)
    headers = lifter if who == "lifter" else admin
    assert client.get("/trainer/assignments", headers=headers).status_code == 403
    assert _open(client, headers, aid).status_code == 403
    assert _answer(client, headers, aid, HIPS).status_code == 403
    assert _grade(client, headers, aid, "correct").status_code == 403


def test_us22_non_admins_get_403_on_admin_grading_endpoints(client, trainer, lifter):
    upload_ok(client, lifter)
    for headers in (lifter, trainer[0]):
        assert client.get("/admin/trainers", headers=headers).status_code == 403
        assert client.get("/admin/grading/assignments", headers=headers).status_code == 403
        assert _assign(client, headers, trainer[1]).status_code == 403


def test_us22_signed_out_requests_get_401(client):
    for path in ("/trainer/assignments", "/admin/trainers", "/admin/grading/assignments"):
        assert client.get(path).status_code == 401
    assert client.post("/admin/grading/assignments", json={"trainer_id": "x", "count": 1}).status_code == 401


def test_us22_auth_me_says_who_is_a_trainer(client, trainer, lifter):
    assert client.get("/auth/me", headers=trainer[0]).json()["is_trainer"] is True
    assert client.get("/auth/me", headers=lifter).json()["is_trainer"] is False


def test_us22_supabase_role_trainer_marks_a_trainer():
    from app.auth import SupabaseAuth

    user = SupabaseAuth._user({"id": "u1", "email": "t@virginia.edu", "app_metadata": {"role": "trainer"}})
    assert (user.is_trainer, user.is_admin) == (True, False)
    assert SupabaseAuth._user({"id": "u2", "email": "a@virginia.edu", "app_metadata": {"role": "admin"}}).is_trainer is False


def test_us22_test_mode_makes_trainer_test_sign_ups_trainers():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services import services_from_env

    with TestClient(create_app(services_from_env({"ALIBI_TEST_MODE": "1"}))) as c:
        r = c.post("/auth/signup", json={"email": "coach@trainer.test", "password": "squat1234"})
        assert r.status_code == 201 and r.json()["user"]["is_trainer"] is True
        r = c.post("/auth/signup", json={"email": "lifter@virginia.edu", "password": "squat1234"})
        assert r.json()["user"]["is_trainer"] is False
