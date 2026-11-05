"""US-07: AI diagnoses my form and picks the top fix. The LLM is always mocked."""
import json

import httpx
import numpy as np
import pytest

from app.config import load_settings
from app.correction import run_correction_loop
from app.faults import fault_ids
from app.llm.client import LLMMessage, LLMRequest, make_llm_client
from app.llm.providers import ClaudeClient, GeminiClient, OpenAIClient
from app.llm.schema import COACH_OUTPUT_FIELDS, coach_output_json_schema, parse_coach_output
from app.pipeline import analyze_set
from app.testing.fakes import RuleFollowingLLM, ScriptedLLM
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat
from app.validator import validate
from tests.helpers import coach_output, context_for
from tests.test_setup01_project import FULL_ENV


def blank(_index):
    return np.zeros((360, 640, 3), dtype=np.uint8)


# ---- [integration] the request carries lift, measurements, confirmed faults, unmeasured checks, 3-5 frames, note ----

def test_us07_llm_request_includes_everything():
    llm = RuleFollowingLLM()
    analyze_set(squat(5, torso_bump={3: 25, 4: 25}), "squat", note="last two felt slow", llm=llm, fps=30, frame_loader=blank)
    req = llm.requests[0]
    p = req.payload
    assert p["lift"] == "squat"
    assert p["rep_count"] == 5
    assert len(p["reps"]) == 5 and "torso_lean_increase_deg" in p["reps"][0]["metrics"]
    assert p["confirmed_faults"]["hips_rise_early"] == [3, 4]
    assert any(c["check"] == "knee_cave" for c in p["not_measured"])
    assert p["note"] == "last two felt slow"
    assert 3 <= len(req.images) <= 5
    assert all(img.jpeg.startswith(b"\xff\xd8") for img in req.images)
    # The structured data is what the model actually reads.
    text = req.messages[0].content
    assert "hips_rise_early" in text and "last two felt slow" in text


def test_us07_request_without_note_says_so():
    llm = RuleFollowingLLM()
    analyze_set(squat(2), "squat", note=None, llm=llm, fps=30, frame_loader=blank)
    assert llm.requests[0].payload["note"] is None


@pytest.mark.parametrize("n_reps", [1, 2, 10])
def test_us07_three_to_five_key_frames_for_any_set_length(n_reps):
    llm = RuleFollowingLLM()
    analyze_set(squat(n_reps, torso_bump={1: 25}), "squat", note=None, llm=llm, fps=30, frame_loader=blank)
    assert 3 <= len(llm.requests[0].images) <= 5


def test_us07_key_frames_include_the_worst_moment_of_confirmed_faults():
    llm = RuleFollowingLLM()
    outcome = analyze_set(squat(5, torso_bump={4: 25}), "squat", note=None, llm=llm, fps=30, frame_loader=blank)
    worst = outcome.measurements.reps[3].worst_frames["torso_lean_increase_deg"]
    assert worst in [img.frame_index for img in llm.requests[0].images]


# ---- [unit] strict JSON schema ----

def test_us07_schema_fields():
    assert set(COACH_OUTPUT_FIELDS) == {"lift", "camera_angle", "rep_count", "top_fault_id", "fault_reps",
                                        "supporting_measurement", "other_faults", "cue", "explanation"}
    schema = coach_output_json_schema("squat")
    assert set(COACH_OUTPUT_FIELDS) <= set(schema["required"])
    assert schema["additionalProperties"] is False


def test_us07_parse_valid_reply():
    ctx, m = context_for(squat(3, torso_bump={2: 25}))
    text = json.dumps(coach_output(ctx, m, top="hips_rise_early", reps=[2]))
    out, issues = parse_coach_output(text)
    assert issues == []
    assert out.top_fault_id == "hips_rise_early"
    assert out.supporting_measurement.rep == 2


def test_us07_parse_reply_wrapped_in_code_fence():
    ctx, m = context_for(squat(2))
    out, issues = parse_coach_output("```json\n" + json.dumps(coach_output(ctx, m)) + "\n```")
    assert issues == [] and out.rep_count == 2


@pytest.mark.parametrize("mutate", [
    lambda o: o.pop("cue"),
    lambda o: o.pop("explanation"),
    lambda o: o.update(rep_count="five"),
    lambda o: o.update(fault_reps="2"),
    lambda o: o.update(unexpected="field"),
    lambda o: o.update(camera_angle="overhead"),
    lambda o: o.update(lift="snatch"),
])
def test_us07_parse_rejects_replies_that_break_the_schema(mutate):
    ctx, m = context_for(squat(3, torso_bump={2: 25}))
    out = coach_output(ctx, m, top="hips_rise_early", reps=[2])
    mutate(out)
    parsed, issues = parse_coach_output(json.dumps(out))
    assert parsed is None
    assert [i.code for i in issues] == ["schema"]


