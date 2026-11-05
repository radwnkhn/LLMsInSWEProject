"""SETUP-01: Project setup and CI."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

from app.config import REQUIRED_ENV_VARS, ConfigError, load_settings

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

FULL_ENV = {
    "SUPABASE_URL": "https://abc.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "service-key",
    "DATABASE_URL": "postgresql://postgres:pw@db.abc.supabase.co:5432/postgres",
    "LLM_PROVIDER": "claude",
    "LLM_API_KEY": "llm-key",
}


# ---- [integration] one-command start, documented in the README ----

def test_setup01_readme_documents_one_command_starts():
    readme = (ROOT / "README.md").read_text()
    assert "make backend" in readme
    assert "make frontend" in readme
    makefile = (ROOT / "Makefile").read_text()
    assert "backend:" in makefile and "uvicorn app.asgi:app" in makefile
    assert "frontend:" in makefile and "npm run dev" in makefile


def test_setup01_frontend_is_nextjs_with_tailwind_and_dev_script():
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    assert pkg["scripts"]["dev"].startswith("next dev")
    deps = {**pkg["dependencies"], **pkg["devDependencies"]}
    assert "next" in deps and "react" in deps and "tailwindcss" in deps


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_setup01_backend_starts_with_one_command():
    port = _free_port()
    env = {**os.environ, "ALIBI_TEST_MODE": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.asgi:app", "--port", str(port)],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
                assert r.json() == {"status": "ok"}
                return
            except httpx.TransportError:
                time.sleep(0.3)
        pytest.fail("backend did not answer /health within 30s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---- [integration] GET /health ----

def test_setup01_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_setup01_health_needs_no_login(client):
    assert client.get("/health", headers={"Authorization": "Bearer nonsense"}).status_code == 200


# ---- [integration] CI runs both test suites with coverage on every PR ----

def _ci():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())


def test_setup01_ci_runs_on_pull_requests():
    ci = _ci()
    triggers = ci.get("on", ci.get(True))  # PyYAML reads the bare key `on` as True
    assert "pull_request" in triggers


def test_setup01_ci_runs_backend_and_frontend_tests_with_coverage():
    runs = " ".join(step.get("run", "") for job in _ci()["jobs"].values() for step in job["steps"])
    assert "pytest" in runs and "--cov" in runs
    assert "npm run test:coverage" in runs
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    assert "--coverage" in pkg["scripts"]["test:coverage"]


def test_setup01_ci_never_uses_a_real_llm_key():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "secrets.LLM_API_KEY" not in text


# ---- [unit] config from environment ----

def test_setup01_config_loads_keys_from_env():
    s = load_settings(FULL_ENV)
    assert s.supabase_url == "https://abc.supabase.co"
    assert s.supabase_anon_key == "anon-key"
    assert s.supabase_service_role_key == "service-key"
    assert s.database_url.startswith("postgresql://")
    assert s.llm_provider == "claude"
    assert s.llm_api_key == "llm-key"


@pytest.mark.parametrize("missing", REQUIRED_ENV_VARS)
def test_setup01_config_missing_key_fails_with_clear_error(missing):
    env = {k: v for k, v in FULL_ENV.items() if k != missing}
    with pytest.raises(ConfigError) as err:
        load_settings(env)
    assert missing in str(err.value)
    assert "Missing required environment variable" in str(err.value)


def test_setup01_config_lists_every_missing_key_at_once():
    with pytest.raises(ConfigError) as err:
        load_settings({})
    for name in REQUIRED_ENV_VARS:
        assert name in str(err.value)


def test_setup01_config_blank_value_counts_as_missing():
    with pytest.raises(ConfigError) as err:
        load_settings({**FULL_ENV, "LLM_API_KEY": "   "})
    assert "LLM_API_KEY" in str(err.value)


def test_setup01_config_rejects_unknown_llm_provider():
    with pytest.raises(ConfigError) as err:
        load_settings({**FULL_ENV, "LLM_PROVIDER": "llama"})
    assert "LLM_PROVIDER" in str(err.value)


def test_setup01_required_vars_cover_supabase_and_llm():
    assert {"SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "LLM_API_KEY", "LLM_PROVIDER"} <= set(REQUIRED_ENV_VARS)
