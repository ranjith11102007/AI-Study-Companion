"""Unit tests for the OpenHTTP-compatible AI provider seam.

These use ``httpx.MockTransport`` so no network or model download is involved.
They prove the wire format is parsed correctly and that the app can be pointed
at a hosted OpenAI-compatible API (the "143" deployment path) instead of Ollama.
"""

import httpx
import pytest

from app.ai import ollama as ollama_module
from app.ai.openai_compat import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
)


def _transport(handler):
    return httpx.MockTransport(handler)


def _chat_provider(handler, **kwargs):
    return OpenAICompatibleChatProvider(
        base_url="http://ai.test/v1",
        api_key="test-key",
        model="test-model",
        transport=_transport(handler),
        **kwargs,
    )


def _embed_provider(handler, **kwargs):
    return OpenAICompatibleEmbeddingProvider(
        base_url="http://ai.test/v1",
        api_key="test-key",
        model="test-embed",
        dimension=768,
        transport=_transport(handler),
        **kwargs,
    )


async def test_openai_chat_parses_response_and_sends_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["path"] = request.url.path
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Hello there"}}]}
        )

    provider = _chat_provider(handler)
    reply = await provider.chat([{"role": "user", "content": "hi"}])

    assert reply == "Hello there"
    assert seen["path"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer test-key"


async def test_openai_chat_handles_empty_choices():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    assert await _chat_provider(handler).chat([{"role": "user", "content": "hi"}]) == ""


async def test_openai_chat_streams_sse_deltas():
    body = (
        'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    provider = _chat_provider(handler)
    pieces = [chunk async for chunk in provider.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(pieces) == "Hello"


async def test_openai_embeddings_return_vectors_of_expected_dimension():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        return httpx.Response(200, json={"data": [{"embedding": [0.1] * 768}]})

    vectors = await _embed_provider(handler).embed(["hello"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 768


async def test_openai_embeddings_reject_dimension_mismatch():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})

    with pytest.raises(RuntimeError, match="dimension"):
        await _embed_provider(handler).embed(["hello"])


async def test_openai_embeddings_empty_input_short_circuits():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no HTTP call should be made for empty input")

    assert await _embed_provider(handler).embed([]) == []


def test_get_chat_provider_defaults_to_ollama():
    assert isinstance(ollama_module.get_chat_provider(), ollama_module.OllamaChatProvider)


def test_get_embedding_provider_defaults_to_ollama():
    provider = ollama_module.get_embedding_provider()
    assert isinstance(provider, ollama_module.OllamaEmbeddingProvider)


def test_provider_factory_respects_openai_configuration(monkeypatch):
    monkeypatch.setattr(ollama_module.settings, "chat_provider", "openai")
    monkeypatch.setattr(ollama_module.settings, "embedding_provider", "openai")

    assert isinstance(
        ollama_module.get_chat_provider(), OpenAICompatibleChatProvider
    )
    assert isinstance(
        ollama_module.get_embedding_provider(), OpenAICompatibleEmbeddingProvider
    )


async def test_provider_health_uses_openai_status_when_configured(monkeypatch):
    from app.services import providers

    monkeypatch.setattr(providers.settings, "chat_provider", "openai")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "gemini-flash-latest"}]})

    transport = _transport(handler)

    async def fake_openai():
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("http://ai.test/v1/models")
            return {
                "name": "openai",
                "status": "ok",
                "detail": response.json()["data"][0]["id"],
            }

    monkeypatch.setattr(providers, "_openai_status", fake_openai)
    status = await providers._openai_status()
    assert status["status"] == "ok"
    assert providers._using_openai_provider() is True
