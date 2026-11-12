"""US-24 criteria 1 and 3: thresholds and their change log through the repository (in memory and Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
import pytest

from app.faults import FAULTS, FaultError
from tests.test_setup02_database import MIGRATIONS
from tests.test_setup02_repository import _user, repo  # noqa: F401  (shared memory/postgres fixture)
from tests.test_us25_fault_repository import reopen  # noqa: F401


def test_us24_repo_saves_a_new_threshold(repo, reopen):
    admin = _user(repo, "coach@virginia.edu", admin=True)
    saved = repo.update_fault("squat", "knee_cave", changed_by=admin, threshold=12.5)
    assert saved.threshold == 12.5
    assert reopen().get_fault("squat", "knee_cave").threshold == 12.5
    assert reopen().get_fault("squat", "hips_rise_early") == FAULTS["squat"][1]


def test_us24_repo_logs_each_threshold_change_newest_first(repo):
    admin = _user(repo, "coach@virginia.edu", admin=True)
    repo.update_fault("squat", "knee_cave", changed_by=admin, threshold=12)
    repo.update_fault("deadlift", "bar_path_drift", changed_by=admin, threshold=0.2)
    newest, oldest = repo.list_threshold_changes()
    assert (oldest.lift, oldest.fault_id, oldest.old_threshold, oldest.new_threshold) == ("squat", "knee_cave", 10, 12)
    assert (newest.lift, newest.fault_id, newest.old_threshold, newest.new_threshold) == ("deadlift", "bar_path_drift",
                                                                                         0.15, 0.2)
    assert oldest.changed_by == admin and oldest.changed_by_email == "coach@virginia.edu"
    assert oldest.changed_at is not None and newest.changed_at >= oldest.changed_at


def test_us24_repo_does_not_log_other_edits_or_unchanged_thresholds(repo):
    admin = _user(repo, "coach@virginia.edu", admin=True)
    repo.update_fault("squat", "knee_cave", changed_by=admin, name="Knees collapse", enabled=False)
    repo.update_fault("squat", "knee_cave", changed_by=admin, threshold=10)
    assert repo.list_threshold_changes() == []


def test_us24_repo_saves_and_logs_nothing_for_an_invalid_threshold(repo):
    admin = _user(repo, "coach@virginia.edu", admin=True)
    with pytest.raises(FaultError):
        repo.update_fault("squat", "knee_cave", changed_by=admin, threshold=500)
    with pytest.raises(FaultError):
        repo.update_fault("squat", "knee_cave", changed_by=admin, name="Knees collapse", threshold=float("nan"))
    fault = repo.get_fault("squat", "knee_cave")
    assert (fault.threshold, fault.name) == (10, "Knees cave inward")
    assert repo.list_threshold_changes() == []


def test_us24_repo_keeps_the_log_when_the_admin_account_is_deleted(repo):
    admin = _user(repo, "coach@virginia.edu", admin=True)
    repo.update_fault("squat", "knee_cave", changed_by=admin, threshold=12)
    repo.delete_user(admin)
    [entry] = repo.list_threshold_changes()
    assert (entry.old_threshold, entry.new_threshold) == (10, 12)
    assert entry.changed_by is None and entry.changed_by_email is None


def test_us24_migration_adds_an_admin_only_threshold_log():
    sql = "\n".join(p.read_text() for p in MIGRATIONS)
    assert "create table if not exists public.fault_threshold_changes" in sql
    assert "alter table public.fault_threshold_changes enable row level security" in sql
    assert "on public.fault_threshold_changes for select to authenticated using (public.is_admin())" in sql
