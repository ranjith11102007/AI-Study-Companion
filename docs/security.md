# Security

This is a local-first app, but it still handles accounts, uploads and a database,
so the standard controls apply.

## Authentication & sessions

- Passwords are hashed with **bcrypt** (`passlib`); plaintext is never stored.
- `POST /api/auth/signin` issues a **JWT** (`python-jose`, HS256) whose `sub` is
  the user email. `get_current_user` validates the signature and loads the user;
  invalid/expired tokens get `401` with `WWW-Authenticate: Bearer`.
- Token lifetime is `access_token_expire_minutes` (default 30).

## Secret key

`SECRET_KEY` defaults to a placeholder. `Settings._reject_insecure_secret_in_non_dev`
**raises at startup** if `APP_ENV` is not `development`/`test` and the secret is
the default or shorter than 32 characters. Do not commit a real `.env`.

## Authorization / tenant isolation

Every resource query is filtered by the owning user:

- courses → `Course.user_id == user_id`;
- materials → joined through the owned course;
- tutor conversations, assessments, attempts, mastery, recommendations → scoped
  to `user_id` and/or the owned course;
- citations → `ContentUnit` joined to the owned `Course`.

Accessing another user's resource returns **`404`**, not `403`, so existence is
not leaked. This is exercised by tests
(`test_citations_are_owner_scoped`, `test_material_cross_user_access_returns_404`).

## Upload safety

- Extension allow-list (`allowed_material_extensions`, default
  `pdf,png,jpg,jpeg,webp,txt,md`).
- Size limit (`max_upload_size_mb`, default 25) enforced while streaming.
- Filenames are sanitised (`_safe_original_name`) and stored under a generated
  UUID name inside `uploads/`; the original name is only kept as metadata.
- Failed extraction marks the material `failed` with a safe message; the
  server-side traceback is logged, not returned.

## Rate limiting

A small in-process sliding-window limiter (`app/core/ratelimit.py`) guards auth
and LLM endpoints (`auth_rate_limit_per_minute`, `llm_rate_limit_per_minute`),
keyed by client IP (honouring `X-Forwarded-For`). It is intentionally simple and
**not** a distributed limiter — see limitations.

## Prompt injection

Retrieved document text is fenced in `<source>` blocks and the system prompt
states that content inside sources is untrusted and must never be interpreted as
instructions. This reduces, but does not eliminate, injection risk.

## CORS

`cors_origins` defaults to `*` for frictionless local use. **Set an explicit
origin list before exposing the API.**

## Not implemented (be aware)

- No MFA, no refresh tokens, no token revocation.
- Rate limiting is per-process and resets on restart.
- No audit log of data access.
- No encryption of uploaded files at rest (relies on OS/disk encryption).
- No dependency-vulnerability scanning in CI.
