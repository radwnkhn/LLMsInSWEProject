"""US-25 criterion 6: fault changes persist through the repository (in memory and Supabase Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
from dataclasses import replace

import pytest

from app import faults
from app.faults import FAULTS
from tests.test_setup02_database import MIGRATIONS
from tests.test_setup02_repository import PG_URL, repo  # noqa: F401  (shared memory/postgres fixture)

ALPHA_FAULTS = [f for lift in ("squat", "deadlift", "bench_press") for f in FAULTS[lift]]


@pytest.fixture
def reopen(repo):
    """A second connection to the same store, to show changes were saved rather than cached."""
    opened = []

    def second_connection():
        if not hasattr(repo, "pool"):
            return repo
        from app.repository import PostgresRepository

        opened.append(PostgresRepository(PG_URL))
        return opened[-1]

    yield second_connection
    for other in opened:
        other.pool.close()


def test_us25_repo_starts_with_the_alpha_fault_definitions(repo):
    assert repo.list_faults() == ALPHA_FAULTS
    assert repo.get_fault("squat", "knee_cave") == FAULTS["squat"][0]
    assert repo.get_fault("squat", "elbow_flare") is None


def test_us25_repo_saves_edits_and_enabled_state(repo, reopen):
    edited = repo.update_fault("deadlift", "rounded_back", name="Back rounds off the floor", short_name="back rounding",
                               enabled=False)
    assert (edited.name, edited.short_name, edited.enabled) == ("Back rounds off the floor", "back rounding", False)
    saved = reopen().get_fault("deadlift", "rounded_back")
    assert saved == replace(FAULTS["deadlift"][0], name="Back rounds off the floor", short_name="back rounding",
                            enabled=False)
    repo.update_fault("deadlift", "rounded_back", enabled=True)
    assert reopen().get_fault("deadlift", "rounded_back").enabled is True


def test_us25_repo_update_accepts_only_editable_fields(repo):
    with pytest.raises(ValueError):
        repo.update_fault("squat", "knee_cave", threshold=3)
    with pytest.raises(KeyError):
        repo.update_fault("squat", "no_such_fault", name="x")
    assert repo.get_fault("squat", "knee_cave").threshold == 10


def test_us25_repo_saves_new_faults_after_the_lifts_existing_ones(repo, reopen):
    fault = faults.new_fault(lift="bench_press", id="shallow_touch", name="Bar stops above your chest", short_name="short touch",
                      category="technique", metric="elbow_angle_min_deg", threshold=100, direction="above")
    repo.create_fault(fault)
    bench = [f for f in reopen().list_faults() if f.lift == "bench_press"]
    assert bench == [*FAULTS["bench_press"], fault]
    with pytest.raises(faults.FaultExists):
        repo.create_fault(fault)


def test_us25_migration_seeds_every_alpha_fault():
    sql = "\n".join(p.read_text() for p in MIGRATIONS)
    assert "create table if not exists public.faults" in sql
    assert "alter table public.faults enable row level security" in sql
    for fault in ALPHA_FAULTS:
        assert f"'{fault.lift}', '{fault.id}'" in sql, fault.id
