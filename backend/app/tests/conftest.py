import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import get_settings

settings = get_settings()

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
