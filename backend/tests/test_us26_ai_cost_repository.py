"""US-26 criterion 1 and 4: usage is saved with each attempt and read back by date range (memory and Postgres).

The Postgres variant runs when TEST_DATABASE_URL is set (it wipes that database's public, auth and storage schemas).
"""
from datetime import datetime, timedelta, timezone

from tests.test_setup02_repository import _analysis, _user, repo  # noqa: F401  (shared memory/postgres fixture)


def test_us26_repo_saves_provider_and_model_with_each_attempt(repo):
    analysis = _analysis(repo, _user(repo))
    repo.save_llm_attempt(analysis, 1, "not JSON", 2104, 312, [], provider="claude", model="claude-sonnet-5-5")
    repo.save_llm_attempt(analysis, 2, "{}", 1990, 600, [], provider="gemini", model="gemini-2.5-flash")
    repo.save_llm_attempt(analysis, 3, "", 0, 0, [])
    saved = repo.list_llm_attempts(analysis)
    assert [(a.provider, a.model, a.input_tokens, a.output_tokens) for a in saved] == [
        ("claude", "claude-sonnet-5-5", 2104, 312), ("gemini", "gemini-2.5-flash", 1990, 600), (None, None, 0, 0)]


def test_us26_repo_lists_attempt_usage_for_analyses_created_in_a_range(repo):
    uid = _user(repo)
    inside, other = _analysis(repo, uid), _analysis(repo, uid)
    repo.save_llm_attempt(inside, 1, "", 100, 10, [], provider="claude", model="claude-sonnet-5-5")
    repo.save_llm_attempt(inside, 2, "", 200, 20, [], provider="claude", model="claude-sonnet-5-5")
    repo.save_llm_attempt(other, 1, "", 300, 30, [], provider="openai", model="gpt-4.1-mini")
    now = datetime.now(timezone.utc)
    rows = repo.list_attempt_usage(now - timedelta(hours=1), now + timedelta(hours=1))
    assert sorted((r.analysis_id, r.attempt_number, r.input_tokens, r.output_tokens, r.model) for r in rows) == sorted([
        (inside, 1, 100, 10, "claude-sonnet-5-5"), (inside, 2, 200, 20, "claude-sonnet-5-5"),
        (other, 1, 300, 30, "gpt-4.1-mini")])
    assert all(r.analysis_created_at is not None for r in rows)
    assert repo.list_attempt_usage(now + timedelta(hours=1), now + timedelta(hours=2)) == []
