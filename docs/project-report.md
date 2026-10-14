# Project Report — StudyMate AI (AI Study Companion)

## 1. Executive summary

StudyMate AI is a **local-first** AI tutoring and adaptive-learning web app. It
indexes a student's own course material and uses a **local** model (Ollama) to
answer questions **with citations back to real stored sources**, generate and
auto-grade assessments, and maintain a per-topic mastery model that drives study
recommendations. There are **no cloud or paid AI calls in the default
configuration**; all inference runs on the user's machine. (The AI layer is a
swappable seam, so an optional hosted deployment can use a free
OpenAI-compatible API instead — see `docs/deployment.md`.) Answers, citations,
scores and mastery values are computed from real stored data — the app never
returns canned or fabricated results, and it says "insufficient evidence" rather
than inventing an answer.

The existing repo already had authentication, courses, uploads and a
PDF/image/text ingestion pipeline into PostgreSQL + pgvector. This work
**extends** that base into a full tutoring/assessment/learner system without
rewriting what worked, and documents the honest boundaries of each feature.

## 2. Objectives

- Grounded tutoring over the user's indexed material, with real citations.
- Assessment generation (from sources) + deterministic grading.
- A learner model (Bayesian Knowledge Tracing) and study recommendations.
- Provider/readiness visibility and a deterministic evaluation harness.
- Keep everything local and free; no fabricated data; document limitations.

## 3. What was already present (preserved)

- FastAPI backend with JWT auth, course CRUD, file uploads.
- Ingestion: `pypdf` (PDF text layer), Tesseract OCR (images), txt/md; chunking;
  768-dim embeddings via `nomic-embed-text`; `pgvector` cosine index.
- Async SQLAlchemy + Alembic; pgvector; health endpoint.
- Static frontend shell (login, courses, upload, tutor, source, settings…).

## 4. What this work added

### 4.1 Grounded tutoring + citations
- `app/services/retrieval.py` — cosine search scoped to the course, similarity
  threshold, and `<source>`-fenced context building.
- `app/services/tutor.py` — retrieval → evidence check → local chat → parse the
  `SOURCES:`/inline markers → attach citations → persist conversation/messages.
  Returns `evidence_status = grounded | insufficient`.
- `app/services/citations.py` — resolve a citation to its stored content unit,
  owner-scoped.
- Endpoints: `POST /api/tutor/ask`, `POST /api/tutor/ask/stream` (SSE),
  `GET/DELETE /api/tutor/conversations…`, `GET /api/citations/{content_unit_id}`.
- See `docs/grounding-and-citations.md`.

### 4.2 Assessments: generation, validation, grading
- `app/services/assessments.py` — the local model drafts questions from the
  course's content units; a **validation layer** rejects malformed items
  (MCQ key not in options, non-numeric numeric, missing rubric/prompt), and
  de-duplicates by fingerprint. Questions carry `source_unit_ids` and a
  `verified` flag.
- Grading: MCQ exact, numeric within tolerance, short answer by a **transparent
  keyword-overlap heuristic** (clearly labelled; `verified = false`).
- Attempts: one submission, answer keys never leak while in progress.
- Endpoints: `POST/GET/DELETE /api/assessments…`,
  `POST /api/assessments/{id}/attempts`, `POST /api/attempts/{id}/submit`,
  `GET /api/attempts/{id}`.

### 4.3 Learner model + recommendations
- `app/services/learner.py` — BKT `bkt_update`, `record_evidence`, weak/strong/
  untested classification (weak needs `evidence_count ≥ 2`), recommendation
  generation (`weak_topic`, `diagnostic`, `revision`).
- Endpoints: `GET /api/courses/{id}/mastery`,
  `GET /api/courses/{id}/recommendations`.
- See `docs/learner-model.md`.

### 4.4 Topics / knowledge graph (heuristic)
- `app/services/topics.py` — heuristic topic suggestions from sources, topic
  CRUD, prerequisite setting with **cycle detection**, source attachment.
- Endpoints under `/api/courses/{id}/topics…`.

### 4.5 Provider health + evaluation harness
- `app/services/providers.py` — aggregates DB, pgvector, the configured AI
  provider (Ollama or OpenAI-compatible), OCR, office and storage
  status (ok / degraded / unavailable) → `GET /api/providers/status`; plus
  `GET /api/health/live` and `GET /api/health/ready`.
- `app/services/evaluation.py` + `backend/evaluation/dataset.json` — a
  deterministic offline harness → `POST /api/evaluate`, `GET /api/evaluate/latest`.
  See `docs/evaluation.md`.

