"""AI provider layer.

All model access (chat + embeddings) goes through the abstractions in
`app.ai.base`, so the local runtime (Ollama today, llama.cpp / vLLM /
Hugging Face tomorrow) can be swapped without touching business logic.
"""

from abc import ABC, abstractmethod
from typing import Any


class ChatModelProvider(ABC):
    """Minimal chat-completion interface implemented by local runtimes."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """Yield answer text incrementally.

        Providers that support true token streaming override this. The default
        implementation falls back to a single complete response so every
        provider remains usable without special-casing at the call site.
        """
        text = await self.chat(
            messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        if text:
            yield text

    @abstractmethod
    async def health(self) -> bool:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    """Minimal embedding interface implemented by local runtimes."""

    name: str = "base"
    dimension: int = 0

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError
