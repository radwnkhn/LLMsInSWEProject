"""US-15: Recommend a professional if I mention pain. (Note field UI: frontend/src/components/__tests__/us15-*.test.tsx.)"""
import numpy as np
import pytest

from app.pipeline import analyze_set
from app.results import PROFESSIONAL_MESSAGE, build_result_view
from app.safety import MAX_NOTE_LENGTH, find_medical_language, mentions_pain
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import squat
from app.validator import validate
from tests.helpers import coach_output, context_for, signup, upload, upload_ok

REFERRAL = "Please see a doctor or physical therapist about the pain before training through it."


# ---- [unit] optional note of up to 300 characters ----

def test_us15_note_limit_is_300():
    assert MAX_NOTE_LENGTH == 300


def test_us15_note_is_optional(client):
    headers, _ = signup(client)
    assert upload(client, headers).status_code == 201


def test_us15_note_of_300_characters_accepted_and_saved(client, services):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers, note="a" * 300)
    assert services.repo.get_upload(services.repo.get_analysis(analysis_id).upload_id).note == "a" * 300


def test_us15_note_over_300_characters_rejected(client):
    headers, _ = signup(client)
    assert upload(client, headers, note="a" * 301).status_code == 422


# ---- [unit] pain or injury in the note => recommend a doctor or physical therapist ----

@pytest.mark.parametrize("note", [
    "my knee hurts on the way down", "Lower back PAIN after rep 3", "I injured my shoulder last month",
    "hip has been aching", "painful at the bottom", "old injury in my wrist", "it hurt",
])
def test_us15_detects_pain_or_injury(note):
    assert mentions_pain(note) is True


@pytest.mark.parametrize("note", [None, "", "felt heavy today", "first time with a belt", "Spain trip next week",
                                  "painting my garage later"])
def test_us15_ordinary_notes_are_not_pain(note):
    assert mentions_pain(note) is False


def test_us15_mentioning_no_pain_still_errs_on_the_safe_side():
    # "no pain" still mentions pain; showing the recommendation is the safe failure mode.
    assert mentions_pain("no pain at all") is True


def _view(note):
    outcome = analyze_set(squat(5, torso_bump={4: 25, 5: 25}), "squat", note=note, llm=RuleFollowingLLM(), fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    return build_result_view(outcome, note=note)


def test_us15_result_recommends_a_professional_when_pain_mentioned():
    view = _view("my knee hurts")
    assert view["professional_message"] == PROFESSIONAL_MESSAGE
    assert "doctor" in PROFESSIONAL_MESSAGE and "physical therapist" in PROFESSIONAL_MESSAGE


def test_us15_no_recommendation_without_pain():
    assert _view("felt heavy")["professional_message"] is None


def test_us15_recommendation_also_shown_when_video_unanalyzable():
    from app.testing.synthetic import empty_frames

    outcome = analyze_set(empty_frames(), "squat", note="back pain", llm=RuleFollowingLLM(), fps=30)
    assert build_result_view(outcome, note="back pain")["professional_message"] == PROFESSIONAL_MESSAGE


# ---- [unit] no diagnosis or injury-prediction language ----

@pytest.mark.parametrize("text", [
    "You have patellar tendinitis.", "Keep this up and you will injure your back.",
    "This looks like a herniated disc.", "You may have torn your ACL.", "You'll get injured lifting like this.",
])
def test_us15_validator_rejects_medical_language(text):
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}))
    result = validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], explanation=text), ctx)
    assert "medical_language" in [i.code for i in result.issues]
    assert find_medical_language(text)


def test_us15_medical_language_in_cue_is_rejected_too():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}))
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], cue="Stop or you will injure yourself")
    assert "medical_language" in [i.code for i in validate(out, ctx).issues]


def test_us15_coaching_language_is_fine():
    assert find_medical_language("Brace your core and drive through your midfoot to protect your back.") == []


# ---- [unit] pain in the note => the output must recommend a professional ----

def test_us15_validator_requires_referral_when_pain_mentioned():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}), note="my lower back hurts")
    result = validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5]), ctx)
    assert "missing_referral" in [i.code for i in result.issues]
    fixed = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], recommendation=REFERRAL)
    assert validate(fixed, ctx).ok


def test_us15_referral_must_name_a_professional():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}), note="my lower back hurts")
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5], recommendation="Take it easy for a while.")
    assert "missing_referral" in [i.code for i in validate(out, ctx).issues]


def test_us15_referral_not_required_without_pain():
    ctx, m = context_for(squat(5, torso_bump={4: 25, 5: 25}), note="felt strong")
    assert validate(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5]), ctx).ok
