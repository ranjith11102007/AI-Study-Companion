"""AI provider seam: local Ollama (default) or any OpenAI-compatible API.

Business logic imports the factory functions from here (or from
``app.ai.ollama``); the concrete runtime is selected by ``CHAT_PROVIDER`` /
``EMBEDDING_PROVIDER``.
"""

from app.ai.base import ChatModelProvider, EmbeddingProvider
from app.ai.ollama import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
    get_chat_provider,
    get_embedding_provider,
)
from app.ai.openai_compat import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
)

__all__ = [
    "ChatModelProvider",
    "EmbeddingProvider",
    "OllamaChatProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleChatProvider",
    "OpenAICompatibleEmbeddingProvider",
    "get_chat_provider",
    "get_embedding_provider",
]
