"""US-26: Track AI usage and cost. (Admin UI: frontend/src/components/__tests__/us26-*.test.tsx.)

Acceptance criteria (#28):
1. [unit] [integration] Every LLM attempt, retries and failed requests included, saves input tokens, output tokens,
   provider and model, read from the provider's usage field.
2. [unit] Cost comes from a per-model price table in a config file; an unknown model shows "Unknown cost".
3. [integration] [e2e] The admin analysis detail shows each attempt's provider, model, tokens and cost, plus totals.
4. [unit] [integration] [e2e] An admin cost summary for a date range: total, analyses, average, retry share.
5. [integration] Non-admins get 403 on the cost summary and every admin endpoint that returns usage or cost.

Provider responses are mocked with httpx.MockTransport; no real LLM API is called.
"""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import importlib

from app.config import load_settings
from app.correction import run_correction_loop
from app.llm.client import LLMReply, LLMRequest, LLMMessage
from app.llm.providers import ClaudeClient, GeminiClient, OpenAIClient
from app.main import create_app
from app.services import build_test_services
from app.testing import synthetic
from app.testing.fakes import RuleFollowingLLM
from tests.helpers import context_for, make_admin, signup, upload_ok

REQUEST = LLMRequest(system="coach", messages=[LLMMessage("user", "measurements")], images=[])

# Realistic response bodies (trimmed), shaped like each provider's documented reply.
CLAUDE_RESPONSE = {
    "id": "msg_01XYZ", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
    "content": [{"type": "text", "text": "{\"ok\": true}"}], "stop_reason": "end_turn",
    "usage": {"input_tokens": 2104, "output_tokens": 312, "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0, "service_tier": "standard"},
}
OPENAI_RESPONSE = {
    "id": "chatcmpl-9", "object": "chat.completion", "model": "gpt-4.1-mini-2025-04-14",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "{\"ok\": true}"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1850, "completion_tokens": 240, "total_tokens": 2090,
              "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0}},
}
GEMINI_RESPONSE = {
    "candidates": [{"content": {"role": "model", "parts": [{"text": "{\"ok\": true}"}]}, "finishReason": "STOP"}],
    "modelVersion": "gemini-2.5-flash",
    "usageMetadata": {"promptTokenCount": 1990, "candidatesTokenCount": 180, "thoughtsTokenCount": 420,
                      "totalTokenCount": 2590},
}


def _http(body):
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))


class UsageLLM(RuleFollowingLLM):
    """A mocked provider that reports realistic usage: first reply invalid, then rule-following."""

    provider, model = "claude", "claude-sonnet-5-5"

    def __init__(self, behaviors=("invalid", "pass")):
        super().__init__()
        self.behaviors = list(behaviors)

    def complete(self, request):
        behavior = self.behaviors[min(len(self.requests), len(self.behaviors) - 1)]
        self.requests.append(request)
        text = self.reply_for(request) if behavior == "pass" else "not JSON"
        n = len(self.requests)
        return LLMReply(text, 2000 + n, 300 + n, provider=self.provider, model=self.model)


class DownLLM:
    provider, model = "openai", "gpt-4.1-mini"

    def complete(self, request):
        raise httpx.ConnectError("provider unreachable")


@pytest.fixture
def pricing():
    """app.pricing, imported per test so each test reports its own failure before the module exists."""
    return importlib.import_module("app.pricing")


@pytest.fixture
def prices(pricing):
    return pricing.PriceTable({"claude-sonnet-5-5": pricing.ModelPrice(2.0, 10.0),
                               "gpt-4.1-mini": pricing.ModelPrice(0.4, 1.6)})


def _services(prices, llm=None):
    services = build_test_services(llm=llm or UsageLLM(), prices=prices)
    return services, TestClient(create_app(services))


# ---- 1. [unit] [integration] every attempt records tokens, provider and model ----

def test_us26_claude_reply_reads_usage_and_model():
    reply = ClaudeClient("key", http=_http(CLAUDE_RESPONSE)).complete(REQUEST)
    assert (reply.provider, reply.model, reply.input_tokens, reply.output_tokens) == ("claude", "claude-sonnet-5-5", 2104, 312)


def test_us26_openai_reply_reads_usage_and_model():
    reply = OpenAIClient("key", http=_http(OPENAI_RESPONSE)).complete(REQUEST)
    assert (reply.provider, reply.model, reply.input_tokens, reply.output_tokens) == (
        "openai", "gpt-4.1-mini-2025-04-14", 1850, 240)


