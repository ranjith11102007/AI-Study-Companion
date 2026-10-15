from contextlib import asynccontextmanager
import mimetypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

# Python's mimetypes table does not always know .mjs, and a wrong content type
# makes the browser refuse the vendored PDF.js ES module. Register it before
# the static mount so the document viewer loads.
mimetypes.add_type("text/javascript", ".mjs")

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    for directory in (
        settings.upload_dir,
        settings.processed_dir,
        settings.log_dir,
        settings.models_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(
        "%s v%s starting (env=%s)", settings.app_name, settings.app_version, settings.app_env
    )
    yield
    logger.info("%s shutting down", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Local-first, open-source AI study companion: source-grounded tutoring, "
        "adaptive assessments and mastery tracking. Powered by Ollama + pgvector."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


if settings.frontend_dir.is_dir():
    # The web app is served at the site root, so users open http://host:port/
    # directly (no /ui/ in the address bar). Older links to /ui keep working.
    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    async def _ui_redirect() -> RedirectResponse:
        return RedirectResponse(url="/", status_code=307)

    # Mounted last so /api/*, /docs and /openapi.json keep priority.
    app.mount(
        "/",
        StaticFiles(directory=str(settings.frontend_dir), html=True),
        name="frontend",
    )
else:

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "health": f"{settings.api_prefix}/health",
            "docs": "/docs",
        }
