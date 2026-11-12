"""Wires up the app's dependencies for production, tests and test mode."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from app.auth import AuthProvider, InMemoryAuth, SupabaseAuth
from app.compress import FfmpegCompressor, VideoCompressor
from app.config import Settings, load_settings
from app.llm.client import LLMClient, make_llm_client
from app.pricing import DEFAULT_PRICES_PATH, ModelPrice, PriceTable, load_price_table
from app.repository import InMemoryRepository, PostgresRepository, Repository
from app.storage import InMemoryStorage, Storage, SupabaseStorage
from app.uploads import MAX_UPLOAD_BYTES
from app.video import OpenCVMediaPipeBackend, VideoBackend


# ALIBI_TEST_MODE only: sign-ups at these reserved domains (RFC 2606 ".test") become admins (US-25 browser tests)
# or trainers (US-22).
TEST_ADMIN_DOMAIN = "admin.test"
TEST_TRAINER_DOMAIN = "trainer.test"


@dataclass
class Services:
    auth: AuthProvider
    repo: Repository
    storage: Storage
    video: VideoBackend
    llm: LLMClient
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    compressor: VideoCompressor | None = None  # None stores the upload as is (tests and test mode)
    test_mode: bool = False
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    prices: PriceTable = field(default_factory=load_price_table)  # US-26: LLM prices per model


# The mocked LLMs report this model. It is priced only in tests and test mode, never in llm_prices.json.
MOCK_MODEL_PRICE = {"mock-coach": ModelPrice(input_per_million=1.0, output_per_million=5.0)}


def build_test_services(**overrides) -> Services:
    """In-memory auth, database and storage; synthetic video backend; rule-following fake LLM."""
    from app.testing.fakes import FakeVideoBackend, RuleFollowingLLM

    services = Services(auth=InMemoryAuth(), repo=InMemoryRepository(), storage=InMemoryStorage(),
                        video=FakeVideoBackend(), llm=RuleFollowingLLM(), test_mode=True,
                        prices=load_price_table(DEFAULT_PRICES_PATH).with_prices(MOCK_MODEL_PRICE))
    for name, value in overrides.items():
        setattr(services, name, value)
    return services


def build_services(settings: Settings) -> Services:
    return Services(
        auth=SupabaseAuth(settings.supabase_url, settings.supabase_anon_key, service_key=settings.supabase_service_role_key),
        repo=PostgresRepository(settings.database_url),
        storage=SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key, settings.storage_bucket),
        video=OpenCVMediaPipeBackend(model_path=settings.pose_model_path),
        llm=make_llm_client(settings),
        compressor=FfmpegCompressor(),
        cors_origins=settings.cors_origins,
        prices=load_price_table(settings.llm_prices_file or DEFAULT_PRICES_PATH),
    )


def services_from_env(env: Mapping[str, str] | None = None) -> Services:
    """ALIBI_TEST_MODE=1 runs the real API with in-memory services and mocks (used by the e2e tests);
    otherwise every setting must be present."""
    env = os.environ if env is None else env
    if env.get("ALIBI_TEST_MODE") == "1":
        from app.testing.fakes import ScenarioLLM, ScenarioVideoBackend

        origins = tuple(o.strip() for o in (env.get("CORS_ORIGINS") or "*").split(",") if o.strip())
        return build_test_services(auth=InMemoryAuth(admin_domain=TEST_ADMIN_DOMAIN, trainer_domain=TEST_TRAINER_DOMAIN),
                                   video=ScenarioVideoBackend(),
                                   llm=ScenarioLLM(), cors_origins=origins)
    return build_services(load_settings(env))