def test_us26_gemini_reply_counts_thinking_tokens_as_output():
    reply = GeminiClient("key", http=_http(GEMINI_RESPONSE)).complete(REQUEST)
    assert (reply.provider, reply.model, reply.input_tokens, reply.output_tokens) == (
        "gemini", "gemini-2.5-flash", 1990, 180 + 420)


@pytest.mark.parametrize("cls,body,model", [
    (ClaudeClient, {**CLAUDE_RESPONSE, "usage": {}, "model": None}, "claude-sonnet-5-5"),
    (OpenAIClient, {k: v for k, v in OPENAI_RESPONSE.items() if k not in ("usage", "model")}, "gpt-4.1-mini"),
    (GeminiClient, {k: v for k, v in GEMINI_RESPONSE.items() if k not in ("usageMetadata", "modelVersion")},
     "gemini-2.5-flash"),
])
def test_us26_missing_usage_records_zero_tokens_and_configured_model(cls, body, model):
    reply = cls("key", http=_http(body)).complete(REQUEST)
    assert (reply.input_tokens, reply.output_tokens, reply.model) == (0, 0, model)


def test_us26_correction_loop_records_usage_for_every_attempt():
    ctx, m = context_for(synthetic.squat(5, torso_bump={4: 25, 5: 25}))
    from app.llm.prompt import build_payload

    request = LLMRequest(system="s", messages=[LLMMessage("user", "u")], images=[],
                         payload=build_payload(m, ctx.not_measured, ctx.confirmed, None, []))
    result = run_correction_loop(UsageLLM(), request, ctx)
    assert result.status == "passed_after_retry"
    assert [(a.attempt_number, a.provider, a.model, a.input_tokens, a.output_tokens) for a in result.attempts] == [
        (1, "claude", "claude-sonnet-5-5", 2001, 301), (2, "claude", "claude-sonnet-5-5", 2002, 302)]


def test_us26_failed_request_records_provider_model_and_zero_tokens():
    ctx, m = context_for(synthetic.squat(3))
    result = run_correction_loop(DownLLM(), REQUEST, ctx)
    assert [(a.provider, a.model, a.input_tokens, a.output_tokens) for a in result.attempts] == [
        ("openai", "gpt-4.1-mini", 0, 0)] * 3


def test_us26_saved_attempts_keep_usage_provider_and_model(prices):
    services, client = _services(prices)
    lifter, _ = signup(client)
    analysis_id = upload_ok(client, lifter)
    saved = services.repo.list_llm_attempts(analysis_id)
    assert [(a.attempt_number, a.provider, a.model, a.input_tokens, a.output_tokens) for a in saved] == [
        (1, "claude", "claude-sonnet-5-5", 2001, 301), (2, "claude", "claude-sonnet-5-5", 2002, 302)]


def test_us26_migration_adds_provider_and_model_to_llm_attempts():
    from tests.test_setup02_database import MIGRATIONS

    sql = "\n".join(p.read_text() for p in MIGRATIONS).lower()
    assert "alter table public.llm_attempts" in sql
    assert "add column if not exists provider text" in sql and "add column if not exists model text" in sql


# ---- 2. [unit] cost from a price table in a config file ----

def test_us26_cost_uses_dollars_per_million_tokens(pricing):
    table = pricing.PriceTable({"m": pricing.ModelPrice(input_per_million=2.0, output_per_million=10.0)})
    assert table.cost("m", 1_000_000, 500_000) == pytest.approx(7.0)
    assert table.cost("m", 2104, 312) == pytest.approx(0.004208 + 0.00312)
    assert table.cost("m", 0, 0) == 0


@pytest.mark.parametrize("model", ["not-in-the-table", None, ""])
def test_us26_unknown_model_has_unknown_cost(model, prices):
    assert prices.cost(model, 1000, 1000) is None


def test_us26_dated_model_names_use_their_base_price(prices):
    # OpenAI replies with a dated snapshot name such as gpt-4.1-mini-2025-04-14.
    assert prices.cost("gpt-4.1-mini-2025-04-14", 1_000_000, 0) == pytest.approx(0.4)
    assert prices.cost("gpt-4.1-mini-preview", 1_000_000, 0) is None


def test_us26_price_table_loads_from_a_config_file(tmp_path, pricing):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps({"checked": "2026-11-11", "source": "test",
                                "models": {"x-model": {"input_per_million": 1.5, "output_per_million": 3}}}))
    table = pricing.load_price_table(path)
    assert table.cost("x-model", 1_000_000, 1_000_000) == pytest.approx(4.5)
    assert table.cost("claude-sonnet-5-5", 1, 1) is None