# ---- [unit] fault IDs come from the lift's fixed list ----

@pytest.mark.parametrize("lift", ["squat", "deadlift", "bench_press"])
def test_us07_schema_limits_fault_ids_to_the_lift(lift):
    schema = coach_output_json_schema(lift)
    allowed = schema["properties"]["top_fault_id"]["anyOf"][0]["enum"]
    assert set(allowed) == set(fault_ids(lift))


def test_us07_fault_from_another_lift_is_rejected():
    frames = make_frames(SetSpec(lift="bench_press", reps=[RepSpec() for _ in range(3)]))
    ctx, m = context_for(frames, lift="bench_press")
    out = coach_output(ctx, m)
    out.update(top_fault_id="knee_cave", fault_reps=[1],
               supporting_measurement={"metric": "knee_valgus_deg", "rep": 1, "value": 12.0}, cue="Push knees out")
    result = validate(out, ctx)
    assert not result.ok
    assert "unknown_fault" in [i.code for i in result.issues]


# ---- [unit] replies that aren't JSON are failed attempts, not crashes ----

@pytest.mark.parametrize("reply", ["not json at all", "{", "[]", "", "null", '{"lift": "squat"'])
def test_us07_non_json_reply_is_a_failed_attempt(reply):
    _, issues = parse_coach_output(reply)
    assert issues and issues[0].code in ("invalid_json", "schema")


def test_us07_non_json_replies_lead_to_fallback_not_exception():
    ctx, _ = context_for(squat(3))
    llm = ScriptedLLM(["Sure! Here's my analysis:", "{", "[]"])
    result = run_correction_loop(llm, LLMRequest(system="s", messages=[LLMMessage("user", "u")], images=[], payload={}), ctx)
    assert result.status == "fallback"
    assert len(result.attempts) == 3
    assert all(a.issues for a in result.attempts)


# ---- [unit] provider switch through config ----

def _reply_for(provider):
    text = '{"ok": true}'
    if provider == "claude":
        return {"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 120, "output_tokens": 30}}
    if provider == "openai":
        return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 120, "completion_tokens": 30}}
    return {"candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30}}


@pytest.mark.parametrize("provider,cls,host", [
    ("claude", ClaudeClient, "api.anthropic.com"),
    ("gemini", GeminiClient, "generativelanguage.googleapis.com"),
    ("openai", OpenAIClient, "api.openai.com"),
])
def test_us07_provider_switched_in_config(provider, cls, host):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_reply_for(provider))

    settings = load_settings({**FULL_ENV, "LLM_PROVIDER": provider})
    client = make_llm_client(settings, http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert isinstance(client, cls)
    from app.llm.client import KeyFrame
    req = LLMRequest(system="coach", messages=[LLMMessage("user", "measurements here")],
                     images=[KeyFrame(frame_index=1, timestamp=0.1, rep=1, jpeg=b"\xff\xd8jpeg")], payload={})
    reply = client.complete(req)
    assert seen[0].url.host == host
    assert "llm-key" in " ".join(seen[0].headers.values()) or "llm-key" in str(seen[0].url)
    body = json.loads(seen[0].content)
    assert "measurements here" in json.dumps(body)
    assert "/9hqcGVn" in json.dumps(body)  # base64 of the frame bytes
    assert reply.text == '{"ok": true}'
    assert (reply.input_tokens, reply.output_tokens) == (120, 30)


def test_us07_model_can_be_set_in_config():
    settings = load_settings({**FULL_ENV, "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-test"})
    seen = []
    client = make_llm_client(settings, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: seen.append(r) or httpx.Response(200, json=_reply_for("openai")))))
    client.complete(LLMRequest(system="s", messages=[LLMMessage("user", "u")], images=[], payload={}))
    assert json.loads(seen[0].content)["model"] == "gpt-test"


def test_us07_provider_http_error_raises():
    settings = load_settings(FULL_ENV)
    client = make_llm_client(settings, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(529))))
    with pytest.raises(Exception):
        client.complete(LLMRequest(system="s", messages=[LLMMessage("user", "u")], images=[], payload={}))


# ---- [integration] mocked LLM + squat with hips rising early => top_fault = hips_rise_early ----

def test_us07_squat_with_hips_rising_early_gets_that_top_fault():
    frames = squat(5, torso_bump={3: 25, 4: 25, 5: 25})
    outcome = analyze_set(frames, "squat", note=None, llm=RuleFollowingLLM(), fps=30, frame_loader=blank)
    assert outcome.final_status == "passed_first_try"
    assert outcome.output.top_fault_id == "hips_rise_early"
    assert outcome.output.fault_reps == [3, 4, 5]
