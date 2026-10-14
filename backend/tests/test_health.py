import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_reports_api_up() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "AI Study Companion"
    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"]["status"] in {"connected", "unavailable"}
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_root_serves_frontend_or_info() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/html"):
        # The bundled web app is served at the site root.
        assert "<!DOCTYPE html>" in response.text
    else:
        # No frontend build present: fall back to a small API info stub.
        payload = response.json()
        assert payload["health"] == "/api/health"
        assert payload["docs"] == "/docs"


@pytest.mark.asyncio
async def test_ui_path_redirects_to_root() -> None:
    if not get_settings().frontend_dir.is_dir():
        pytest.skip("frontend build not present")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ui", follow_redirects=False)

    assert response.status_code in {301, 302, 307, 308}
    assert response.headers["location"] == "/"
