"""Settings loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

REQUIRED_ENV_VARS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
    "LLM_PROVIDER",
    "LLM_API_KEY",
)
LLM_PROVIDERS = ("claude", "gemini", "openai")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str
    llm_provider: str
    llm_api_key: str
    llm_model: str | None = None
    storage_bucket: str = "videos"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    pose_model_path: str | None = None


def load_dotenv(path: str | os.PathLike | None = None) -> None:
    """Copies KEY=VALUE lines from backend/.env into os.environ, without overriding variables already set."""
    from pathlib import Path

    path = Path(path) if path else Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Reads settings from `env` (default: os.environ). Raises ConfigError naming every missing variable."""
    env = os.environ if env is None else env
    values = {name: (env.get(name) or "").strip() for name in REQUIRED_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in backend/.env (see backend/.env.example)."
        )
    provider = values["LLM_PROVIDER"].lower()
    if provider not in LLM_PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER must be one of {', '.join(LLM_PROVIDERS)}, got '{values['LLM_PROVIDER']}'.")
    origins = tuple(o.strip() for o in (env.get("CORS_ORIGINS") or "http://localhost:3000").split(",") if o.strip())
    return Settings(
        supabase_url=values["SUPABASE_URL"].rstrip("/"),
        supabase_anon_key=values["SUPABASE_ANON_KEY"],
        supabase_service_role_key=values["SUPABASE_SERVICE_ROLE_KEY"],
        database_url=values["DATABASE_URL"],
        llm_provider=provider,
        llm_api_key=values["LLM_API_KEY"],
        llm_model=(env.get("LLM_MODEL") or "").strip() or None,
        storage_bucket=(env.get("STORAGE_BUCKET") or "videos").strip(),
        cors_origins=origins,
        pose_model_path=(env.get("POSE_MODEL_PATH") or "").strip() or None,
    )
