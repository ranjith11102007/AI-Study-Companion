from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    email: str
    password: str


# --- Phase 10: verification, reset, OAuth ---------------------------------

class EmailVerifyConfirmRequest(BaseModel):
    token: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str

class ProviderStatusResponse(BaseModel):
    email_enabled: bool
    google_oauth_enabled: bool
    smtp_from: str | None = None
    redirect_uri: str | None = None
