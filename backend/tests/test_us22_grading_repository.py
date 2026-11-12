"""US-22: trainer accounts and grading assignments through the repository (in memory and Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
import uuid

from tests.test_setup02_database import MIGRATIONS
from tests.test_setup02_repository import _analysis, _user, repo  # noqa: F401  (shared memory/postgres fixture)


def _trainer(repo, email="trainer@virginia.edu"):
    uid = _user(repo, email)
    repo.ensure_user(uid, email, is_trainer=True)
    return uid


def test_us22_repo_saves_the_trainer_role_and_lists_trainers(repo):
    trainer = _trainer(repo)
    _user(repo, "lifter@virginia.edu")
    _user(repo, "coach@virginia.edu", admin=True)
    assert repo.get_user(trainer).is_trainer is True
    assert [(u.id, u.email) for u in repo.list_trainers()] == [(trainer, "trainer@virginia.edu")]
    repo.ensure_user(trainer, "trainer@virginia.edu")                    # the role was removed in Supabase
    assert repo.list_trainers() == []


def test_us22_repo_creates_and_lists_assignments_newest_first(repo):
    admin, trainer, lifter = _user(repo, "coach@virginia.edu", admin=True), _trainer(repo), _user(repo)
    first, second = _analysis(repo, lifter), _analysis(repo, lifter, lift="deadlift")
    repo.create_assignments(trainer, [first], assigned_by=admin)
    [made] = repo.create_assignments(trainer, [second], assigned_by=admin)
    assert (made.analysis_id, made.trainer_id, made.assigned_by) == (second, trainer, admin)
    assert made.assigned_at is not None and made.answered_at is None and made.verdict is None
    newest, oldest = repo.list_assignments()
    assert (newest.analysis_id, oldest.analysis_id) == (second, first)
    assert newest.trainer_email == "trainer@virginia.edu"
    assert [a.analysis_id for a in repo.list_assignments(trainer_id=trainer)] == [second, first]
    assert repo.list_assignments(trainer_id=admin) == []
    assert repo.get_assignment(made.id).analysis_id == second
    assert repo.get_assignment(str(uuid.uuid4())) is None
    assert repo.get_assignment("not-a-uuid") is None


def test_us22_repo_records_the_trainers_answer_once(repo):
    trainer, lifter = _trainer(repo), _user(repo)
    [a] = repo.create_assignments(trainer, [_analysis(repo, lifter)], assigned_by=None)
    saved = repo.save_trainer_answer(a.id, "knee_cave")
    assert (saved.trainer_fault_id, saved.answered_at is not None) == ("knee_cave", True)
    assert repo.save_trainer_answer(a.id, "hips_rise_early") is None     # already answered: unchanged
    assert repo.get_assignment(a.id).trainer_fault_id == "knee_cave"
    [b] = repo.create_assignments(trainer, [_analysis(repo, lifter)], assigned_by=None)
    none = repo.save_trainer_answer(b.id, None)                            # "No major issue"
    assert none.trainer_fault_id is None and none.answered_at is not None


def test_us22_repo_saves_a_verdict_only_after_an_answer(repo):
    trainer, lifter = _trainer(repo), _user(repo)
    [a] = repo.create_assignments(trainer, [_analysis(repo, lifter)], assigned_by=None)
    assert repo.save_verdict(a.id, "correct") is None
    repo.save_trainer_answer(a.id, "knee_cave")
    graded = repo.save_verdict(a.id, "partly_correct")
    assert (graded.verdict, graded.graded_at is not None) == ("partly_correct", True)
    assert repo.get_assignment(a.id).verdict == "partly_correct"


def test_us22_repo_deleting_an_upload_or_the_trainer_removes_assignments(repo):
    admin, trainer, lifter = _user(repo, "coach@virginia.edu", admin=True), _trainer(repo), _user(repo)
    first, second = _analysis(repo, lifter), _analysis(repo, lifter)
    repo.create_assignments(trainer, [first, second], assigned_by=admin)
    repo.delete_upload(repo.get_analysis(first).upload_id)
    assert [a.analysis_id for a in repo.list_assignments()] == [second]
    repo.delete_user(admin)                                               # who assigned it is forgotten, not the work
    assert repo.list_assignments()[0].assigned_by is None
    repo.delete_user(trainer)
    assert repo.list_assignments() == []


def test_us22_migration_adds_trainers_and_admin_or_trainer_only_assignments():
    sql = "\n".join(p.read_text() for p in MIGRATIONS)
    assert "add column if not exists is_trainer boolean not null default false" in sql
    assert "create table if not exists public.grading_assignments" in sql
    assert "alter table public.grading_assignments enable row level security" in sql
    assert "using (trainer_id = auth.uid() or public.is_admin())" in sql
