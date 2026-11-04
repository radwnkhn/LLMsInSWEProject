"""US-09: Automatic correction and safe fallback. (Fallback note on screen: frontend/e2e/us09-fallback.spec.ts.)"""
import json

import numpy as np
from fastapi.testclient import TestClient

from app.correction import MAX_ATTEMPTS, run_correction_loop
from app.llm.client import LLMMessage, LLMRequest
from app.main import create_app
from app.pipeline import analyze_set
from app.results import FALLBACK_NOTE, build_result_view
from app.services import build_test_services
from app.testing.fakes import FailingLLM, ScriptedLLM, SequenceLLM
from app.testing.synthetic import squat
from tests.helpers import coach_output, context_for, signup, upload_ok

def _request():
    return LLMRequest(system="coach", messages=[LLMMessage("user", "measurements")], images=[], payload={})


def _ctx():
    return context_for(squat(5, torso_bump={4: 25, 5: 25}))


def _good(ctx, m):
    return json.dumps(coach_output(ctx, m, top="hips_rise_early", reps=[4, 5]))


def _wrong_count(ctx, m, count=6):
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["rep_count"] = count
    return json.dumps(out)


def test_us09_at_most_three_attempts():
    assert MAX_ATTEMPTS == 3


# ---- [unit] the exact validation errors go back to the LLM ----

def test_us09_errors_sent_back_word_for_word():
    ctx, m = _ctx()
    bad = _wrong_count(ctx, m)
    llm = ScriptedLLM([bad, _good(ctx, m)])
    run_correction_loop(llm, _request(), ctx)
    retry = llm.requests[1]
    assert retry.messages[0].content == "measurements"          # original request kept
    assert retry.messages[1].role == "assistant" and retry.messages[1].content == bad
    assert retry.messages[2].role == "user"
    assert "feedback says 6 reps but 5 were detected" in retry.messages[2].content
    assert retry.images == []


def test_us09_every_error_is_sent_back():
    ctx, m = _ctx()
    out = coach_output(ctx, m, top="hips_rise_early", reps=[4, 5])
    out["rep_count"] = 7
    out["fault_reps"] = [4, 5, 9]
    llm = ScriptedLLM([json.dumps(out), _good(ctx, m)])
    run_correction_loop(llm, _request(), ctx)
    feedback = llm.requests[1].messages[-1].content
    assert "feedback says 7 reps but 5 were detected" in feedback
    assert "rep 9 cited for hips rising early, but only 5 reps were detected" in feedback


# ---- [unit] corrected replies are validated again, at most 3 attempts in total ----

def test_us09_corrected_reply_is_validated_again():
    ctx, m = _ctx()
    llm = ScriptedLLM([_wrong_count(ctx, m, 6), _wrong_count(ctx, m, 4), _good(ctx, m)])
    result = run_correction_loop(llm, _request(), ctx)
    assert llm.calls == 3
    assert result.status == "passed_after_retry"
    assert "feedback says 4 reps but 5 were detected" in result.attempts[1].messages
    assert "feedback says 4 reps but 5 were detected" in llm.requests[2].messages[-1].content


def test_us09_never_more_than_three_attempts():
    ctx, m = _ctx()
    llm = ScriptedLLM([_wrong_count(ctx, m)] * 10)
    result = run_correction_loop(llm, _request(), ctx)
    assert llm.calls == 3
    assert result.status == "fallback"
    assert result.output is None
    assert [a.attempt_number for a in result.attempts] == [1, 2, 3]


def test_us09_llm_errors_count_as_failed_attempts():
    ctx, _ = _ctx()
    llm = FailingLLM()
    result = run_correction_loop(llm, _request(), ctx)
    assert llm.calls == 3
    assert result.status == "fallback"
    assert all(a.issues[0].code == "llm_error" for a in result.attempts)


# ---- [unit] a passing attempt is used and no more attempts are made ----

def test_us09_first_pass_is_used_without_retrying():
    ctx, m = _ctx()
    llm = ScriptedLLM([_good(ctx, m), _wrong_count(ctx, m)])
    result = run_correction_loop(llm, _request(), ctx)
    assert llm.calls == 1
    assert result.status == "passed_first_try"
    assert result.output.top_fault_id == "hips_rise_early"


def test_us09_pass_on_second_attempt_stops_there():
    ctx, m = _ctx()
    llm = ScriptedLLM([_wrong_count(ctx, m), _good(ctx, m), _wrong_count(ctx, m)])
    result = run_correction_loop(llm, _request(), ctx)
    assert llm.calls == 2
    assert result.status == "passed_after_retry"
    assert result.attempts[-1].issues == []


# ---- [unit] after 3 failures: only verified measurements and the rep breakdown ----

def test_us09_fallback_result_has_measurements_but_no_ai_text():
    llm = ScriptedLLM(["not json"] * 3)
    outcome = analyze_set(squat(5, torso_bump={4: 25, 5: 25}), "squat", note=None, llm=llm, fps=30,
                          frame_loader=lambda i: np.zeros((360, 640, 3), np.uint8))
    assert outcome.final_status == "fallback"
    view = build_result_view(outcome, note=None)
    assert view["fallback_note"] == FALLBACK_NOTE
    assert view["top_fix"] is None and view["cue"] is None and view["explanation"] is None
    assert view["other_faults"] == [] and view["no_major_issues"] is False
    assert view["annotated_frame"] is None
    assert len(view["measurements"]) == 5
    assert len(view["rep_breakdown"]["rows"]) == 5
    assert "not json" not in json.dumps(view)


def test_us09_fallback_note_text():
    assert FALLBACK_NOTE == "Coaching feedback isn't available for this video. Here are your measurements."


# ---- [integration] every attempt is logged ----

def test_us09_every_attempt_logged_with_number_output_errors_and_tokens():
    services = build_test_services(llm=SequenceLLM(["invalid", "pass"]))
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    attempts = services.repo.list_llm_attempts(analysis_id)
    assert [a.attempt_number for a in attempts] == [1, 2]
    assert attempts[0].output_text == "this is not JSON"
    assert attempts[0].issues and attempts[0].passed is False
    assert attempts[1].issues == [] and attempts[1].passed is True
    assert json.loads(attempts[1].output_text)["top_fault_id"] == "hips_rise_early"
    assert all(a.input_tokens > 0 and a.output_tokens > 0 for a in attempts)
    assert services.repo.get_analysis(analysis_id).final_status == "passed_after_retry"


def test_us09_fallback_attempts_are_all_logged():
    services = build_test_services(llm=SequenceLLM(["invalid"] * 3))
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert len(services.repo.list_llm_attempts(analysis_id)) == 3
    result = client.get(f"/analyses/{analysis_id}", headers=headers).json()
    assert result["final_status"] == "fallback"
    assert result["fallback_note"] == FALLBACK_NOTE
