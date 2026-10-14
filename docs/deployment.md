# Deployment & Running Locally

## Prerequisites

- Windows 10/11, Python 3.11+, PowerShell.
- PostgreSQL 15+ with **pgvector**, or a managed Postgres (Supabase/Neon) — the
  default `.env.example` guidance targets Supabase's connection pooler.
- [Ollama](https://ollama.com) running locally.
- Optional: Tesseract OCR (image ingestion), Docker Desktop (local Postgres).

## 1. Database

Either use Docker:

```powershell
docker compose up -d db        # PostgreSQL + pgvector on :5432
```

…or point `DATABASE_URL` at Supabase/Neon. `normalize_database_url` enables SSL
automatically for `*.supabase.co` / `*.neon.tech` and converts `sslmode=` to
`ssl=`. Make sure the `vector` extension can be created (it is, by migration
`0001`).

## 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # + requirements-dev.txt for tests
Copy-Item .env.example .env              # then edit DATABASE_URL / SECRET_KEY
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>
- Readiness (all deps): <http://127.0.0.1:8000/api/health/ready>
- Frontend: <http://127.0.0.1:8000/> (`/ui` redirects here)

## 3. Local models

```powershell
ollama serve
ollama pull llama3.2          # chat     (settings.ollama_chat_model)
ollama pull nomic-embed-text  # embeddings (settings.ollama_embed_model, 768-dim)
```

`GET /api/providers/status` reports whether Ollama, the DB, pgvector, OCR and
storage are available. Missing models show as `degraded`.

## 4. OCR (optional)

```powershell
winget install UB-Mannheim.TesseractOCR
```

Set `TESSERACT_CMD` if Tesseract is not on `PATH`. Without it, image ingestion
returns a clear error; everything else works.

## Environment variables

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | Postgres/pgvector connection (required) |
| `SECRET_KEY` | JWT signing key (**required**, ≥32 chars, outside dev) |
| `APP_ENV` | `development` / `production` (gates the secret-key check) |
| `CHAT_PROVIDER`, `EMBEDDING_PROVIDER` | `ollama` (default, local) or `openai` (any OpenAI-compatible API) |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBED_MODEL` | used when a provider is `openai` |
| `OPENAI_EMBED_DIMENSION` | only for OpenAI `text-embedding-3-*` (0 = don't send) |
| `OLLAMA_BASE_URL` | default `http://127.0.0.1:11434` |
| `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL` | model names |
| `EMBEDDING_DIMENSION` | must equal the DB vector dimension (768) |
| `RETRIEVAL_TOP_K`, `RETRIEVAL_MIN_SCORE` | retrieval tuning |
| `TUTOR_MAX_CONTEXT_CHARS`, `TUTOR_MAX_TOKENS`, `TUTOR_TEMPERATURE` | generation limits |
| `ALLOWED_MATERIAL_EXTENSIONS`, `MAX_UPLOAD_SIZE_MB` | upload policy |
| `CORS_ORIGINS` | comma-separated origins (set explicitly in production) |
| `RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT_PER_MINUTE`, `LLM_RATE_LIMIT_PER_MINUTE` | rate limiting |


## Production checklist

- Set `APP_ENV=production` and a strong unique `SECRET_KEY` (startup fails
  otherwise).
- Set `CORS_ORIGINS` to your real frontend origin(s); never `*`.
- Run behind a TLS-terminating reverse proxy; the app itself speaks HTTP.
- Run Alembic migrations as a release step, then start uvicorn (use multiple
  workers if desired; the in-process rate limiter is then per-worker).
- Back up the database; uploaded files live in `uploads/` (back it up too).
- Ollama must be reachable by the backend host.

## Migrations

```powershell
.\.venv\Scripts\alembic.exe upgrade head     # apply
.\.venv\Scripts\alembic.exe downgrade -1     # roll back one revision
```

Current head: `0003_material_error` (adds `learning_materials.processing_error`).
Migration `0002_learning_features` adds conversations/messages, assessments/
questions/attempts/responses, topic_mastery, recommendations, evaluation_runs.
Both are additive only.

---

## Deploy to a free host (the "143" plan)

**What runs where.** The app is one process: FastAPI serves the API *and* the
static frontend, and talks to a managed Postgres over the network. A free host
has no GPU and no Ollama, so hosting changes the **AI runtime only** — the same
code talks to a free OpenAI-compatible API instead of a local server. Locally
nothing changes (Ollama stays the default).

| Piece | Free option | Notes |
| ----- | ----------- | ----- |
| Host (API + frontend) | **Render** free web service (Docker) | 512 MB RAM, sleeps after ~15 min idle → 30–60 s cold start |
| Database | **Supabase** or **Neon** free Postgres + pgvector | you already use Supabase — reuse it |
| Chat AI | **Google Gemini** (`gemini-2.0-flash`) free tier | OpenAI-compatible endpoint; no paid API |
| Embeddings | **Google Gemini** `text-embedding-004` | 768-dim, matches the existing vector column |
| File storage | container disk (**ephemeral**) | uploads are lost on redeploy — see limitations |

> **Trade-off, stated plainly:** a hosted app is no longer "local-first /
> private". Prompts and document passages leave your machine and go to the AI
> provider's API. If that is unacceptable, deploy only for yourself and keep
> using the local Ollama path, or run the Docker image on your own machine.

### Steps

1. **Database.** In Supabase (or Neon), run `create extension if not exists vector;`
   and copy the pooled `DATABASE_URL` (see §1). Reuse the DB you already have.
2. **AI key.** Create a free key at Google AI Studio
   (<https://aistudio.google.com/app/apikey>) → this is `OPENAI_API_KEY`.
   (Groq also has a free tier for **chat**, but no embeddings; Gemini covers both.)
3. **Put the repo on GitHub.** The folder is already a git repo with an initial
   commit (`.env` is ignored). Create an **empty** repo on GitHub, then:

   ```powershell
   git remote add origin https://github.com/<you>/<repo>.git
   git branch -M main
   git push -u origin main
   ```
4. **Deploy on Render.** *New + → Blueprint* → choose the repo. Render reads
   [`render.yaml`](../render.yaml) and builds the [`Dockerfile`](../Dockerfile).
5. **Set the two secrets** in the Render dashboard when prompted:
   `DATABASE_URL` and `OPENAI_API_KEY`. `SECRET_KEY` is generated automatically.
6. **Wait for the first deploy.** Alembic migrations run automatically at start
   (`alembic upgrade head`). Health: `<https://<app>.onrender.com>/api/health/live`;
   readiness (all deps): `/api/health/ready`.

### Docker (any host, or local test of the hosted config)

```powershell
docker build -t studymate .
docker run --rm -p 8000:8000 --env-file backend/.env.production studymate
```

`backend/.env.production.example` is the template (copy to `.env.production`, fill
`DATABASE_URL` + `OPENAI_API_KEY`, never commit it).

### Hosted limitations (be honest about these)

- **Cold starts:** the free Render instance sleeps; the first request after idle
  takes 30–60 s.
- **Ephemeral uploads:** `data/uploads/` lives in the container. A redeploy or
  restart wipes uploaded files (the DB rows remain, but the file is gone → a
  material shows the "stored file is missing" reason). Persist to Supabase
  Storage / Cloudflare R2 before real use, or accept that uploads are transient.
- **Free-tier rate limits:** the Gemini free tier throttles requests; the tutor
  and assessment generation can hit `429`s under load.
- **Per-process rate limiting:** each host process has its own limiter.
- **PDF OCR** for scanned pages is still not implemented; PPTX/PDF/text/images
  are.
