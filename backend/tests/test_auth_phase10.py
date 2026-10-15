"""Phase 10 auth: verification, password reset, Google OAuth.

SMTP and Google are never assumed to be live: every external boundary is
either exercised through a mocked transport/email capture, or honestly reported
as "not configured". The single source of truth is always the database.
"""

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Response
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.auth_security import OAuthIdentity
from app.services import email as email_service

PASSWORD = "secret123"

_EMAIL_CAPTURE = {"to": None, "subject": None, "body": None}


async def _fake_send(to_address, subject, body_text):
    _EMAIL_CAPTURE["to"] = to_address
    _EMAIL_CAPTURE["subject"] = subject
    _EMAIL_CAPTURE["body"] = body_text
    return True


@pytest.fixture
def smtp_on(monkeypatch):
    settings = get_settings()
    snapshot = {
        "smtp_host": settings.smtp_host,
        "smtp_from": settings.smtp_from,
        "frontend_base_url": settings.frontend_base_url,
    }
    settings.smtp_host = "smtp.example.test"
    settings.smtp_port = 587
    settings.smtp_from = "noreply@example.test"
    settings.frontend_base_url = "http://testserver"
    monkeypatch.setattr(email_service, "is_configured", lambda: True)
    monkeypatch.setattr(email_service, "send_email", _fake_send)
    _EMAIL_CAPTURE["to"] = _EMAIL_CAPTURE["subject"] = _EMAIL_CAPTURE["body"] = None
    yield
    settings.smtp_host = snapshot["smtp_host"]
    settings.smtp_from = snapshot["smtp_from"]
    settings.frontend_base_url = snapshot["frontend_base_url"]


async def _signup_and_signin(client: AsyncClient, email: str) -> dict:
    await client.post("/api/auth/signup", json={"name": "T", "email": email, "password": PASSWORD})
    token = (await client.post("/api/auth/signin", json={"email": email, "password": PASSWORD})).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _cleanup(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(User).filter(User.email == email))
        await db.commit()


def _extract_token(body: str | None) -> str | None:
    if not body:
        return None
    match = re.search(r"[?&]token=([A-Za-z0-9_\-]+)", body)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# Provider status                                                              #
# --------------------------------------------------------------------------- #
async def test_email_is_unconfigured_by_default():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email_enabled"] is False
        assert body["google_oauth_enabled"] is False


# --------------------------------------------------------------------------- #
# Password reset flow                                                          #
# --------------------------------------------------------------------------- #
async def test_password_reset_flow_with_mocked_smtp(smtp_on):
    _EMAIL_CAPTURE["body"] = None
    email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/auth/signup", json={"name": "T", "email": email, "password": PASSWORD})

            # Generic 202 regardless of whether the account exists.
            unknown = await client.post("/api/auth/password-reset/request", json={"email": "nope@example.com"})
            assert unknown.status_code == 200
            assert "message" in unknown.json()

            req = await client.post("/api/auth/password-reset/request", json={"email": email})
            assert req.status_code == 200
            assert _EMAIL_CAPTURE["to"] == email
            raw_token = _extract_token(_EMAIL_CAPTURE["body"])
            assert raw_token is not None

            bad = await client.post("/api/auth/password-reset/confirm", json={"token": "0" * 10, "new_password": "newpass42"})
            assert bad.status_code == 400

            ok = await client.post("/api/auth/password-reset/confirm", json={"token": raw_token, "new_password": "newpass42"})
            assert ok.status_code == 200, ok.text

            replay = await client.post("/api/auth/password-reset/confirm", json={"token": raw_token, "new_password": "x"})
            assert replay.status_code == 400

            assert (await client.post("/api/auth/signin", json={"email": email, "password": PASSWORD})).status_code == 401
            assert (await client.post("/api/auth/signin", json={"email": email, "password": "newpass42"})).status_code == 200
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# Email verification flow                                                      #
# --------------------------------------------------------------------------- #
async def test_email_verification_flow_with_mocked_smtp(smtp_on):
    email = f"ver-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _signup_and_signin(client, email)

            me0 = await client.get("/api/users/me", headers=headers)
            assert me0.json()["email_verified"] is False

            await client.post("/api/auth/verify-email/request", headers=headers)
            assert _EMAIL_CAPTURE["to"] == email
            raw = _extract_token(_EMAIL_CAPTURE["body"])
            assert raw is not None

            bad = await client.post("/api/auth/verify-email/confirm", json={"token": "wrong"})
            assert bad.status_code == 400

            ok = await client.post("/api/auth/verify-email/confirm", json={"token": raw})
            assert ok.status_code == 200
            assert ok.json()["email_verified"] is True

            me1 = await client.get("/api/users/me", headers=headers)
            assert me1.json()["email_verified"] is True
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# Google OAuth (disabled without creds)                                        #
# --------------------------------------------------------------------------- #
async def test_google_oauth_start_503_without_creds():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/google/start", follow_redirects=False)
        assert resp.status_code == 503


async def test_google_state_roundtrip():
    from app.services.auth_tokens import create_oauth_state, verify_oauth_state

    st = create_oauth_state()
    verify_oauth_state(st)  # must not raise
    with pytest.raises(ValueError):
        verify_oauth_state(st[:-4] + "AAAA")


async def test_google_exchange_with_mock_transport_and_user_create():
    settings = get_settings()
    snapshot = {
        "google_client_id": settings.google_client_id,
        "google_client_secret": settings.google_client_secret,
        "google_redirect_uri": settings.google_redirect_uri,
    }
    settings.google_client_id = "cid"
    settings.google_client_secret = "csecret"
    settings.google_redirect_uri = "http://test/cb"

    def handler(request):
        if "token" in str(request.url):
            return Response(200, json={"access_token": "atok"})
        return Response(200, json={
            "sub": "g-123",
            "email": "gl@test.test",
            "email_verified": True,
            "name": "Google Tester",
        })

    transport = MockTransport(handler)
    from app.services.auth_tokens import exchange_google_code, google_find_or_create_user

    try:
        info = await exchange_google_code("code-xyz", transport=transport)
        assert info["sub"] == "g-123"
        async with SessionLocal() as db:
            user = await google_find_or_create_user(db, info)
            assert user.password_hash is None
            assert user.email == "gl@test.test"
            assert user.email_verified_at is not None
            again = await google_find_or_create_user(db, info)
            assert again.id == user.id
            await db.execute(delete(User).filter(User.email == user.email))
            await db.execute(delete(OAuthIdentity).filter(OAuthIdentity.user_id == user.id))
            await db.commit()
    finally:
        settings.google_client_id = snapshot["google_client_id"]
        settings.google_client_secret = snapshot["google_client_secret"]
        settings.google_redirect_uri = snapshot["google_redirect_uri"]
