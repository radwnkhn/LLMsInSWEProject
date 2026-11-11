"""US-27: sign-up times, upload rows and the moderation log through the repository (memory and Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
from datetime import datetime, timedelta, timezone

from tests.test_setup02_repository import _analysis, _user, repo  # noqa: F401  (shared memory/postgres fixture)


def _window():
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=1), now + timedelta(hours=1)


def test_us27_repo_records_when_each_user_signed_up(repo):
    uid = _user(repo, "a@virginia.edu")
    start, end = _window()
    assert repo.get_user(uid).created_at is not None
    assert len(repo.list_signup_times(start, end)) == 1
    repo.ensure_user(uid, "a@virginia.edu")                     # signing in again keeps the sign-up time
    assert len(repo.list_signup_times(start, end)) == 1
    assert repo.list_signup_times(end, end + timedelta(hours=1)) == []


def test_us27_repo_lists_uploads_with_owner_and_latest_analysis(repo):
    uid = _user(repo, "a@virginia.edu")
    first = _analysis(repo, uid, lift="squat")
    upload_id = repo.get_analysis(first).upload_id
    retry = "00000000-0000-4000-8000-000000000001"
    repo.create_analysis(retry, upload_id, uid, "squat")
    _analysis(repo, uid, lift="deadlift")
    start, end = _window()
    rows = repo.list_upload_rows(start, end)
    assert [r.upload.lift for r in rows] == ["deadlift", "squat"]          # newest first
    squat = rows[1]
    assert squat.user_email == "a@virginia.edu" and squat.analysis.id == retry
    assert [r.upload.lift for r in repo.list_upload_rows(start, end, lift="squat")] == ["squat"]
    assert repo.list_upload_rows(end, end + timedelta(hours=1)) == []


def test_us27_repo_moderation_log_round_trip_and_lookup_by_analysis(repo):
    owner, admin = _user(repo, "a@virginia.edu"), _user(repo, "coach@virginia.edu", admin=True)
    analysis = _analysis(repo, owner)
    upload_id = repo.get_analysis(analysis).upload_id
    entry = repo.create_moderation_entry(upload_id=upload_id, analysis_ids=[analysis], lift="squat", owner_id=owner,
                                         removed_by=admin, reason="other", note="Not a lift")
    assert entry.removed_at is not None
    repo.delete_upload(upload_id)                                 # the log outlives the upload it describes
    [saved] = repo.list_moderation_entries()
    assert (saved.upload_id, saved.analysis_ids, saved.reason, saved.note) == (upload_id, [analysis], "other", "Not a lift")
    assert (saved.owner_email, saved.removed_by_email) == ("a@virginia.edu", "coach@virginia.edu")
    assert repo.get_removal_for_analysis(analysis).id == saved.id
    assert repo.get_removal_for_analysis("00000000-0000-4000-8000-000000000009") is None
    repo.delete_user(owner)
    [after] = repo.list_moderation_entries()
    assert after.owner_id is None and after.owner_email is None
    repo.delete_moderation_entry(after.id)
    assert repo.list_moderation_entries() == []
