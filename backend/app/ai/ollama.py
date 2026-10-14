"""Ollama provider: local embeddings + chat (no cloud, no paid APIs).

Talks to a local Ollama server over HTTP so the rest of the application
depends only on the abstract interfaces in ``app.ai.base``.
"""

import json
from typing import Any

import httpx

from app.ai.base import ChatModelProvider, EmbeddingProvider
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_embed_model
        self.dimension = dimension or settings.embedding_dimension
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
        vectors = data.get("embeddings")
        if not vectors:
            raise RuntimeError("Ollama returned no embeddings")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False


class OllamaChatProvider(ChatModelProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_chat_model
        self.timeout = timeout

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("message", {}).get("content", "")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """Yield answer tokens from Ollama's streaming ``/api/chat`` endpoint."""
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise RuntimeError(str(data["error"]))
                    piece = data.get("message", {}).get("content")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider.

    Defaults to local Ollama; set ``EMBEDDING_PROVIDER=openai`` (plus
    ``OPENAI_*`` settings) to use any OpenAI-compatible embedding API instead —
    which is what a hosted deployment does.
    """
    from app.ai.openai_compat import OPENAI_ALIASES, OpenAICompatibleEmbeddingProvider

    if settings.embedding_provider.strip().lower() in OPENAI_ALIASES:
        return OpenAICompatibleEmbeddingProvider()
    return OllamaEmbeddingProvider()


def get_chat_provider() -> ChatModelProvider:
    """Return the configured chat provider (Ollama locally, OpenAI-compatible if set)."""
    from app.ai.openai_compat import OPENAI_ALIASES, OpenAICompatibleChatProvider

    if settings.chat_provider.strip().lower() in OPENAI_ALIASES:
        return OpenAICompatibleChatProvider()
    return OllamaChatProvider()
