# AI Study Companion — hosted deployment image.
#
# The app is a single FastAPI process that also serves the static frontend
# (frontend/) and talks to a managed PostgreSQL + pgvector database
# (Supabase/Neon) over the network. AI runs through the configurable provider
# layer (Ollama locally, or any OpenAI-compatible API when hosted).
#
# Build context must be the repository root:
#   docker build -t studymate .
#   docker run --env-file backend/.env.production -p 8000:8000 studymate

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

# Tesseract enables image OCR ingestion; curl is used for a container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so Docker can cache this layer.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Application code + static frontend + docs. PROJECT_ROOT resolves to /app, so
# settings.frontend_dir (/app/frontend) and settings.upload_dir (/app/data/uploads)
# line up automatically.
COPY backend /app/backend
COPY frontend /app/frontend
COPY docs /app/docs

WORKDIR /app/backend

# Render/Railway/HF Spaces inject $PORT; default to 8000 for plain Docker.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health/live" || exit 1

# Apply migrations, then start the server bound to all interfaces.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
