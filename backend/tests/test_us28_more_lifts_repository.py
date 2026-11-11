"""US-28: the database accepts the new lifts everywhere a lift is stored, and seeds their faults
(memory and Supabase Postgres; the Postgres variant runs when TEST_DATABASE_URL is set)."""
from app.faults import FAULTS
from tests.test_setup02_repository import _analysis, _user, repo  # noqa: F401  (shared memory/postgres fixture)


def test_us28_repo_stores_uploads_analyses_and_removals_of_the_new_lifts(repo):
    uid, admin = _user(repo, "a@virginia.edu"), _user(repo, "coach@virginia.edu", admin=True)
    for lift in ("overhead_press", "romanian_deadlift"):
        analysis = _analysis(repo, uid, lift=lift)
        assert repo.get_analysis(analysis).lift == lift
        upload_id = repo.get_analysis(analysis).upload_id
        entry = repo.create_moderation_entry(upload_id=upload_id, analysis_ids=[analysis], lift=lift, owner_id=uid,
                                             removed_by=admin, reason="off_topic", note=None)
        assert entry.lift == lift


def test_us28_repo_seeds_the_new_faults_after_the_existing_ones(repo):
    faults = repo.list_faults()
    assert [f.lift for f in faults][-6:] == ["overhead_press"] * 3 + ["romanian_deadlift"] * 3
    assert [f for f in faults if f.lift == "romanian_deadlift"] == list(FAULTS["romanian_deadlift"])
    assert [f for f in faults if f.lift == "overhead_press"] == list(FAULTS["overhead_press"])
