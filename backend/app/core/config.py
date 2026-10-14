from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "super-secret-key-change-in-production"

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def normalize_database_url(url: str) -> str:
    """Make a libpq-style URL safe for SQLAlchemy + asyncpg.

    - Forces the ``postgresql+asyncpg://`` driver prefix.
    - Translates libpq ``sslmode=`` into the asyncpg ``ssl=`` parameter.
    - Requires SSL for managed cloud hosts (Neon ``*.neon.tech`` and
      Supabase ``*.supabase.co`` / ``*.supabase.com``).
    - Drops ``channel_binding`` (libpq-only, unsupported by asyncpg).

    Local URLs are returned unchanged.
    """
    if not url:
        return url
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = {
            "disable": "disable",
            "allow": "require",
            "prefer": "require",
            "require": "require",
            "verify-ca": "verify-ca",
            "verify-full": "verify-full",
        }.get(sslmode, "require")

    host = parts.hostname or ""
    cloud_suffixes = (".neon.tech", ".supabase.co", ".supabase.com")
    if host.endswith(cloud_suffixes) and "ssl" not in query:
        query["ssl"] = "require"

    query.pop("channel_binding", None)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "AI Study Companion"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "*"

    # PostgreSQL + pgvector (local database name: studymate)
    database_url: str = (
        "postgresql+asyncpg://studymate:studymate@127.0.0.1:5432/studymate"
    )
    db_echo: bool = False
    db_connect_timeout_seconds: int = 3

    # Local AI (Ollama) - swapped without touching application code
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

    # AI runtime selection. "ollama" = local server (default, local-first);
    # "openai" = any OpenAI-compatible HTTP API (OpenAI, Groq, OpenRouter,
    # Google Gemini's /openai endpoint, LM Studio, llamafile, vLLM). Hosting has
    # no local Ollama, so a free host sets these to "openai".
    chat_provider: str = "ollama"
    embedding_provider: str = "ollama"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    # Only used to force the size for OpenAI text-embedding-3-* (0 = don't send).
    openai_embed_dimension: int = 0
    openai_timeout_seconds: float = 120.0

    # Auth
    secret_key: str = DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Retrieval-augmented tutoring (all local, via Ollama)
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.15
    retrieval_candidate_k: int = 20
    tutor_max_context_chars: int = 6000
    tutor_temperature: float = 0.1
    tutor_max_tokens: int = 700
    tutor_excerpt_chars: int = 320

    # Assessment engine
    assessment_max_questions: int = 20
    assessment_numeric_tolerance: float = 0.01

    # Learner model (Bayesian Knowledge Tracing; documented in docs/learner-model.md)
    bkt_prior_learned: float = 0.3
    bkt_learn_rate: float = 0.2
    bkt_guess: float = 0.2
    bkt_slip: float = 0.1
    bkt_mastery_threshold: float = 0.7

    # Simple in-process rate limiting for auth + LLM endpoints
    rate_limit_enabled: bool = True
    auth_rate_limit_per_minute: int = 30
    llm_rate_limit_per_minute: int = 60

    # Provider health probes
    provider_health_timeout_seconds: float = 5.0

    # Ingestion (PDF + PPTX + images + text; OCR uses the local Tesseract engine)
    allowed_material_extensions: str = "pdf,pptx,png,jpg,jpeg,webp,txt,md"
    max_upload_size_mb: int = 15
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    # Optional explicit path to tesseract.exe; empty = rely on PATH.
    tesseract_cmd: str = ""
    chunk_size: int = 900
    chunk_overlap: int = 150

    # Filesystem
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    log_dir: Path = PROJECT_ROOT / "data" / "logs"
    models_dir: Path = PROJECT_ROOT / "models"
    frontend_dir: Path = PROJECT_ROOT / "frontend"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def allowed_extension_set(self) -> set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.allowed_material_extensions.split(",")
            if ext.strip()
        }

    @field_validator("embedding_dimension")
    @classmethod
    def _positive_dimension(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be positive")
        return value

    @model_validator(mode="after")
    def _reject_insecure_secret_in_non_dev(self) -> "Settings":
        if self.app_env.lower() not in {"development", "dev", "test", "testing"}:
            if self.secret_key == DEFAULT_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong unique value outside development."
                )
        return self

    @property
    def is_insecure_secret(self) -> bool:
        return self.secret_key == DEFAULT_SECRET


@lru_cache
def get_settings() -> Settings:
    return Settings()
