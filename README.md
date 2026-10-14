# AI Study Companion

A **local-first, free & open-source** AI study companion for personalized tutoring and adaptive
learning.

It turns your own study material into a searchable knowledge base, answers questions with
**source-grounded citations**, generates adaptive assessments, tracks mastery, finds weak topics
and recommends what to study next.

**Local-first and free by default: no paid APIs, no cloud AI — the models run on your own machine
(Ollama).** An *optional* hosted deployment ("143") can instead point the same code at any
**OpenAI-compatible** endpoint (a free Gemini/Groq tier) without rewriting anything; the default
configuration makes **zero** external AI calls. See [`docs/deployment.md`](docs/deployment.md).

---

## Status at a glance

| Capability | State |
| ---------- | ----- |
| FastAPI backend, async PostgreSQL, migrations | ✅ Working |
| JWT authentication (signup / signin, bcrypt-hashed passwords) | ✅ Working |
| Courses CRUD (per-user, isolated) | ✅ Working |
| Material ingestion — **PDF, images (OCR), text / Markdown** | ✅ Working |
| Chunking + local embeddings (`pgvector`) + live indexing status | ✅ Working |
| Source-grounded tutor with real citations (`/api/tutor`, `/api/citations`) | ✅ Working |
| Streaming tutor answers (SSE, `/api/tutor/ask/stream`) | ✅ Working |
| Adaptive assessments, validation & grading (`/api/assessments`, `/api/attempts`) | ✅ Working |
| Mastery tracking (BKT), weak topics, recommendations (`/api/courses/{id}/mastery`) | ✅ Working |
| Provider / readiness status (`/api/providers/status`, `/api/health/ready`) | ✅ Working |
| Deterministic offline evaluation harness (`/api/evaluate`) | ✅ Working |
| PPTX ingestion (slide text + speaker notes) | ✅ Working |
| Lecture-video ingestion (Whisper) | ⬜ Planned |
| Claim-level answer verification (NLI / reranker) | ⬜ Planned |

