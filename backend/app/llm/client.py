"""Provider-neutral LLM request/reply types and the provider factory."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass(frozen=True)
class KeyFrame:
    frame_index: int
    timestamp: float
    rep: int | None
    jpeg: bytes


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    system: str
    messages: list[LLMMessage]
    images: list[KeyFrame]           # attached to the first user message
    payload: dict = field(default_factory=dict)  # the structured data behind the first message


@dataclass(frozen=True)
class LLMReply:
    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMReply: ...


def make_llm_client(settings, http: httpx.Client | None = None) -> LLMClient:
    """Builds the client for settings.llm_provider (claude | gemini | openai)."""
    from app.llm.providers import PROVIDERS

    cls = PROVIDERS[settings.llm_provider]
    return cls(api_key=settings.llm_api_key, model=settings.llm_model, http=http)
