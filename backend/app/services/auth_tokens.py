"""Authentication helpers: verification/reset tokens + (optional) Google OAuth.

No mail or provider call happens unless the operator configures the relevant
settings. Tokens are always stored hashed; the raw value only travels in the
email/link to the user.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import get_settings
from app.models.auth_security import (
    EmailVerificationToken,
    OAuthIdentity,
    PasswordResetToken,
)
from app.models.user import User
from app.services import email as email_service
from app.services.auth import get_password_hash

settings = get_settings()


# --------------------------------------------------------------------------- #
# Tokens (raw + hash)                                                         #
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _expires(minutes: int) -> datetime:
    return _now() + timedelta(minutes=minutes)


# --------------------------------------------------------------------------- #
# Email verification                                                           #
# --------------------------------------------------------------------------- #
async def request_email_verification(db: AsyncSession, user: User) -> bool:
    """Create (and email) a verification link. Returns whether mail was sent.

    Any previously issued, unused token is revoked so only the latest link works.
    The caller receives the same response regardless of delivery so the endpoint
    cannot be used to probe whether an address exists.
    """
    if user.email_verified_at is not None:
        return False
    if not email_service.is_configured():
        return False

    now = _now()
    existing = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    for token in existing.scalars().all():
        token.used_at = now
        db.add(token)

    raw = new_raw_token()
    row = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=_expires(settings.email_verify_token_ttl_minutes),
    )
    db.add(row)
    await db.commit()

    link = f"{settings.frontend_base_url}/verify.html?token={raw}"
    subject = "Confirm your StudyMate AI email"
    body = (
        "Confirm your email address to finish setting up your account.\n\n"
        f"Verification link: {link}\n\n"
        f"This link expires in {settings.email_verify_token_ttl_minutes} minutes. "
        "If you did not request this, you can ignore this message.\n"
    )
    await email_service.send_email(user.email, subject, body)
    return True


async def confirm_email_verification(db: AsyncSession, raw_token: str) -> User:
    hashed = hash_token(raw_token)
    row = (
        await db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hashed)
        )
    ).scalar_one_or_none()
    now = _now()
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ValueError("invalid_or_expired_token")

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalars().first()
    if user is None:
        raise ValueError("invalid_or_expired_token")

    row.used_at = now
    user.email_verified_at = now
    db.add(row)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Password reset                                                               #
# --------------------------------------------------------------------------- #
async def request_password_reset(db: AsyncSession, email: str) -> bool:
    """Issue (and email) a reset link if the account exists; always silent."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        # No enumeration: silently report success from the endpoint side too.
        return True
    if not email_service.is_configured():
        return False
    if user.password_hash is None:
        # OAuth-only account has no password to reset.
        return False

    now = _now()
    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for token in existing.scalars().all():
        token.used_at = now
        db.add(token)

    raw = new_raw_token()
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=_expires(settings.password_reset_token_ttl_minutes),
    )
    db.add(row)
    await db.commit()

    link = f"{settings.frontend_base_url}/reset.html?token={raw}"
    subject = "Reset your StudyMate AI password"
    body = (
        "We received a request to reset the password for this account.\n\n"
        f"Reset link: {link}\n\n"
        f"This link expires in {settings.password_reset_token_ttl_minutes} minutes. "
        "If you did not request this, you can ignore this message — your password "
        "will not change without it.\n"
    )
    await email_service.send_email(user.email, subject, body)
    return True


async def confirm_password_reset(db: AsyncSession, raw_token: str, new_password: str) -> User:
    hashed = hash_token(raw_token)
    row = (
        await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hashed)
        )
    ).scalar_one_or_none()
    now = _now()
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ValueError("invalid_or_expired_token")

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalars().first()
    if user is None:
        raise ValueError("invalid_or_expired_token")

    row.used_at = now
    user.password_hash = get_password_hash(new_password)
    db.add(row)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Google OAuth (opt-in)                                                        #
# --------------------------------------------------------------------------- #
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_oauth_enabled() -> bool:
    return bool(settings.google_oauth_enabled)


def create_oauth_state() -> str:
    """Short-lived signed state value (no server-side storage needed)."""
    payload = {
        "purpose": "google_oauth",
        "nonce": new_raw_token(),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=settings.oauth_state_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_oauth_state(state: str) -> None:
    try:
        decoded = jwt.decode(state, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise ValueError("invalid_state")
    if decoded.get("purpose") != "google_oauth":
        raise ValueError("invalid_state")


def build_google_authorization_url() -> str:
    from urllib.parse import urlencode

    state = create_oauth_state()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_google_code(code: str, *, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Exchange an authorization code for userinfo. Raises ValueError on any
    failure so the endpoint can return a clean error without leaking details."""
    if not google_oauth_enabled():
        raise ValueError("oauth_disabled")
    async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        try:
            token_resp.raise_for_status()
        except httpx.HTTPStatusError:
            raise ValueError("token_exchange_failed")
        access_token = (token_resp.json() or {}).get("access_token")
        if not access_token:
            raise ValueError("no_access_token")

        info_resp = await client.get(
            GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        try:
            info_resp.raise_for_status()
        except httpx.HTTPStatusError:
            raise ValueError("userinfo_failed")
        info = info_resp.json() or {}
    if not info.get("sub"):
        raise ValueError("invalid_userinfo")
    return info


async def google_find_or_create_user(db: AsyncSession, info: dict) -> User:
    provider_user_id = str(info["sub"])
    email = (info.get("email") or "").strip() or None

    # Link by existing oauth identity first.
    row = (
        await db.execute(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == "google",
                OAuthIdentity.provider_user_id == provider_user_id,
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        user = await db.get(User, row.user_id)
        if user is not None:
            # Mark verified if google reports a verified address.
            if email and user.email_verified_at is None and info.get("email_verified"):
                user.email_verified_at = datetime.now(timezone.utc)
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user

    # Or by email, to avoid creating a duplicate account.
    if email:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None:
            link = OAuthIdentity(
                user_id=user.id,
                provider="google",
                provider_user_id=provider_user_id,
                email=email,
            )
            db.add(link)
            if user.email_verified_at is None and info.get("email_verified"):
                user.email_verified_at = datetime.now(timezone.utc)
                db.add(user)
            await db.commit()
            await db.refresh(user)
            return user

    # Create a new (password-less) account.
    name = (info.get("name") or info.get("given_name") or (email or "").split("@")[0] or "Google user").strip()
    if not name:
        name = "Google user"
    user = User(
        name=name,
        email=email or f"google-{provider_user_id}@example.invalid",
        password_hash=None,
        display_name=name,
        email_verified_at=(datetime.now(timezone.utc) if info.get("email_verified") else None),
    )
    db.add(user)
    await db.flush()
    link = OAuthIdentity(
        user_id=user.id,
        provider="google",
        provider_user_id=provider_user_id,
        email=email,
    )
    db.add(link)
    await db.commit()
    await db.refresh(user)
    return user
