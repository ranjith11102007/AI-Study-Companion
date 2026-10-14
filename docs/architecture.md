# Architecture

StudyMate AI is a **local-first** AI study companion. By default all inference
runs on the user's machine through [Ollama](https://ollama.com) — no cloud AI
calls and no paid APIs. The model layer is a swappable seam, so an *optional*
hosted deployment can instead point at any OpenAI-compatible API
(`CHAT_PROVIDER=openai`; see `docs/deployment.md`) — but nothing leaves the
machine with the default configuration. Persistence is PostgreSQL with the
`pgvector` extension.

```
Browser (static SPA at /)
        │  fetch  /api/...
        ▼
FastAPI (backend/app)
  ├── api/v1/endpoints   HTTP surface (auth, courses, materials, tutor,
  │                      assessments, learner, topics, providers, evaluation)
  ├── services           business logic (materials, retrieval, tutor, citations,
  │                      assessments, learner, topics, providers, evaluation)
  ├── ingestion          extraction (PDF/PPTX/image/text) → chunking → embeddings
  ├── ai                 provider interfaces (Ollama + OpenAI-compatible)
  ├── models             SQLAlchemy ORM (async)
  └── core               settings, logging, rate limiting
        │  asyncpg + SQLAlchemy 2.0
        ▼
PostgreSQL + pgvector
        │  HTTP
        ▼
Ollama  (chat: llama3.2, embeddings: nomic-embed-text)
        — or — any OpenAI-compatible API when hosted (CHAT_PROVIDER=openai)
```

## Backend

- **FastAPI** mounted with the router under `settings.api_prefix` (`/api`).
- **SQLAlchemy 2.0 async** over `asyncpg`. One engine/session factory in
  `app/db/session.py`; a per-request session via the `get_db` dependency.
- **Alembic** migrations in `backend/alembic/versions`. Head:
  `0003_material_error`.
- **Auth** is stateless JWT (`python-jose`) with bcrypt password hashing
  (`passlib`). `get_current_user` resolves the bearer token to a `User`.
  Every course/material/assessment query is filtered by `user_id`.
- **Tutor answers** have two delivery shapes with identical grounding and
  persistence (`app/services/tutor.py`): `POST /api/tutor/ask` returns one JSON
  object, while `POST /api/tutor/ask/stream` returns SSE
  (`status → sources → token* → done`). Provider outages surface as a `503`
  (streamed as an `error` event), and a course with no indexed vectors returns an
  honest `insufficient` answer **without** calling the model.

### Data model (head schema)

| Table | Purpose |
| ----- | ------- |
| `users` | accounts (bcrypt hash) |
| `courses` | user-owned courses |
| `learning_materials` | uploaded files + processing status + last error reason |
| `content_units` | source-preserving chunks (page/slide/timestamp metadata) |
| `content_embeddings` | 768-dim vectors, HNSW cosine index |
| `topics`, `content_unit_topics` | editable knowledge graph over sources |
| `conversations`, `messages` | tutor history with citations (JSONB) |
| `assessments`, `questions` | generated, validated questions |
| `attempts`, `assessment_responses` | learner answers + grading |
| `topic_mastery` | per-student BKT mastery estimate |
| `recommendations` | generated study recommendations |
| `evaluation_runs` | stored evaluation harness results |

### Ingestion pipeline

`app/ingestion/pipeline.py::process_material` runs as a FastAPI background task
with its own DB session:

1. Any chunks from a previous run are deleted first, so re-indexing a material
   (via `POST /api/materials/{id}/reprocess`) never duplicates content.
2. `extractors.extract_units` turns the file into `ExtractedUnit`s.
   - PDF → text layer via `pypdf` (one unit per page, preserving `page_number`).
   - PPTX → slide text + speaker notes via `python-pptx` (one unit per slide,
     preserving `slide_number`).
   - image → OCR via Tesseract (when available).
   - `txt`/`md` → single/few units.
3. `chunking.chunk_text` **sanitizes** each unit — NUL bytes (`0x00`) and other
   control characters PostgreSQL rejects are stripped — then splits long text
   into overlapping chunks.
4. `ai.get_embedding_provider().embed(...)` embeds each chunk; rows are written
   to `content_units` + `content_embeddings`.
5. Status moves `pending → processing → ready`, or `failed` with a short,
   user-safe reason stored in `learning_materials.processing_error` (migration
   `0003`) and shown in the UI. Failures never crash the API.

## AI layer

`app/ai/base.py` defines `ChatModelProvider` and `EmbeddingProvider`. Two
implementations exist behind those interfaces:

- `app/ai/ollama.py` — the **default**, talking to a local Ollama HTTP API.
- `app/ai/openai_compat.py` — any OpenAI-compatible API (OpenAI, Groq,
  OpenRouter, Gemini, LM Studio, llamafile, vLLM), used for hosted deployments.

`get_chat_provider()` / `get_embedding_provider()` (in `app/ai/ollama.py`, also
re-exported from `app/ai/__init__.py`) pick one at runtime from
`CHAT_PROVIDER` / `EMBEDDING_PROVIDER`. Business logic only depends on the
interfaces, which is what makes the deterministic tests possible (fakes are
injected in `backend/tests`) and what lets the same code run locally or hosted.

## Frontend

Static HTML/CSS/JS served by FastAPI (`StaticFiles`). `frontend/js/api.js` is the
only place that talks to the API. Pages degrade to honest empty/error states
when the backend or a provider is unavailable.

## Configuration

`app/core/config.py` (pydantic-settings, prefix-free, `.env`). Notable settings:
the AI provider (`chat_provider` / `embedding_provider` = `ollama` or `openai`,
plus `openai_base_url` / `openai_api_key` / `openai_chat_model` /
`openai_embed_model`), Ollama URL/models, embedding dimension (must match the DB
column, 768), retrieval `top_k`/`min_score`, tutor context/token limits,
assessment limits, BKT parameters, and rate limits. `normalize_database_url`
coerces libpq URLs to `asyncpg` and requires SSL for managed hosts.

## Evaluation

`app/services/evaluation.py` is a deterministic, offline harness over a small
original dataset (`backend/evaluation/dataset.json`). It measures retrieval
hit@k, context precision/recall, citation correctness, unsupported-question
detection and learner-model trajectories. See `docs/evaluation.md`.