### 4.5b Hardening
- `SECRET_KEY` startup guard (fails outside dev if default/short).
- In-process sliding-window rate limiting for auth and LLM endpoints.
- Extended settings and `.env.example` for ingestion/retrieval/tutor/assessment/
  BKT/rate-limit/provider settings.

### 4.5 Frontend
The static pages are wired to the real APIs (tutor chat + citations, assessment
creation, quiz, results, progress/mastery, recommendations, dashboard, source
viewer, provider status). No fake data; degraded/empty states are explicit.
See section 8 for the current status of each page.

## 5. Data model added by migration `0002_learning_features`

`conversations`, `messages`, `assessments`, `questions`, `attempts`,
`assessment_responses`, `topic_mastery`, `recommendations`, `evaluation_runs`.
The migration is **additive only** and matches the ORM models
(`alembic check` → "No new upgrade operations detected").

## 6. Setup & run commands

```powershell
# 1. Database (or point DATABASE_URL at Supabase/Neon)
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env      # edit DATABASE_URL and SECRET_KEY
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3. Models
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text
```

- Frontend: <http://127.0.0.1:8000/> (`/ui` redirects here)
- API docs: <http://127.0.0.1:8000/docs>
- Readiness: <http://127.0.0.1:8000/api/health/ready> and `/api/providers/status`

## 7. Tests & evaluation

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\ruff.exe check .
```

```text
# backend (60 collected)
tests/test_services_unit.py .......... 15 passed        # pure logic, no DB
tests/test_health.py ...............   3 passed        # health, root→HTML, /ui→/ redirect
tests/test_tutor_assessments.py ....   12 passed       # incl. 4 new streaming tests
# full run: 59 passed, 1 failed, 2 rerun (20:59)
```

> The single failure was `test_assessment_generation_grading_and_mastery` with
> `asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of
> operation` — a **transient remote-Postgres (Supabase pooler) network drop**, not a logic
> error. Re-run in isolation it passes (`1 passed in 44s`). All prior full runs passed it.
> `ruff check .` is clean; all 21 frontend JS files pass `node --check`.

Unit/streaming/health detail: `tests/test_services_unit.py` 15/15;
`tests/test_tutor_assessments.py -k stream` 4/4; `tests/test_health.py` 3/3.

Evaluation harness (deterministic, offline), `k = 3`:

```json
{
  "retrieval_hit_at_k": 1.0,
  "context_precision": 0.5741,
  "context_recall": 0.963,
  "citation_correctness": 1.0,
  "unsupported_detection": 1.0,
  "learner_improving_profiles": 2.0,
  "learner_profiles": 3.0
}
```

## 8. Feature status (implemented vs. not)

| Feature | Status |
| ------- | ------ |
| Auth (JWT/bcrypt), courses, uploads | Implemented (pre-existing) |
| PDF / image(OCR) / txt ingestion → pgvector | Implemented (pre-existing) |
| Grounded tutor + real citations + insufficient state | Implemented |
| Streaming tutor answers (SSE) with live status | Implemented |
| Assessment generation + validation + dedupe | Implemented |
| Grading (MCQ/numeric exact, short heuristic) | Implemented (heuristic labelled) |
| Learner model (BKT) + weak/untested + recommendations | Implemented |
| Topic graph with prerequisite cycle detection | Implemented (heuristic suggestions) |
| Provider/readiness status | Implemented |
| Offline evaluation harness | Implemented |
| Frontend wired to real APIs | See below |
| **PPTX ingestion** (slide text + speaker notes) | Implemented |
| **Video ingestion (Whisper)** | Not implemented (rejected with a clear message) |
| **Claim-level answer verification (NLI)** | **Not implemented** (documented) |
| MFA / refresh tokens / token revocation | Not implemented |
| Distributed rate limiting | Not implemented (in-process only) |

## 9. Limitations (honest)

- Citations indicate the passages the model **used**; they are not a
  machine-checked proof that every sentence is entailed. The UI says "grounded",
  not "verified".
- Small local models can still hallucinate; keep temperature low.
- Short-answer grading is a keyword heuristic, not semantic understanding.
- BKT parameters are sensible defaults, not per-student fitted.
- Retrieval has no reranker; context precision is ~0.57 on the eval set.
- Rate limiting is per-process; CORS defaults to `*` (must be locked down).

## 10. Future work

- Reranker and an optional local NLI/LLM verifier for claim-level grounding.
- Video (FFmpeg + faster-whisper) ingestion.
- Fit BKT parameters per student; add prerequisite-aware practice sequencing.
- Playwright end-to-end UI tests; distributed rate limiting; CI
  dependency scanning.
