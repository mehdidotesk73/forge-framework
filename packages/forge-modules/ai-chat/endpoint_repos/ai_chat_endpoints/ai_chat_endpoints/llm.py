"""Multi-provider LLM abstraction.

Add a new provider by subclassing LLMProvider and registering it in
AVAILABLE_MODELS below. No other file needs to change.

Required environment variables (only the providers you use):
    ANTHROPIC_API_KEY
    OPENAI_API_KEY
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Generator


# ── Abstract base ─────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Common interface for all LLM providers."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],   # [{"role": "user"|"assistant", "content": "..."}]
        system: str = "",
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """Yield text tokens as they arrive from the model."""
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Return the full response in one call (used for skill extraction)."""
        ...


# ── Anthropic ─────────────────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-3-5-sonnet-20241022") -> None:
        try:
            import anthropic as _ant  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package not installed. "
                "Run: pip install forge-modules-ai-chat[anthropic]"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
        self._client = _ant.Anthropic(api_key=api_key)
        self.model = model

    def stream_chat(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream

    def chat(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text  # type: ignore[index]


# ── OpenAI ────────────────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o") -> None:
        try:
            import openai as _oai  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. "
                "Run: pip install forge-modules-ai-chat[openai]"
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        self._client = _oai.OpenAI(api_key=api_key)
        self.model = model

    def _build_messages(self, messages: list[dict], system: str) -> list[dict]:
        full: list[dict] = []
        if system:
            full.append({"role": "system", "content": system})
        full.extend(messages)
        return full

    def stream_chat(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(messages, system),  # type: ignore[arg-type]
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def chat(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(messages, system),  # type: ignore[arg-type]
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


# ── Registry ──────────────────────────────────────────────────────────────────

#: All models the module knows about — surfaced to the frontend via list_available_models.
AVAILABLE_MODELS: list[dict] = [
    {"id": "claude-opus-4-5",              "name": "Claude Opus 4.5",    "provider": "anthropic"},
    {"id": "claude-3-5-sonnet-20241022",   "name": "Claude 3.5 Sonnet",  "provider": "anthropic"},
    {"id": "claude-3-opus-20240229",       "name": "Claude 3 Opus",      "provider": "anthropic"},
    {"id": "claude-3-haiku-20240307",      "name": "Claude 3 Haiku",     "provider": "anthropic"},
    {"id": "gpt-4o",                       "name": "GPT-4o",             "provider": "openai"},
    {"id": "gpt-4o-mini",                  "name": "GPT-4o Mini",        "provider": "openai"},
    {"id": "gpt-4-turbo",                  "name": "GPT-4 Turbo",        "provider": "openai"},
    {"id": "o1",                           "name": "o1",                 "provider": "openai"},
    {"id": "o3-mini",                      "name": "o3-mini",            "provider": "openai"},
]

_EXACT: dict[str, type[LLMProvider]] = {
    m["id"]: AnthropicProvider if m["provider"] == "anthropic" else OpenAIProvider
    for m in AVAILABLE_MODELS
}


def resolve_provider(model_id: str) -> LLMProvider:
    """Resolve a model_id string to a ready-to-use LLMProvider instance."""
    if model_id in _EXACT:
        return _EXACT[model_id](model_id)

    lower = model_id.lower()
    if "claude" in lower:
        return AnthropicProvider(model_id)
    if "gpt" in lower or lower.startswith("o1") or lower.startswith("o3"):
        return OpenAIProvider(model_id)

    raise ValueError(
        f"Unknown model_id {model_id!r}. "
        f"Supported: {[m['id'] for m in AVAILABLE_MODELS]}"
    )
