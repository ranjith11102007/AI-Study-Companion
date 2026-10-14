import pytest


@pytest.fixture(autouse=True)
async def _dispose_async_engine():
    """Dispose the app's async engine after each test.

    The application engine (app.db.session.engine) is a module-level global.
    pytest-asyncio gives every test its own event loop, so pooled asyncpg
    connections created in one test's loop must be closed in that same loop;
    otherwise teardown raises "Event loop is closed".
    """
    yield
    from app.db.session import engine

    await engine.dispose()
