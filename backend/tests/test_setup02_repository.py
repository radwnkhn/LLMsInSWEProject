"""SETUP-02: the same repository contract for the in-memory store and Supabase Postgres.

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
import os
import uuid

import pytest

from app.llm.schema import ValidationIssue
from app.measure import RepMeasurement
from app.repository import InMemoryRepository
from tests.test_setup02_database import MIGRATIONS, STUB

PG_URL = os.environ.get("TEST_DATABASE_URL")


def _postgres():
    import psycopg

    from app.repository import PostgresRepository

    with psycopg.connect(PG_URL, autocommit=True) as conn:
        conn.execute("drop schema if exists public cascade; drop schema if exists auth cascade; "
                     "drop schema if exists storage cascade; create schema public;")
        conn.execute(STUB.read_text())
        for path in MIGRATIONS:
            conn.execute(path.read_text())
    return PostgresRepository(PG_URL)


@pytest.fixture(params=["memory", "postgres"])
def repo(request):
    if request.param == "memory":
        return InMemoryRepository()
    if not PG_URL:
        pytest.skip("set TEST_DATABASE_URL to run the Postgres repository tests")
    return _postgres()


def _user(repo, email="a@virginia.edu", admin=False):
    uid = str(uuid.uuid4())
    if hasattr(repo, "pool"):  # Postgres: profiles hang off Supabase auth.users
        with repo.pool.connection() as conn:
            conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, email))
    repo.ensure_user(uid, email, admin)
    return uid


def _analysis(repo, user_id, lift="squat"):
    up, an = str(uuid.uuid4()), str(uuid.uuid4())
    repo.create_upload(up, user_id, lift, f"{user_id}/{up}.mp4", "set.mp4", None)
    repo.create_analysis(an, up, user_id, lift)
    return an


def test_setup02_repo_uploads_and_analyses_round_trip(repo):
    uid = _user(repo)
    up = str(uuid.uuid4())
    saved = repo.create_upload(up, uid, "deadlift", f"{uid}/{up}.mov", "IMG_1.MOV", "felt slow")
    assert repo.get_upload(up).note == "felt slow" and saved.created_at is not None
    an = str(uuid.uuid4())
    repo.create_analysis(an, up, uid, "deadlift")
    assert repo.get_analysis(an).status == "queued"
    repo.update_analysis(an, status="done", final_status="fallback", rep_count=3, result={"top_fix": None, "cue": None})
    a = repo.get_analysis(an)
    assert (a.status, a.final_status, a.rep_count, a.result) == ("done", "fallback", 3, {"top_fix": None, "cue": None})
    assert repo.get_analysis(str(uuid.uuid4())) is None
    assert repo.get_analysis("not-a-uuid") is None


def test_setup02_repo_rejects_unknown_analysis_fields(repo):
    uid = _user(repo)
    with pytest.raises(ValueError):
        repo.update_analysis(_analysis(repo, uid), user_id="someone-else")


def test_us19_repo_persists_processing_stage_without_changing_job_status_contract(repo):
    an = _analysis(repo, _user(repo))
    assert getattr(repo.get_analysis(an), "processing_stage", "missing") is None
    for stage in ("measuring", "writing_feedback", "checking"):
        repo.update_analysis(an, status="processing", processing_stage=stage)
        saved = repo.get_analysis(an)
        assert saved.status == "processing" and saved.processing_stage == stage
    repo.update_analysis(an, status="done", processing_stage=None)
    assert repo.get_analysis(an).processing_stage is None


def test_setup02_repo_lists_a_users_analyses_newest_first(repo):
    a, b = _user(repo), _user(repo, "b@virginia.edu")
    first, other, second = _analysis(repo, a), _analysis(repo, b), _analysis(repo, a, "bench_press")
    assert [x.id for x in repo.list_analyses_for_user(a)] == [second, first]
    assert [x.id for x in repo.list_analyses_for_user(a, lift="squat")] == [first]


def test_setup02_repo_rep_measurements(repo):
    an = _analysis(repo, _user(repo))
    reps = [RepMeasurement(rep=i, start_frame=i * 10, turn_frame=i * 10 + 5, end_frame=i * 10 + 9, start_time=i / 3,
                           end_time=i / 3 + 0.3, metrics={"knee_angle_min_deg": 45.0 + i, "knee_valgus_deg": None},
                           worst_frames={"knee_angle_min_deg": i * 10 + 5}, depth_reached=True) for i in (1, 2)]
    repo.save_rep_measurements(an, reps)
    loaded = repo.list_rep_measurements(an)
    assert [r.to_dict() for r in loaded] == [r.to_dict() for r in reps]


def test_setup02_repo_llm_attempts_and_validation_results(repo):
    an = _analysis(repo, _user(repo))
    repo.save_llm_attempt(an, 1, "bad", 100, 20, [ValidationIssue("rep_count", "feedback says 6 reps but 5 were detected")])
    repo.save_llm_attempt(an, 2, "{}", 120, 30, [])
    attempts = repo.list_llm_attempts(an)
    assert [(a.attempt_number, a.passed, a.input_tokens) for a in attempts] == [(1, False, 100), (2, True, 120)]
    assert attempts[0].issues == [ValidationIssue("rep_count", "feedback says 6 reps but 5 were detected")]
    assert [i.code for i in repo.all_validation_issues()] == ["rep_count"]


def test_setup02_repo_feedback_upsert_keeps_one_row(repo):
    uid = _user(repo)
    an = _analysis(repo, uid)
    repo.upsert_feedback(an, uid, 4, None)
    repo.upsert_feedback(an, uid, None, "yes")
    repo.upsert_feedback(an, uid, 2, None)
    fb = repo.get_feedback(an, uid)
    assert (fb.rating, fb.tried_cue) == (2, "yes")
    assert len(repo.list_feedback(an)) == 1


def test_setup02_repo_admin_rows(repo):
    a = _user(repo, "a@virginia.edu")
    an = _analysis(repo, a)
    repo.update_analysis(an, status="done", final_status="passed_after_retry")
    repo.save_llm_attempt(an, 1, "x", 1, 1, [ValidationIssue("invalid_json", "x")])
    repo.save_llm_attempt(an, 2, "y", 1, 1, [])
    _analysis(repo, a, "deadlift")
    rows = repo.list_admin_rows()
    assert [r.analysis.lift for r in rows] == ["deadlift", "squat"]
    assert rows[1].attempt_count == 2 and rows[1].user_email == "a@virginia.edu"
    assert [r.analysis.id for r in repo.list_admin_rows(final_status="passed_after_retry")] == [an]
    assert repo.get_user(a).email == "a@virginia.edu"
