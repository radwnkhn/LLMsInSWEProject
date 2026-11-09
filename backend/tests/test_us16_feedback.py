"""US-16: Rate the feedback and say if I tried the cue. (Form UI: frontend/src/components/__tests__/us16-*.test.tsx.)"""
import pytest

from app.feedback import find_previous_cue_prompt
from tests.helpers import signup, upload_ok


def _post(client, headers, analysis_id, **body):
    return client.post(f"/analyses/{analysis_id}/feedback", headers=headers, json=body)


# ---- [integration] answers saved with the analysis and user; resubmitting replaces ----

def test_us16_answers_saved_with_analysis_and_user(client, services):
    headers, user_id = signup(client)
    analysis_id = upload_ok(client, headers)
    r = _post(client, headers, analysis_id, rating=4, tried_cue="yes")
    assert r.status_code == 200
    saved = services.repo.get_feedback(analysis_id, user_id)
    assert (saved.analysis_id, saved.user_id, saved.rating, saved.tried_cue) == (analysis_id, user_id, 4, "yes")


def test_us16_resubmitting_replaces_the_previous_answer(client, services):
    headers, user_id = signup(client)
    analysis_id = upload_ok(client, headers)
    _post(client, headers, analysis_id, rating=4, tried_cue="not_yet")
    _post(client, headers, analysis_id, rating=2, tried_cue="no")
    saved = services.repo.get_feedback(analysis_id, user_id)
    assert (saved.rating, saved.tried_cue) == (2, "no")
    assert len(services.repo.list_feedback(analysis_id)) == 1


def test_us16_answering_only_the_cue_keeps_the_rating(client, services):
    headers, user_id = signup(client)
    analysis_id = upload_ok(client, headers)
    _post(client, headers, analysis_id, rating=5)
    _post(client, headers, analysis_id, tried_cue="yes")
    saved = services.repo.get_feedback(analysis_id, user_id)
    assert (saved.rating, saved.tried_cue) == (5, "yes")


def test_us16_saved_answer_shown_with_the_result(client):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    _post(client, headers, analysis_id, rating=3, tried_cue="yes")
    assert client.get(f"/analyses/{analysis_id}", headers=headers).json()["feedback"] == {"rating": 3, "tried_cue": "yes"}


# ---- [integration] ratings outside 1-5 are rejected with 422 ----

@pytest.mark.parametrize("rating", [0, 6, -1, 3.5, "five", None])
def test_us16_rating_outside_1_to_5_rejected(client, rating):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert _post(client, headers, analysis_id, rating=rating, tried_cue="yes").status_code == 422


@pytest.mark.parametrize("rating", [1, 5])
def test_us16_rating_bounds_accepted(client, rating):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert _post(client, headers, analysis_id, rating=rating).status_code == 200


def test_us16_tried_cue_must_be_yes_no_or_not_yet(client):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert _post(client, headers, analysis_id, tried_cue="maybe").status_code == 422


def test_us16_empty_answer_rejected(client):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert _post(client, headers, analysis_id).status_code == 422


def test_us16_cannot_answer_for_someone_elses_analysis(client):
    a, _ = signup(client, "a@virginia.edu")
    b, _ = signup(client, "b@virginia.edu")
    analysis_id = upload_ok(client, a)
    assert _post(client, b, analysis_id, rating=1).status_code == 404


# ---- [unit] new result for the same lift asks about the previous cue if unanswered ----

def test_us16_previous_cue_prompt_when_unanswered(client, services):
    headers, user_id = signup(client)
    first = upload_ok(client, headers)
    second = upload_ok(client, headers)
    prompt = find_previous_cue_prompt(services.repo, user_id, "squat", second)
    assert prompt["analysis_id"] == first
    assert prompt["cue"] == client.get(f"/analyses/{first}", headers=headers).json()["cue"]
    assert client.get(f"/analyses/{second}", headers=headers).json()["previous_cue_prompt"] == prompt


def test_us16_no_prompt_once_answered(client, services):
    headers, user_id = signup(client)
    first = upload_ok(client, headers)
    second = upload_ok(client, headers)
    _post(client, headers, first, tried_cue="yes")
    assert find_previous_cue_prompt(services.repo, user_id, "squat", second) is None


def test_us16_not_yet_means_ask_again(client, services):
    headers, user_id = signup(client)
    first = upload_ok(client, headers)
    second = upload_ok(client, headers)
    _post(client, headers, first, tried_cue="not_yet")
    assert find_previous_cue_prompt(services.repo, user_id, "squat", second)["analysis_id"] == first


def test_us16_no_prompt_for_a_different_lift(client, services):
    headers, user_id = signup(client)
    upload_ok(client, headers, lift="squat")
    deadlift = upload_ok(client, headers, lift="deadlift", filename="deadlift.mp4")
    assert find_previous_cue_prompt(services.repo, user_id, "deadlift", deadlift) is None


def test_us16_no_prompt_when_previous_result_had_no_cue(client, services):
    headers, user_id = signup(client)
    upload_ok(client, headers, filename="no_person.mp4")
    second = upload_ok(client, headers)
    assert find_previous_cue_prompt(services.repo, user_id, "squat", second) is None


def test_us16_no_prompt_on_the_first_result(client, services):
    headers, user_id = signup(client)
    first = upload_ok(client, headers)
    assert find_previous_cue_prompt(services.repo, user_id, "squat", first) is None


def test_us16_prompt_never_shows_someone_elses_cue(client, services):
    a, _ = signup(client, "a@virginia.edu")
    b, b_id = signup(client, "b@virginia.edu")
    upload_ok(client, a)
    mine = upload_ok(client, b)
    assert find_previous_cue_prompt(services.repo, b_id, "squat", mine) is None
