"""US-23: the data points behind the metrics, through the repository (in memory and Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
from datetime import datetime, timedelta, timezone

from tests.test_setup02_repository import _analysis, _user, repo  # noqa: F401  (shared memory/postgres fixture)
from tests.test_us22_grading_repository import _trainer


def _window():
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=1), now + timedelta(hours=1)


def test_us23_repo_lists_feedback_for_analyses_created_in_a_range(repo):
    lifter = _user(repo)
    rated, asked = _analysis(repo, lifter), _analysis(repo, lifter)
    repo.upsert_feedback(rated, lifter, 5, None)
    repo.upsert_feedback(asked, lifter, None, "yes")
    start, end = _window()
    assert {(f.rating, f.tried_cue) for f in repo.list_feedback_between(start, end)} == {(5, None), (None, "yes")}
    assert repo.list_feedback_between(end, end + timedelta(hours=1)) == []


def test_us23_repo_lists_verdicts_of_graded_assignments_in_a_range(repo):
    trainer, lifter = _trainer(repo), _user(repo)
    graded, answered, waiting = (_analysis(repo, lifter) for _ in range(3))
    a, b, _c = repo.create_assignments(trainer, [graded, answered, waiting], assigned_by=None)
    repo.save_trainer_answer(a.id, "knee_cave")
    repo.save_verdict(a.id, "wrong")
    repo.save_trainer_answer(b.id, None)
    start, end = _window()
    assert repo.list_graded_verdicts(start, end) == ["wrong"]
    assert repo.list_graded_verdicts(end, end + timedelta(hours=1)) == []


def test_us23_repo_lists_every_upload_time_by_user(repo):
    one, two = _user(repo, "one@virginia.edu"), _user(repo, "two@virginia.edu")
    _analysis(repo, one)
    _analysis(repo, one)
    _analysis(repo, two)
    times = repo.list_upload_times()
    assert sorted(uid for uid, _ in times) == sorted([one, one, two])
    assert all(when.tzinfo is not None for _, when in times)
