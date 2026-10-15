
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    EmailVerifyConfirmRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    ProviderStatusResponse,
    Token,
    UserCreate,
    UserResponse,
)
from app.services import auth as auth_service
from app.services.auth_tokens import (
    build_google_authorization_url,
    confirm_email_verification,
    confirm_password_reset,
    exchange_google_code,
    google_find_or_create_user,
    request_email_verification,
    request_password_reset,
    verify_oauth_state,
)

router = APIRouter()
settings = get_settings()


# --------------------------------------------------------------------------- #
# Existing (password) auth                                                     #
# --------------------------------------------------------------------------- #
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth"))],
)
async def signup(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=auth_service.get_password_hash(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/signin",
    response_model=Token,
    dependencies=[Depends(rate_limit("auth", 30))],
)
async def signin(login_in: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == login_in.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not auth_service.verify_password(
        login_in.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --------------------------------------------------------------------------- #
# Provider status (drives the login/signup UI buttons)                          #
# --------------------------------------------------------------------------- #
@router.get("/providers", response_model=ProviderStatusResponse)
async def auth_providers():
    return {
        "email_enabled": settings.email_enabled,
        "google_oauth_enabled": settings.google_oauth_enabled,
        "smtp_from": settings.smtp_from or None,
        "redirect_uri": settings.google_redirect_uri or None,
    }


# --------------------------------------------------------------------------- #
# Email verification                                                           #
# --------------------------------------------------------------------------- #
@router.post("/verify-email/request")
async def verify_email_request(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sent = await request_email_verification(db, current_user)
    return {
        "sent": sent,
        "email_enabled": settings.email_enabled,
        "email_verified": current_user.email_verified_at is not None,
    }


@router.post("/verify-email/confirm")
async def verify_email_confirm(
    body: EmailVerifyConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await confirm_email_verification(db, body.token)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="This verification link is invalid or has expired.",
        )
    return {"email_verified": True, "email": user.email}


# --------------------------------------------------------------------------- #
# Password reset                                                               #
# --------------------------------------------------------------------------- #
@router.post("/password-reset/request")
async def password_reset_request(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    # Always respond identically so the endpoint cannot be used to enumerate
    # which addresses have an account. Delivery failures are logged server-side.
    await request_password_reset(db, body.email.strip().lower())
    return {
        "message": "If an account exists for that address, a reset link has been sent.",
        "email_enabled": settings.email_enabled,
    }


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    body: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await confirm_password_reset(db, body.token, body.new_password)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="This reset link is invalid or has expired.",
        )
    return {"ok": True, "email": user.email}


# --------------------------------------------------------------------------- #
# Google OAuth                                                                 #
# --------------------------------------------------------------------------- #
@router.get("/google/start")
async def google_start():
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured on this server.",
        )
    url = build_google_authorization_url()
    return RedirectResponse(url=url, status_code=307)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    frontend = settings.frontend_base_url.rstrip("/")
    if error:
        return RedirectResponse(url=f"{frontend}/login.html?error=oauth_cancelled", status_code=303)
    if not code or not state:
        return RedirectResponse(url=f"{frontend}/login.html?error=missing_code", status_code=303)
    try:
        verify_oauth_state(state)
        info = await exchange_google_code(code)
        user = await google_find_or_create_user(db, info)
    except ValueError:
        return RedirectResponse(url=f"{frontend}/login.html?error=oauth_failed", status_code=303)

    access_token = auth_service.create_access_token(data={"sub": user.email})
    # The frontend reads the token from the query string and clears it from the
    # address bar immediately. HTTPS only in deployed environments.
    return RedirectResponse(
        url=f"{frontend}/login.html?token={access_token}&token_type=bearer",
        status_code=303,
    )