@pytest.mark.parametrize("content", ["not json", json.dumps({"models": {"m": {"input_per_million": 1}}}),
                                     json.dumps({"models": {"m": {"input_per_million": -1, "output_per_million": 1}}}),
                                     json.dumps({"models": []})])
def test_us26_malformed_price_file_fails_with_a_clear_error(tmp_path, content, pricing):
    path = tmp_path / "prices.json"
    path.write_text(content)
    with pytest.raises(pricing.PriceTableError, match="prices.json"):
        pricing.load_price_table(path)


def test_us26_default_price_file_covers_each_providers_default_model(pricing):
    table = pricing.load_price_table(pricing.DEFAULT_PRICES_PATH)
    for cls in (ClaudeClient, OpenAIClient, GeminiClient):
        assert table.cost(cls.default_model, 1000, 1000) is not None, cls.default_model
    raw = json.loads(pricing.DEFAULT_PRICES_PATH.read_text())
    assert raw["checked"] and raw["source"]


def test_us26_price_file_location_comes_from_settings(tmp_path):
    env = {name: "x" for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL",
                                  "LLM_API_KEY")}
    env["LLM_PROVIDER"] = "claude"
    assert load_settings(env).llm_prices_file is None
    assert load_settings({**env, "LLM_PRICES_FILE": str(tmp_path / "p.json")}).llm_prices_file == str(tmp_path / "p.json")


