"""OpenAI-compatible chat + embedding provider.

Speaks the OpenAI wire format so the same application can run against **any**
compatible endpoint without code changes: OpenAI itself, Groq, OpenRouter,
Google Gemini (its ``/v1beta/openai` endpoint), LM Studio, llamafile or a local
vLLM. Selected with ``CHAT_PROVIDER=openai` / `EMBEDDING_PROVIDER=openai``.

This is what a *hosted* deployment uses, because a free host has no local Ollama.
The default remains ``ollama`` so the app stays local-first unless configured
otherwise. No SDK is required — it speaks HTTP directly (``httpx``).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.ai.base import ChatModelProvider, EmbeddingProvider
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Values that select this provider for CHAT_PROVIDER / EMBEDDING_PROVIDER.
OPENAI_ALIASES = {"openai", "openai-compatible", "openai_compatible"}


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


class OpenAICompatibleChatProvider(ChatModelProvider):
    name = "openai"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.api_key = settings.openai_api_key if api_key is None else api_key
        self.model = model or settings.openai_chat_model
        self.timeout = timeout or settings.openai_timeout_seconds
        self._transport = transport  # injectable for tests

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with self._client() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=_headers(self.api_key),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "") or ""

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """Yield tokens from the OpenAI SSE ``stream: true`` response."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with self._client() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=_headers(self.api_key),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    piece = choices[0].get("delta", {}).get("content") if choices else None
                    if piece:
                        yield piece

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{self.base_url}/models", headers=_headers(self.api_key)
                )
                return response.status_code < 500
        except httpx.HTTPError:
            return False


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.api_key = settings.openai_api_key if api_key is None else api_key
        self.model = model or settings.openai_embed_model
        self.dimension = dimension or settings.embedding_dimension
        self.timeout = timeout or settings.openai_timeout_seconds
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self.model, "input": texts}
        if settings.openai_embed_dimension > 0:
            payload["dimensions"] = settings.openai_embed_dimension
        async with self._client() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=_headers(self.api_key),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        rows = data.get("data") or []
        vectors = [row.get("embedding") or [] for row in rows]
        if len(vectors) != len(texts):
            raise RuntimeError(
                "Embedding count did not match the number of inputs."
            )
        if vectors and len(vectors[0]) != self.dimension:
            raise RuntimeError(
                f"Embedding dimension {len(vectors[0])} does not match the "
                f"configured {self.dimension}. Choose a {self.dimension}-dim "
                "model (e.g. Gemini text-embedding-004) or set EMBEDDING_DIMENSION."
            )
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{self.base_url}/models", headers=_headers(self.api_key)
                )
                return response.status_code < 500
        except httpx.HTTPError:
            return False
