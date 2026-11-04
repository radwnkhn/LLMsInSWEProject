"""HTTP clients for each LLM provider. Each turns an LLMRequest into the provider's format."""
from __future__ import annotations

import base64

import httpx

from app.llm.client import LLMReply, LLMRequest

TIMEOUT = httpx.Timeout(90.0, connect=10.0)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class _HTTPClient:
    default_model = ""

    def __init__(self, api_key: str, model: str | None = None, http: httpx.Client | None = None):
        self.api_key = api_key
        self.model = model or self.default_model
        self.http = http or httpx.Client(timeout=TIMEOUT)

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        r = self.http.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()


class ClaudeClient(_HTTPClient):
    default_model = "claude-sonnet-5-5"

    def complete(self, request: LLMRequest) -> LLMReply:
        messages = []
        for i, m in enumerate(request.messages):
            content: list[dict] = [{"type": "text", "text": m.content}]
            if i == 0:
                content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(f.jpeg)}}
                           for f in request.images] + content
            messages.append({"role": m.role, "content": content})
        data = self._post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 2048, "system": request.system, "messages": messages},
        )
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMReply(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0))


class OpenAIClient(_HTTPClient):
    default_model = "gpt-4.1-mini"

    def complete(self, request: LLMRequest) -> LLMReply:
        messages: list[dict] = [{"role": "system", "content": request.system}]
        for i, m in enumerate(request.messages):
            if i == 0:
                parts = [{"type": "text", "text": m.content}] + [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(f.jpeg)}"}}
                    for f in request.images]
                messages.append({"role": m.role, "content": parts})
            else:
                messages.append({"role": m.role, "content": m.content})
        data = self._post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {"model": self.model, "messages": messages, "response_format": {"type": "json_object"}},
        )
        usage = data.get("usage", {})
        return LLMReply(data["choices"][0]["message"]["content"] or "",
                        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


class GeminiClient(_HTTPClient):
    default_model = "gemini-2.5-flash"

    def complete(self, request: LLMRequest) -> LLMReply:
        contents = []
        for i, m in enumerate(request.messages):
            parts: list[dict] = [{"text": m.content}]
            if i == 0:
                parts = [{"inline_data": {"mime_type": "image/jpeg", "data": _b64(f.jpeg)}} for f in request.images] + parts
            contents.append({"role": "model" if m.role == "assistant" else "user", "parts": parts})
        data = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.api_key},
            {"systemInstruction": {"parts": [{"text": request.system}]}, "contents": contents,
             "generationConfig": {"responseMimeType": "application/json"}},
        )
        parts = data["candidates"][0]["content"]["parts"]
        usage = data.get("usageMetadata", {})
        return LLMReply("".join(p.get("text", "") for p in parts),
                        usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))


PROVIDERS = {"claude": ClaudeClient, "gemini": GeminiClient, "openai": OpenAIClient}