The frontend is a static app served by FastAPI at the **site root**
(<http://127.0.0.1:8000/>; old `/ui` links redirect there). Pages talk to the real
endpoints — including the **streaming** tutor with live retrieval status — and features
that do not exist yet (lecture video, flashcards) are labelled as such. Short-answer
questions are auto-graded with a transparent keyword heuristic and clearly marked
**not machine-verified**; the app never shows fabricated answers, citations or scores.

---

## Tech stack

| Layer | Technology |
| ----- | ---------- |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | PostgreSQL + **pgvector** (Supabase free tier, or local Docker) |
| ORM / migrations | SQLAlchemy 2 (async), asyncpg, Alembic |
| Auth | `python-jose` (JWT), `passlib[bcrypt]` |
| LLM | Ollama (`llama3.2:3b`) by default — or any OpenAI-compatible API (`CHAT_PROVIDER=openai`) |
| Embeddings | Ollama (`nomic-embed-text`, 768-dim) by default — or an OpenAI-compatible API |
| Ingestion | `pypdf` (PDF), `python-pptx` (PPTX), `pytesseract` + Pillow (OCR), plain text / Markdown |
| Frontend | Plain HTML / CSS / JavaScript (no build step) |
| Tests / lint | pytest, pytest-asyncio, pytest-rerunfailures, Ruff |

---

## Project structure

```
AI-Study-Companion/
├── backend/
│   ├── alembic/                 # migration environment + versions
│   ├── app/
│   │   ├── api/v1/endpoints/    # health, auth, courses, materials
│   │   ├── core/                # config (.env), logging
│   │   ├── db/                  # async engine, sessions, declarative base
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # business logic (auth, courses, materials)
│   │   ├── ai/                  # swappable AI providers (Ollama / OpenAI-compatible)
│   │   ├── ingestion/           # extractors, chunking, pipeline
│   │   └── main.py              # FastAPI app factory + router mounting
│   ├── tests/                   # pytest suite
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/                    # static HTML/CSS/JS (served by FastAPI at /)
├── data/                        # uploads/, processed/, logs/ (git-ignored)
├── models/                      # local model files (git-ignored)
├── scripts/                     # helper scripts
├── docker-compose.yml           # optional local PostgreSQL + pgvector
├── Dockerfile                   # hosted image (API + static frontend)
├── render.yaml                  # free Render Blueprint (the "143" plan)
└── README.md
```

---

## Prerequisites

1. **Python 3.11+** — [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.11`
2. **Ollama** — [ollama.com/download](https://ollama.com/download/) (needed for embeddings and the
   tutor **in the default local setup**). Hosted deployments don't install Ollama — they set
   `CHAT_PROVIDER=openai` and use a free OpenAI-compatible API instead (see
   [`docs/deployment.md`](docs/deployment.md)).
3. **Tesseract OCR** — required for image ingestion:
   `winget install UB-Mannheim.TesseractOCR`
4. **A PostgreSQL + pgvector database** — either a free **Supabase** project (recommended) or
   local **Docker Desktop**.

---

## 1. Get the code and configure

```powershell
cd AI-Study-Companion
copy backend\.env.example backend\.env
```

Edit `backend\.env` and set `DATABASE_URL` to **your own** database. The example file contains
placeholders only — never commit real secrets.

## 2. Set up the database

**Option A — Supabase (recommended, no Docker):**

1. Create a free project at [supabase.com](https://supabase.com).
2. Enable pgvector: run `create extension if not exists vector;` in the SQL editor.
3. Copy the connection string from **Settings → Database → Connection string**.
   Use the **Session pooler** URI (IPv4) on port `5432`, e.g.:

   ```
   DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

   The app automatically rewrites `postgresql://` → `postgresql+asyncpg://`, `sslmode` → `ssl`,
   and forces SSL for Supabase hosts.

**Option B — Local Docker:**

```powershell
docker compose up -d
docker compose ps          # should show "healthy"
```

Then set:

```
DATABASE_URL=postgresql+asyncpg://studymate:studymate@127.0.0.1:5432/studymate
```

## 3. Create a virtual environment and install dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(With [uv](https://github.com/astral-sh/uv): `uv venv --python 3.11` then
`uv pip install -r requirements.txt`.)

## 4. Apply database migrations

```powershell
alembic upgrade head
```

This creates the `users`, `courses`, `learning_materials`, `content_units` and
`content_embeddings` tables (and the pgvector index). Later migrations add the tutor/assessment
tables and the `learning_materials.processing_error` column, so re-run `alembic upgrade head`
after pulling changes.

## 5. Pull the local AI models

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Model names are configured in `backend\.env` (`OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`) and all
model access goes through the provider interfaces in `backend/app/ai/`, so runtimes can be swapped
without touching application code.

> **The configured tag must match a model you actually pulled.** `OLLAMA_CHAT_MODEL=llama3.2:3b`
> expects the `3b` tag; `llama3.2` (no tag) means `llama3.2:latest`, a different download. A
> mismatch makes the tutor and assessment generation fail with a "model not found" error — pull the
> exact tag, or point `OLLAMA_CHAT_MODEL` at the one you have. Ollama must also be **running**
> (launch the app, or `ollama serve`) or ingestion and the tutor will refuse to work.

## 6. Run the backend

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Always run uvicorn **from inside the `backend/` folder** so the `app` package is importable.

## 7. Verify it works

| What | URL |
| ---- | --- |
| Health endpoint | <http://127.0.0.1:8000/api/health> |
| Interactive API docs | <http://127.0.0.1:8000/docs> |
| Frontend (served by FastAPI) | <http://127.0.0.1:8000/> |
| Upload page | <http://127.0.0.1:8000/upload.html> |

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

```json
{
  "service": "AI Study Companion",
  "version": "0.1.0",
  "environment": "development",
  "status": "ok",
  "timestamp": "2026-10-12T15:00:00Z",
  "database": { "status": "connected", "latency_ms": 6.0, "detail": null }
}
```

If the database is unreachable the endpoint still returns HTTP `200` with `status: "degraded"`
and a sanitized message (no driver details leaked).

## 8. Using the app

1. Open <http://127.0.0.1:8000/> — the **landing page** — then **Create account** or **Sign in**.
2. Create a **course**.
3. Go to **Upload materials**, pick the course, and drop a supported file:
   **`.pdf`, `.pptx`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.txt`, `.md`**.
4. Click **Upload & index**. The queue shows `Pending → Indexing → Indexed`, and the number of
   indexed chunks, as the backend extracts → chunks → embeds the content in the background.
   If a file shows **Failed**, the actual reason appears under it (and on the course page), with a
   **Retry** button that re-runs indexing — you don't have to delete and re-upload.

> Supported today: **PDF** (text layer), **PowerPoint `.pptx`** (slide text + speaker notes),
> **images** (OCR), and **text / Markdown**.
> Scanned PDFs have no text layer — export them as images, or the upload reports a clear error.

## API endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/health` | Service + database health |
| POST | `/api/auth/signup` | Create an account |
| POST | `/api/auth/signin` | Obtain a JWT access token |
| GET | `/api/courses` | List the current user's courses |
| POST | `/api/courses` | Create a course |
| GET / PATCH / DELETE | `/api/courses/{id}` | Read / update / delete a course |
| POST | `/api/courses/{id}/materials` | Upload a material (multipart `file`) |
| GET | `/api/courses/{id}/materials` | List a course's materials + status |
| GET / DELETE | `/api/materials/{id}` | Read status / delete a material |
| POST | `/api/materials/{id}/reprocess` | Re-run extraction + indexing for an existing material |
| POST | `/api/tutor/ask` | Source-grounded answer (JSON) |
| POST | `/api/tutor/ask/stream` | Same answer streamed as SSE: `status` → `sources` → `token`* → `done` |
| GET | `/api/tutor/conversations` | List conversations for a course |
| GET / DELETE | `/api/tutor/conversations/{id}` | Read / delete one conversation |
| GET | `/api/citations/{content_unit_id}` | Resolve a citation to its stored source text (owner-scoped) |
| POST | `/api/assessments` | Generate an assessment from indexed material |
| GET | `/api/assessments` | List assessments for a course |
| POST | `/api/attempts` | Start an attempt |
| POST | `/api/attempts/{id}/submit` | Submit + grade an attempt |
| GET | `/api/courses/{id}/mastery` | Per-topic mastery (BKT) for the user |
| GET | `/api/courses/{id}/recommendations` | Study recommendations |
| GET / POST | `/api/courses/{id}/topics` | List / create topics and prerequisites |
| POST | `/api/evaluate` | Run the deterministic offline evaluation harness |
| GET | `/api/providers/status` | Dependency health (database, pgvector, AI provider, ocr, office, storage) |
| GET | `/api/health/live`, `/api/health/ready` | Liveness + readiness probes |

> `POST /api/tutor/ask/stream` returns `text/event-stream`; each event is
> `data: {json}` with a `type` of `status | sources | token | done | error`. Provider
> outages surface as `{"type":"error","status":503,...}` rather than a raw 500, and a
> course with no indexed material returns an honest `insufficient` answer.

All `/api/courses` and `/api/materials` routes require `Authorization: Bearer <token>` and are
scoped to the authenticated user.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Upload finishes but the material shows **Failed** | Ollama isn't running, or the embedding call failed | Start Ollama (`ollama serve`), then use **Retry** on the material |
| Tutor or assessment generation fails / "model not found" | `OLLAMA_CHAT_MODEL` tag not pulled | `ollama pull llama3.2:3b`, or set `OLLAMA_CHAT_MODEL` to the tag you have |
| Tutor answers say "insufficient evidence" | The course has no *indexed* material yet, or the question is off-topic | Wait for indexing to finish; ask something covered by your sources |
| **Failed** reason mentions characters/encoding | The source contained characters PostgreSQL rejects (e.g. NUL) | Fixed automatically since migration `0003`; re-run indexing |
| `/api/providers/status` shows `degraded` | A local dependency (Ollama, OCR, pgvector) is missing | Read the `detail` field per provider |

## 9. Run tests and lint

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
ruff check .
```

---

## Deployment (optional, free)

The default setup is fully local. If you want a **hosted** copy, the same code runs against a
managed Postgres + a free OpenAI-compatible API — no source changes, just environment variables:

```powershell
# Local Docker test of the hosted configuration
docker build -t studymate .
docker run --rm -p 8000:8000 --env-file backend/.env.production studymate
```

- [`Dockerfile`](Dockerfile) — one image serving the API and the static frontend.
- [`render.yaml`](render.yaml) — a free **Render** Blueprint (Render builds the Dockerfile).
- [`backend/.env.production.example`](backend/.env.production.example) — the hosted env template.
- Full walkthrough, free-stack table and honest limitations: [`docs/deployment.md`](docs/deployment.md).

> Hosting means prompts and passages leave your machine (they go to the AI provider's API), and the
> free instance sleeps (30–60 s cold starts) with ephemeral upload storage. The local setup has none
> of those caveats.

---

## Design principles

- **Local-first & free** — open-source tools only; no API keys, no cloud AI bills by default.
- **Modular AI layer** — the LLM and embedding runtime sit behind interfaces, so the app runs on
  Ollama locally *or* any OpenAI-compatible API (Gemini/Groq/OpenRouter/llamafile/vLLM) when
  hosted, with no rewriting of application code.
- **Source-grounded by construction** — every generated answer must carry retrievable citations
  (page number, slide number, or video timestamp).
- **Per-user isolation** — every course and material is owned by exactly one user and verified
  on each request.
- **No build step** — the frontend is plain HTML/CSS/JS served directly by FastAPI.

---

## Roadmap

1. ✅ Backend foundation (config, logging, async DB, health, Alembic)
2. ✅ Authentication (JWT) and per-user course management
3. ✅ Ingestion: PDF, PPTX (slides + notes), image OCR, and text/Markdown → chunk → embed → `pgvector`
4. ✅ Materials upload UI with live indexing status
5. ✅ Topics / concepts / prerequisites (heuristic suggestions + editable graph)
6. ✅ Source-grounded tutor (retrieval + page/slide/timestamp citations)
7. ✅ Adaptive assessments with validation, grading and explanations
8. ✅ Mastery tracking (BKT), weak topics, recommendations
9. ✅ Deterministic offline evaluation harness (RAG-style metrics)
10. ✅ Frontend wired to the real APIs (simple auth gateway at the site root)
11. ✅ Streaming tutor answers (SSE) with live retrieval status
12. ✅ Simple sign-in / create-account gateway served at the site root
13. ✅ PPTX ingestion (slide text + speaker notes)
14. ⬜ Lecture-video ingestion (Whisper)
15. ⬜ Claim-level answer verification (reranker + optional local NLI)

> Deliberately **not** implemented (documented as limitations, never faked):
> scanned-PDF OCR, audio/video transcription, diagram/table extraction, and
> machine-verified free-text grading.
