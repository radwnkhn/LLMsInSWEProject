"""US-05: Tell me when a video can't be analyzed. (Refilm button: frontend/e2e/us05-refilm.spec.ts.)"""
import pytest

from app.analyzability import BODY_NOT_VISIBLE, NO_PERSON, NO_REPS, check_analyzable
from app.measure import measure_set
from app.pipeline import analyze_set
from app.testing.fakes import SpyLLM
from app.testing.synthetic import RepSpec, SetSpec, empty_frames, make_frames, squat, standing_still
from tests.helpers import signup, upload_ok


def _reason(frames, lift="squat"):
    m = measure_set(frames, lift, fps=30)
    return check_analyzable(frames, m.rep_count)


def test_us05_messages_are_exact():
    assert NO_PERSON == "Couldn't analyze: no person found"
    assert BODY_NOT_VISIBLE == "Couldn't analyze: body not clearly visible"
    assert NO_REPS == "Couldn't analyze: no reps found"


# ---- [unit] no person ----

def test_us05_no_person_detected():
    assert check_analyzable(empty_frames(), 0) == NO_PERSON


def test_us05_empty_video_has_no_person():
    assert check_analyzable([], 0) == NO_PERSON


# ---- [unit] key joints below 0.5 confidence on more than half the frames ----

@pytest.mark.parametrize("group", ["hips", "knees", "ankles", "shoulders"])
def test_us05_body_not_clearly_visible(group):
    frames = make_frames(SetSpec(low_confidence={group: 0.6}))
    assert _reason(frames) == BODY_NOT_VISIBLE


def test_us05_low_confidence_on_exactly_half_the_frames_is_still_analyzable():
    frames = make_frames(SetSpec(low_confidence={"knees": 0.5}))
    assert _reason(frames) is None


def test_us05_low_confidence_on_non_key_joints_is_analyzable():
    frames = make_frames(SetSpec(low_confidence={"wrists": 1.0, "ears": 1.0}))
    assert _reason(frames) is None


def test_us05_frames_without_a_person_count_against_visibility():
    frames = make_frames(SetSpec(reps=[RepSpec()], no_person_frames=400))
    assert _reason(frames) == BODY_NOT_VISIBLE


# ---- [unit] no complete rep ----

def test_us05_no_reps_when_standing_still():
    assert _reason(standing_still()) == NO_REPS


def test_us05_incomplete_rep_is_not_a_rep():
    frames = make_frames(SetSpec(reps=[], trailing_partial=True))
    assert _reason(frames) == NO_REPS


def test_us05_visibility_is_checked_before_reps():
    frames = make_frames(SetSpec(reps=[], low_confidence={"hips": 1.0}))
    assert _reason(frames) == BODY_NOT_VISIBLE


def test_us05_good_video_is_analyzable():
    assert _reason(squat(3)) is None


# ---- [integration] the LLM is never called for an unanalyzable video ----

@pytest.mark.parametrize("frames,reason", [
    (empty_frames(), NO_PERSON),
    (make_frames(SetSpec(low_confidence={"hips": 0.9})), BODY_NOT_VISIBLE),
    (standing_still(), NO_REPS),
])
def test_us05_llm_never_called_for_unanalyzable_video(frames, reason):
    llm = SpyLLM()
    outcome = analyze_set(frames, "squat", note=None, llm=llm, fps=30)
    assert llm.calls == 0
    assert outcome.final_status == "unanalyzable"
    assert outcome.unanalyzable_reason == reason
    assert outcome.correction is None


@pytest.mark.parametrize("filename,reason", [
    ("no_person.mp4", NO_PERSON), ("blurry.mp4", BODY_NOT_VISIBLE), ("no_reps.mp4", NO_REPS),
])
def test_us05_api_reports_reason_without_calling_llm(client, services, filename, reason):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers, filename=filename)
    result = client.get(f"/analyses/{analysis_id}", headers=headers).json()
    assert result["final_status"] == "unanalyzable"
    assert result["unanalyzable_reason"] == reason
    assert result["top_fix"] is None
    assert services.llm.requests == []
    assert services.repo.list_llm_attempts(analysis_id) == []