def test_us26_changing_the_price_table_changes_reported_cost(pricing):
    cheap = pricing.PriceTable({"claude-sonnet-5-5": pricing.ModelPrice(1.0, 1.0)})
    services, client = _services(cheap)
    admin, _ = make_admin(client, services)
    lifter, _ = signup(client, "l@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    attempt = client.get(f"/admin/analyses/{analysis_id}", headers=admin).json()["attempts"][0]
    assert attempt["cost"] == pytest.approx((2001 + 301) / 1_000_000)


# ---- 3. [integration] the analysis detail shows tokens and cost per attempt and in total ----

def test_us26_admin_detail_shows_usage_and_cost_per_attempt_and_total(prices):
    services, client = _services(prices)
    admin, _ = make_admin(client, services)
    lifter, _ = signup(client, "l@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    detail = client.get(f"/admin/analyses/{analysis_id}", headers=admin).json()
    costs = [2001 * 2e-6 + 301 * 10e-6, 2002 * 2e-6 + 302 * 10e-6]
    for attempt, cost in zip(detail["attempts"], costs):
        assert (attempt["provider"], attempt["model"]) == ("claude", "claude-sonnet-5-5")
        assert attempt["cost"] == pytest.approx(cost)
    assert detail["usage"]["input_tokens"] == 4003 and detail["usage"]["output_tokens"] == 603
    assert detail["usage"]["cost"] == pytest.approx(sum(costs))
    assert detail["usage"]["unknown_cost_attempts"] == 0


def test_us26_admin_detail_shows_unknown_cost_instead_of_failing(pricing):
    services, client = _services(pricing.PriceTable({}))
    admin, _ = make_admin(client, services)
    lifter, _ = signup(client, "l@virginia.edu")
    detail = client.get(f"/admin/analyses/{upload_ok(client, lifter)}", headers=admin).json()
    assert [a["cost"] for a in detail["attempts"]] == [None, None]
    assert detail["usage"]["cost"] is None and detail["usage"]["unknown_cost_attempts"] == 2


def test_us26_attempts_saved_before_us26_show_unknown_model_and_cost(prices):
    services, client = _services(prices)
    admin, _ = make_admin(client, services)
    lifter, _ = signup(client, "l@virginia.edu")
    analysis_id = upload_ok(client, lifter)
    services.repo.attempts[analysis_id] = [replace(a, provider=None, model=None)
                                           for a in services.repo.attempts[analysis_id]]
    attempt = client.get(f"/admin/analyses/{analysis_id}", headers=admin).json()["attempts"][0]
    assert (attempt["provider"], attempt["model"], attempt["cost"]) == (None, None, None)


# ---- 4. [unit] [integration] cost summary over a date range ----

def _usage(pricing, analysis, attempt, model="claude-sonnet-5-5", tokens=(1_000_000, 0), day=1):
    return pricing.AttemptUsage(analysis_id=analysis, analysis_created_at=datetime(2026, 11, day, tzinfo=timezone.utc),
                                attempt_number=attempt, input_tokens=tokens[0], output_tokens=tokens[1],
                                provider="claude", model=model)


def test_us26_summary_unit_totals_average_and_retry_share(pricing, prices):
    rows = [_usage(pricing, "a", 1), _usage(pricing, "a", 2), _usage(pricing, "a", 3), _usage(pricing, "b", 1, tokens=(0, 100_000)),
            _usage(pricing, "c", 1, model="mystery")]
    s = pricing.summarize_costs(rows, prices)
    assert s["analysis_count"] == 3 and s["attempt_count"] == 5 and s["retry_attempt_count"] == 2
    assert s["total_cost"] == pytest.approx(2 * 3 + 1.0)       # analysis a: 3 x $2; b: 0.1M output x $10
    assert s["average_cost"] == pytest.approx(7.0 / 3)
    assert s["retry_cost"] == pytest.approx(4.0)
    assert s["retry_share"] == pytest.approx(4.0 / 7.0)
    assert s["unknown_cost_attempts"] == 1
    assert s["input_tokens"] == 3_000_000 and s["output_tokens"] == 100_000


def test_us26_summary_unit_with_no_attempts_has_no_average_or_share(pricing, prices):
    s = pricing.summarize_costs([], prices)
    assert (s["analysis_count"], s["total_cost"], s["average_cost"], s["retry_share"]) == (0, 0, None, None)


def test_us26_cost_summary_counts_only_analyses_in_the_date_range(prices):
    services, client = _services(prices)
    admin, _ = make_admin(client, services)
    lifter, _ = signup(client, "l@virginia.edu")
    old, recent = upload_ok(client, lifter), upload_ok(client, lifter)
    a = services.repo.analyses[old]
    services.repo.analyses[old] = replace(a, created_at=datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    today = datetime.now(timezone.utc).date()

    r = client.get(f"/admin/costs?start={today - timedelta(days=1)}&end={today}", headers=admin)
    assert r.status_code == 200, r.text
    s = r.json()
    per_analysis = (2001 + 2002) * 2e-6 + (301 + 302) * 10e-6
    assert (s["start"], s["end"]) == (str(today - timedelta(days=1)), str(today))
    assert s["analysis_count"] == 1 and s["attempt_count"] == 2
    assert s["total_cost"] == pytest.approx(per_analysis) and s["average_cost"] == pytest.approx(per_analysis)
    assert s["retry_share"] == pytest.approx((2002 * 2e-6 + 302 * 10e-6) / per_analysis)

    january = client.get("/admin/costs?start=2026-01-15&end=2026-01-15", headers=admin).json()
    assert january["analysis_count"] == 1
    assert client.get("/admin/costs?start=2025-01-01&end=2025-12-31", headers=admin).json()["analysis_count"] == 0
    assert recent


def test_us26_cost_summary_defaults_to_the_last_30_days(client, services):
    admin, _ = make_admin(client, services)
    s = client.get("/admin/costs", headers=admin).json()
    today = datetime.now(timezone.utc).date()
    assert (s["start"], s["end"]) == (str(today - timedelta(days=29)), str(today))


@pytest.mark.parametrize("query", ["start=2026-11-10&end=2026-11-01", "start=11/01/2026&end=2026-11-10",
                                   "start=2026-02-30&end=2026-03-01"])
def test_us26_cost_summary_rejects_invalid_date_ranges(client, services, query):
    admin, _ = make_admin(client, services)
    assert client.get(f"/admin/costs?{query}", headers=admin).status_code == 422


# ---- 5. [integration] non-admins get 403 ----

@pytest.mark.parametrize("path", ["/admin/costs", "/admin/costs?start=2026-11-01&end=2026-11-10",
                                  "/admin/analyses/00000000-0000-0000-0000-000000000000"])
def test_us26_non_admin_gets_403_on_usage_and_cost(client, path):
    lifter, _ = signup(client)
    assert client.get(path, headers=lifter).status_code == 403
    assert client.get(path).status_code == 401


def test_us26_lifters_never_see_usage_or_cost_on_their_own_results(prices):
    services, client = _services(prices)
    lifter, _ = signup(client)
    result = client.get(f"/analyses/{upload_ok(client, lifter)}", headers=lifter).json()
    text = json.dumps(result)
    assert "cost" not in result and "usage" not in result and "claude-sonnet-5-5" not in text
