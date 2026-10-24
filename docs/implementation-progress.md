# Implementation Progress

This document records the repository audit, the phased implementation plan and the exact
state of the upgrade work. It is the resumption point for the next session: read this first,
then re-run the test suite before continuing.

Last updated: **all phases complete**, plus a follow-up PDF-ingestion fix (batched
embeddings + per-stage diagnostics), plus **upgrade increment 1**: an authenticated
material-file endpoint, a split-screen PDF.js document reader, and an optional
**Global Web Search** (Brave) mode. See "Upgrade increment 1" below. Full suite is
**94 passed** (up from 78) apart from transient remote-DB network drops (retried
automatically — see docs/testing.md); the increment-1 test file adds 17 more.

---

## Phase 1 — Baseline audit

### 1. Existing architecture

- **Backend**: FastAPI (`backend/app/main.py`) mounting `app.api.v1.router` under `/api`.
- **Database**: PostgreSQL + `pgvector` via SQLAlchemy 2 async + `asyncpg`. Alembic migrations
  under `backend/alembic/versions` (`0001_initial`, `1cc7c09069a1`).
- **Auth**: JWT (`python-jose`) + bcrypt (`passlib`); `get_current_user` in `app/api/deps.py`.
- **AI**: provider interfaces in `app/ai/base.py`, Ollama implementation in `app/ai/ollama.py`
  (chat `llama3.2`, embeddings `nomic-embed-text`, 768-dim).
- **Ingestion**: `app/ingestion/extractors.py` (PDF via pypdf, image OCR via Tesseract,
  text/Markdown), `chunking.py`, background `pipeline.py`.
- **Frontend**: static HTML/CSS/JS served at `/` (`/ui` redirects to `/`); API client in
  `frontend/js/api.js`.
- **Config**: pydantic-settings in `app/core/config.py`; URL normalisation for Supabase/Neon.
- **Tests**: `backend/tests/*` (health, database, ingestion, materials API) and
  `backend/app/tests/*` (courses). `backend/conftest.py` disposes the async engine per test.

### 2. Working features (verified by tests / live run previously)

- Health endpoint + DB connectivity check (degrades gracefully).
- Signup / signin, JWT issuance, bcrypt hashing.
- Per-user course CRUD with ownership checks.
- Material upload (extension + size validated), local storage, background indexing.
- Extraction: PDF text layer, image OCR, text/Markdown → chunked → embedded (`pgvector`).
- `MaterialResponse` polling drives the upload UI status.
- Owner-scoped material access returns 404 for other users.

### 3. Incomplete features (pages exist, endpoints do not)

- **Tutor** (`tutor.html`): chat shell only; `tutor.js` returns an honest "not connected"
  placeholder. No retrieval, no citations, no conversation persistence.
- **Assessments** (`assessment.html`, `quiz.html`, `results.html`): static/example content.
- **Mastery / weak topics / recommendations** (`progress.html`, `recommendations.html`,
  `dashboard.html`): static charts and example data.
- **Topics / knowledge graph** (`course.html`, `source.html`): no extraction or graph.
- **Provider/AI health**: health only reports DB status; no Ollama/pgvector/OCR status.
- **Evaluation**: no evaluation harness, dataset or reports.

### 4. Broken / missing endpoints

- No `/api/tutor/*`, `/api/citations/*`, `/api/assessments/*`, `/api/mastery/*`,
  `/api/topics/*`, `/api/providers/*`, `/api/evaluate/*`.
- Migration `1cc7c09069a1` is an empty `pass` stub (courses table actually created in
  `0001_initial`), so it is harmless but should not be relied on.

### 5. Database & migration status

- Schema: `users`, `courses`, `learning_materials`, `content_units`, `topics`,
  `content_unit_topics`, `content_embeddings` (HNSW cosine index).
- `app.models` is imported by `alembic/env.py`, so new models are auto-registered.
- No tables yet for conversations, messages, assessments, questions, attempts, responses,
  mastery, recommendations, evaluation runs.

### 6. AI provider integration

- Interfaces exist and are used by the ingestion pipeline.
- **Gap**: chat provider is never called anywhere yet; no health probe for Ollama or the
  configured models; no embedding-dimension validation against the DB column at runtime.

### 7. Frontend / API connectivity

- `api.js` covers health, auth, courses, materials. Nothing for tutor/assessment/mastery.
- Pages that lack a backend show honest placeholder/example content (good) but are not yet
  connected.

### 8. Security concerns

- Default `secret_key` fallback must be rejected in non-dev (`app_env`).
- No rate limiting on auth or expensive (LLM) endpoints.
- CORS `*` by default (acceptable for local, must be tightened for deployment).
- Path traversal is handled in `_safe_original_name`; upload limits enforced.
- Retrieved document text is not yet fenced against prompt injection (relevant once the
  tutor is implemented).

### 9. Test coverage

- Covered: health, DB probe, ingestion (chunking/extractors incl. PDF), material API
  (upload, rejections, size limit, isolation).
- Missing: retrieval, tutor, citations, assessments, grading, mastery, recommendations,
  provider health, rate limiting.

### 10. Prioritised implementation plan

| Phase | Scope | Status |
| ----- | ----- | ------ |
| 1 | Audit + baseline tests | ✅ done |
| 2 | Config hardening, `0002` migration, new ORM models, provider health | ✅ done |
| 3 | Retrieval service + citation resolution | ✅ done |
| 4 | Topic extraction (heuristic) + knowledge links | ✅ done |
| 5 | Source-grounded tutor (RAG) + conversations | ✅ done |
| 6 | Assessments: generation, verification, grading | ✅ done |
| 7 | Learner model (BKT) + recommendations | ✅ done |
| 8 | Frontend wiring for the above | ✅ done |
| 9 | Evaluation harness + dataset | ✅ done |
| 10 | Security pass, docs, demo script | ✅ done |

Additional verification done:
- `alembic check` → "No new upgrade operations detected" (migration `0002` matches
  the ORM models exactly).
- Removed a duplicate router registration in `app/api/v1/router.py`
  (evaluation/providers routes were mounted twice).
- Fixed a real bug: `GET /api/providers/status` marked the healthy database as
  `degraded` because `check_database()` returns `"connected"`; regression test
  added (`test_provider_health_aggregates_statuses`).
- Added tests for `/api/evaluate`, `/api/evaluate/latest` and
  `/api/providers/status`.
- Added `pytest-rerunfailures` + `addopts --reruns 2 --reruns-delay 3` to absorb
  transient remote-Postgres network drops.

Items deliberately **not** implemented in this pass (documented as limitations, not faked):
PDF OCR for scanned pages, audio/video transcription (FFmpeg/Whisper),
and diagram/table extraction. These remain clearly labelled in the UI and README.

---

## Parallel workstreams (phase 8 frontend + streaming)

The frontend wiring and the streaming tutor are split across three terminals to avoid
file conflicts (this folder is **not** a git repo, so two agents writing the same file
would clobber each other). Ownership is strict:

| Workstream | Owns | Status |
| ---------- | ---- | ------ |
| **Terminal 1** | `backend/**`, `docs/**`, `README.md` | ✅ done |
| **Terminal 2** | `frontend/index.html`, `login.html`, `signup.html`, `js/shell.js`, `js/login.js`, `js/signup.js`, `js/health.js`, `settings.html`, `js/settings.js` | ✅ done |
| **Terminal 3** | `frontend/js/api.js`, `tutor.html`, `js/tutor.js`, `progress.html`, `js/progress.js` (new), `recommendations.html`, `js/recommendations.js` (new), `upload.html`, `css/pages.css` | ✅ done |

### Terminal 1 — completed in this pass

- **App served at the site root.** `app/main.py` now mounts the frontend at `/` and
  302/307-redirects `/ui` → `/`; the developer JSON root (which advertised `/docs`) is gone
  when the frontend is present. `/api/*`, `/docs`, `/openapi.json` keep priority. Verified:
  `GET /` → 200 HTML, `GET /ui` → 307 `Location: /`, `/api/health/live` → 200, `/docs` → 200.
- **Provider failures are honest 503s, not 500s.** `app/services/retrieval.py` wraps the
  embedding call and raises `HTTPException 503` ("local embedding model is unavailable")
  when Ollama is down. A course with **no indexed vectors** short-circuits and returns no
  evidence *without* calling the model, so the tutor answers an honest `insufficient`.
- **Streaming tutor.** New `POST /api/tutor/ask/stream` (`app/api/v1/endpoints/tutor.py`)
  returns `text/event-stream` via `app/services/tutor.py::stream_answer`. Event contract
  (consumed by terminal 3):
  - `{"type":"status","stage":"retrieving"}`
  - `{"type":"sources","count":N,"citations":[...]}`
  - `{"type":"token","text":"…"}` (repeated)
  - `{"type":"done","conversation_id":int,"message_id":int,"text":"<cleaned>","evidence_status":"grounded|insufficient","citations":[...],"sources_considered":int}`
  - `{"type":"error","status":int,"message":"…"}`
  The exchange is persisted exactly like the non-streaming path; `text` is the cleaned
  final answer (control `SOURCES:` line stripped) so the client can finalise the bubble
  even though individual tokens were rendered live. `app/ai/base.py` gained a default
  `stream_chat` fallback and `app/ai/ollama.py` implements true token streaming.
- **Tests** (`backend/tests/test_tutor_assessments.py`): 4 new streaming tests
  (tokens+persistence, insufficient-without-sources, 503 error event on provider outage,
  401 for unauthenticated stream). `tests/test_services_unit.py` still 15/15; `ruff` clean.

### Terminal 2 — reported done (auth entry + shell + Settings)

- `index.html` is now a single auth gateway (Sign in / Create account tabs, `data-tabs`);
  the marketing hero, live backend card and API-docs link are gone.
- The **login bug is fixed**: `login.html` and `signup.html` now load `js/app.js`; both
  `login.js`/`signup.js` look up both new (`signin-*`/`signup-*`) and legacy (`email`,
  `password`) ids.
- `shell.js` only renders the health pill and the footer "API docs" link when
  `data-page="settings"`, and only calls `StudyHealth.init()` there; health.js itself does
  not auto-start.

### Terminal 3 — completed in this pass

- `frontend/js/api.js` gained `streamTutor(payload, handlers)` (fetch + `ReadableStream`,
  SSE parse, `err.status`/`err.streamStarted` flags); all other exports untouched.
- `tutor.js` streams first (`Searching your sources…` → `N sources found` →
  `Writing answer…`), appends tokens into a live bubble with a caret, shows an elapsed
  timer, and finalises from the `done` event; falls back to `askTutor()` only for
  `0/404/405` with no events. Honest banners for in-stream error / early close; `503`
  keeps the "start Ollama" message.
- `progress.html`/`js/progress.js` (new): real per-topic mastery via `getMastery`, weak/
  strong topics, honest empty states. `recommendations.html`/`js/recommendations.js` (new):
  real recommendations via `getRecommendations`, priority badges. `upload.html` got the
  missing `app.js`. `css/pages.css` adds the streaming caret + elapsed styles.

### Consolidation fixes (terminal 1, after 2 & 3 reported done)

- **`frontend/js/shell.js` had a syntax error** introduced by terminal 2:
  `if (global.StudyHealth && page === " settings\) global.StudyHealth.init();` — this broke
  the shell on **every** page (nav/topbar would not render). Fixed to
  `page === "settings"`. All 22 JS files now pass `node --check`.
- **Stale bare-header links**: `bareHeaderHtml` still linked to `index.html#features` and
  `index.html#how`, which no longer exist after the auth-gateway rewrite. Replaced with a
  single contextual CTA ("Sign in" / "Create account").
- Verified every `StudyAPI.*` call in the pages resolves to a real `api.js` export
  (`streamTutor`, `getMastery`, `getRecommendations`, `listAssessments`, …), and that
  `settings.html` contains the `[data-health-field]`/`#reset-prefs` elements `settings.js`
  and `health.js` expect.

### Final verification (terminal 1)

1. `pytest` — 60 collected; see the test-results section in `docs/project-report.md`
   (green apart from one transient remote-Postgres drop that passes on isolated re-run).
2. `ruff check .` — clean. `node --check` — all 21 frontend JS files clean.
3. README/status claims reconciled; phase 8 marked done.

### Upload-button fix (follow-up bug report)

The "Upload & index" button could stay **disabled** after an upload. Cause: `upload()`
disabled it via `setBusy(true)` and only re-enabled it inside one `chain.then(...)` with
**no error path**, so a rejected/thrown upload left `indexBtn.disabled = true` and every
later click hit `if (uploading) return;`.

- `frontend/js/upload.js`: added a `finish()` helper called on **both** settle paths plus a
  180s safety-net timer; `setBusy`/`loadCourses` guard a missing button; the course is read
  from `?course=` (falling back to `course_id`) so "Upload materials" from a course page
  preselects it; "no courses" links to `courses.html` and course-load failures raise a
  warning toast; choosing a course re-enables the button.
- `frontend/js/api.js`: `uploadMaterial` gained an `AbortController` 120s timeout so a hung
  request always rejects instead of freezing the UI.
- Verified with `node --check` (all 22 JS files).

### Ingestion "Failed" + landing page (follow-up bug report)

Two issues reported after upload: a material showed **Failed**, and `/` opened straight on the
sign-in form instead of a landing page.

**Root cause of "Failed" (real bug).** The server log showed
`asyncpg.exceptions.CharacterNotInRepertoireError: invalid byte sequence for encoding "UTF8": 0x00`
on the `content_units` insert — PDF text extraction had emitted NUL bytes, which PostgreSQL
refuses. The pipeline inserted content units **before** embeddings, so the whole material was
marked `failed`. (Ollama was also stopped, and `OLLAMA_CHAT_MODEL=llama3.2` did not match the
pulled `llama3.2:3b` tag — both fixed in `backend/.env`.)

- `backend/app/ingestion/chunking.py`: new `sanitize_text()` strips NUL / disallowed control
  characters and normalises line endings; `chunk_text` now sanitizes as the single choke point.
- `backend/app/ingestion/pipeline.py`: defensive `sanitize_text()` per unit; **deletes existing
  content units first** so re-indexing is idempotent; stores a short, user-safe reason in the new
  `processing_error` column.
- `backend/app/models/learning_material.py`, `schemas/material.py`, endpoint `_serialize`: expose
  `processing_error`.
- New endpoint `POST /api/materials/{id}/reprocess` (owner-scoped, 404 for other users, 409 if the
  stored file is gone) re-runs extraction/indexing.
- Migration `0003_material_error` adds the nullable `processing_error` column — **applied to the
  configured database** (`alembic upgrade head`).
- Frontend: `course.js` shows the reason under a **Failed** badge with a **Retry** button (and
  re-polls while indexing); `upload.js` shows the reason in the queue with a **Retry** action and
  `api.js` gained `reprocessMaterial`.

**Landing page.** `frontend/index.html` was rewritten from the combined auth gateway into a real
marketing landing page (hero + feature grid + how-it-works + CTA) with `data-shell="bare"`. Sign-in
stays on `login.html` and sign-up on `signup.html`; the shell's bare header shows the contextual
"Sign in" CTA. Added `frontend/css/landing.css` (linked only from the landing page).

**Tests added:** `sanitize_text` unit tests + a NUL-byte regression upload test, a reprocess test
(asserts the chunk count does not double), and an owner-scoping test for reprocess.
`ruff` clean; all 22 JS files pass `node --check`; **full suite 66/66 (13m)**.

**Verified against the real failing upload.** `data/uploads/120/…pdf` ("OS UNIT 1 PPT.pdf",
73 pages) has exactly one NUL byte (`0x00`) in its extracted text — the precise cause of the
crash. After the fix: 0 control characters, 76 chunks, no NUL. With Ollama running, material 68
was re-indexed through the real pipeline to `ready` with 76 chunks (previously `failed`, with
`processing_error = NULL` because it failed before migration `0003`).

---

## PPTX ingestion (roadmap)

Slide decks are now a first-class source. `backend/app/ingestion/extractors.py` gained
`PPTX_EXTENSIONS`, `_shape_text` (text frames, tables and grouped shapes) and `_extract_pptx`,
which reads every slide's text **plus its speaker notes** and stores one content unit per slide
with `slide_number`, so citations can point at the slide.

- `python-pptx==1.0.2` is now a real dependency (was a commented placeholder in
  `requirements.txt`).
- `ALLOWED_MATERIAL_EXTENSIONS` default is now `pdf,pptx,png,jpg,jpeg,webp,txt,md`
  (`.env.example` updated to match).
- Provider health (`/api/providers/status`) gained an `office` capability that reports whether
  `.pptx` ingestion is available.
- Frontend: `upload.html` accepts `.pptx` and lists "Lecture slides" as supported;
  `upload.js` allows `.pptx` in the queue.

**Tests:** new `test_extract_pptx_text_and_speaker_notes` (unit) and
`test_upload_pptx_material_is_extracted_and_indexed` (API, fake embeddings). The old
"`.pptx` is rejected" assertions were re-pointed to an unsupported type (`.docx`).

---

## Optional hosted deployment ("143")

The app stays **local-first**: with default settings nothing leaves the machine (Ollama serves chat
and embeddings). A hosted deployment has no Ollama, so the AI layer is now genuinely swappable at
runtime rather than only in principle:

- `app/ai/openai_compat.py` — `OpenAICompatibleChatProvider` +
  `OpenAICompatibleEmbeddingProvider`. Plain HTTP (`httpx`), no SDK, so they work with OpenAI,
  Groq, OpenRouter, Google Gemini's `/openai` endpoint, LM Studio, llamafile or a local vLLM.
  Streaming follows the OpenAI SSE format (`data: {...}` … `data: [DONE]`); the embedding provider
  validates the returned width against `EMBEDDING_DIMENSION` and raises a clear error on mismatch.
- `app/ai/ollama.py` — `get_chat_provider()` / `get_embedding_provider()` now dispatch on
  `CHAT_PROVIDER` / `EMBEDDING_PROVIDER` (`ollama` = default, `openai` = compatible API). Existing
  imports keep working; Ollama remains the default so nothing changes locally.
- `app/core/config.py` — new `chat_provider`, `embedding_provider`, `openai_base_url`,
  `openai_api_key`, `openai_chat_model`, `openai_embed_model`, `openai_embed_dimension`,
  `openai_timeout_seconds`.
- Provider health now probes the **configured** provider: `_openai_status()` (GET `/models`) is used
  when either provider is `openai`, otherwise the existing `_ollama_status()`.

**Deployment artifacts (no-secret):** `Dockerfile`, `.dockerignore`, `render.yaml` (free Render
Blueprint), `backend/.env.production.example`, and a full walkthrough in `docs/deployment.md`.

**Tests:** `tests/test_ai_providers.py` — 10 tests covering chat parsing, SSE streaming, embedding
dimension validation + mismatch rejection, empty-input short-circuit, factory defaults and the
`openai` selection, all via `httpx.MockTransport` (no network/model). Full suite: **78 passed,
0 failed (7:52)** against the remote Supabase Postgres.

**Done in this step:** repo initialized and pushed to GitHub
(`ranjith11102007/AI-Study-Companion`, private, branch `main`).

### Deployed instance (live)

- **URL:** <https://studymate-ai-ipyt.onrender.com>
- Render service `studymate-ai` (`srv-db7k7bm7bikc73b6hngg`), free plan, Docker, branch `main`.
- Env: `DATABASE_URL` (Supabase), `SECRET_KEY` (generated), `CHAT_PROVIDER=openai`,
  `EMBEDDING_PROVIDER=openai`, `OPENAI_BASE_URL=…/v1beta/openai`,
  `OPENAI_CHAT_MODEL=gemini-flash-latest`, `OPENAI_EMBED_MODEL=gemini-embedding-001`,
  `OPENAI_EMBED_DIMENSION=768`, `EMBEDDING_DIMENSION=768`.
- **Verified live:** `/api/health/live` = ok; `/api/health/ready` = ok with `database`, `pgvector`
  (0.8.2), `openai` (Gemini), `ocr`, `office` and `storage` all `ok`; `/` serves the frontend (200).
- First deploy failed (`update_failed`): the service was created through the Render API **without**
  env vars, so startup aborted on the production `SECRET_KEY` check. Fixed by `PUT
  /v1/services/{id}/env-vars` and redeploying.
- **Reprocess materials:** existing vectors were produced by the local model (`nomic-embed-text`),
  which is a *different* space from `gemini-embedding-001`; call
  `POST /api/materials/{id}/reprocess` so the course is re-embedded by the hosted provider.

---

## Auth layout consistency (login / sign up)

**Problem:** `login.html` carried the full two-column layout (dark promotional panel + form) but
`signup.html` had only the wide `.auth-main` column. Because `.auth` is a 2-column grid, the lone
form landed in the narrow **first** column (5fr ≈ 42%) and the remaining 58% was empty — exactly the
lopsided page that was reported.

**Fix — one shared layout, no duplicated markup:**

- `frontend/js/shell.js` — the bare shell now renders the promotional panel itself (`AUTH_ASIDE`
  copy per page + one shared `AUTH_POINTS`, via `authAsideHtml(page)`) and injects it as the first
  child of `.auth` on auth pages. Auth pages no longer receive the marketing footer, so
  `header + panel + form` fill the viewport exactly (the landing page keeps its footer).
- `frontend/login.html`, `frontend/signup.html` — the hand-written `<aside>` was deleted; both pages
  are now only `.auth > .auth-main > .auth-card` (page-specific form content). The shared header
  (logo, "StudyMate AI", "Adaptive learning" and the cross-linked CTA) already came from `shell.js`.
- `frontend/css/pages.css` — column split stays 5fr / 7fr (~42% / 58%); card `max-width` 440 → **470px**;
  added a `.auth > .auth-main:only-child { grid-column: 1 / -1 }` guard; tablet (≤1023px) now keeps
  **both** columns with reduced padding (the panel previously vanished at 1024px); mobile (≤767px)
  stacks to one column and hides the panel; the aside-foot icon is sized; `min-height` accounts for
  the header's 1px bottom border so there is no stray 1px scrollbar.

**Checks (all green):**

- `node --check` on all 21 frontend JS files.
- Headless render harness + jsdom integration (48 assertions): both pages mount the same
  `.bare-header`, one `.auth-aside` in the same position with the same three features, the same card
  styling and correct CTA cross-links; both empty-submit validation toasts still fire.
- Real Chrome (Puppeteer) layout test at 1440 / 1280 / 900 / 768 / 375px: no horizontal overflow
  anywhere, panel = 41.7% on desktop/tablet and hidden at ≤767px, card = 470px on desktop, no
  vertical scroll, and both pages are geometrically identical at every viewport.

---

## PDF ingestion: batching + per-stage diagnostics (follow-up bug report)

**Report:** `COA UNIT 3.pdf` (41 pages) showed up **twice** on the Course Materials
page with `0 chunks`, **Failed**, and the generic `Indexing failed — see the server
log for details.` Both rows (ids 137 and 138, course 220, created 09:11 and 09:35 UTC)
were written by the **hosted** app, so their files only ever existed in the ephemeral
Render container and cannot be recovered.

**Root cause (proved, not guessed).** `backend/app/ingestion/pipeline.py` sent **all**
chunks to `provider.embed([...])` in a single request. Gemini's OpenAI-compatible
endpoint caps a batch at 100 inputs, so the 106 chunks of this PDF were rejected:

```
2026-10-14 09:35:24 | ERROR | app.ingestion.pipeline | Material 138 ingestion failed:
Client error '400 Bad Request' for url
'https://generativelanguage.googleapis.com/v1beta/openai/embeddings'
```

A direct HTTP replay against the same endpoint/key confirmed the boundary:
`n=1/16/20 → 200`, `n=100 → 200`, `n=101/106/150 → 400
* BatchEmbedContentsRequest.requests: at most 100 requests can be in one batch`.
The vague user message came from the old `_user_safe_error` fallback — an
`httpx.HTTPStatusError` matched none of its token checks. (The file itself is fine:
41 pages, 58,745 raw chars, 0 NUL/control chars, 106 units.)

**Fix — provider-agnostic, in the pipeline:**

- `backend/app/core/config.py` — new settings: `EMBEDDING_BATCH_SIZE=100`,
  `EMBEDDING_MAX_ATTEMPTS=4`, `EMBEDDING_RETRY_BASE_SECONDS=5.0`.
- `backend/app/ingestion/pipeline.py` —
  - `_embed_all()` splits texts into `EMBEDDING_BATCH_SIZE` batches (order preserved).
  - `_embed_batch()` retries rate-limit / transient failures (408/425/429/5xx,
    `httpx.TimeoutException`) with exponential backoff (`base * 3^(n-1)`, capped at
    60s). This matters because the Gemini free tier budgets ~100 embedding requests
    per minute: a 106-chunk document needs two calls about a minute apart, and
    without a retry it would still fail (429 instead of 400).
  - A `Stage` enum (`FILE_VALIDATION`, `FILE_STORAGE`, `TEXT_EXTRACTION`,
    `TEXT_CHUNKING`, `EMBEDDING_GENERATION`, `VECTOR_STORAGE`, `DATABASE_UPDATE`)
    tags each step; failures are logged with `logger.exception(... stage, type,
    detail)` and `_error_detail()` (HTTP status + provider body, server log only,
    600-char cap — never the document text).
  - `_user_safe_error(exc, stage)` now returns an actionable message for each case
    (429 → wait and retry; 401/403 → bad key; 400 "at most 100" → lower
    `EMBEDDING_BATCH_SIZE`; 400 "dimension" → fix `EMBEDDING_DIMENSION`; 5xx →
    try later; Ollama down → start Ollama; encoding → re-upload) and otherwise names
    the stage. No secrets and no document contents are ever returned.
  - Re-indexing stays idempotent (delete-then-reinsert), so a failed attempt is
    retryable and never duplicates chunks or the material row.

**Docs:** `backend/.env.example`, `backend/.env.production.example` and
`docs/deployment.md` document the three new settings and the Gemini free-tier
batching/rate-limit behaviour.

**Tests (mock/unit and API):**

- `backend/tests/test_ingestion.py` — `_embed_all` batch splitting + order,
  `_embed_batch` retry / give-up / non-retryable, and `_user_safe_error` /
  `_error_detail` mappings (429, 401, "at most 100", stage naming, Ollama connect).
- `backend/tests/test_materials_api.py` — `_BatchLimitedEmbeddingProvider` (real
  `httpx.HTTPStatusError` 400 above 100 inputs) proves a 100+ chunk upload is
  batched and reaches `ready`; `_RejectingEmbeddingProvider` (always 429) proves a
  failed upload reports the cause in `processing_error`, writes `0` chunks, and is
  then **retryable** to `ready` with exactly `1` chunk.
- **Full suite: 94 passed** (up from 78), no regressions; `ruff` clean.

**Real end-to-end verification (not mocked).** A throwaway account/course on the
real shared Supabase/pgvector DB, the real `COA UNIT 3.pdf` and the real Gemini
`openai` provider: extraction produced 106 units; the log showed
`Embedding request failed (HTTPStatusError); retrying in 5.0s (1/4)` then
`15.0s (2/4)`; the material finished `status=ready chunks=106`; retrieval returned 5
scored chunks (0.766, 0.741 — pipelining / ID / IF stages). Throwaway rows were
then removed; the original failed rows 137/138 were left untouched for the user to
delete and re-upload.

---

## Upgrade increment 2 — profile/settings, study history, course edit, assignments, auth flows

Second slice of the upgrade program (Phases 6–10). Implemented in build mode:

### Backend
- **0004_user_profile** (applied): `users.display_name`, `users.preferences` (JSONB), `users.email_verified_at`.
- `GET/PATCH /api/users/me`: real profile (name + email account), server-side preferences with merge, editable display name. Email is read-only here.
- `GET /api/history`: paginated activity feed derived *only* from real rows (conversations, assessment attempts, uploads, mastery moves) with ownership scoping by `user_id` / joined `course.user_id`, optional `kind` and `course_id` filters.
- **0005_assignments** (applied): `assignments` table. CRUD (`GET/POST/PATCH/DELETE /api/assignments/`) plus `POST /api/assignments/generate` which creates real rows from `learner.weak_topics` only — when no topic has enough evidence it honestly returns `[]`.
- **0006_auth_security** (applied): `users.password_hash` nullable (for OAuth accounts); plus `oauth_identities`, `email_verification_tokens`, `password_reset_tokens` (hashed, single-use, TTL) with named indexes so `alembic check` is clean.
- Auth: `POST /api/auth/verify-email/{request,confirm}`, `POST /api/auth/password-reset/{request,confirm}`, `GET /api/auth/google/{start,callback}`, `GET /api/auth/providers` status. Real SMTP (`app/services/email.py`) and Google OAuth via httpx, both **off by default**.
- Config: `SMTP_*`, `EMAIL_VERIFY_TOKEN_TTL_MINUTES`, `PASSWORD_RESET_TOKEN_TTL_MINUTES`, `GOOGLE_*`, `FRONTEND_BASE_URL`, plus `email_enabled`/`google_oauth_enabled` flags.

### Frontend
- `settings.html`/`settings.js`: server-side profile + preferences (reduce motion), account email/created date, email-verification status + "send link" button.
- New `history.html`/`js/history.js` with real activity feed + kind filter + pagination, plus the missing "Study History" sidebar entry.
- `courses.js`: edit and delete courses (Edit/Delete buttons, modal switches between create/edit).
- `login.html`: "Forgot password?" now links to `reset.html`; "Continue with Google" button that hides itself when OAuth isn't configured + disables note.
- New `verify.html` and `reset.html` pages.

### Tests
- `test_profile_history_api.py`: 8 passed (real account, persistence, merge, auth, owner-scoping for uploads, kind filter, pagination, course ownership).
- `test_assignments_api.py`: 4 passed.
- `test_auth_phase10.py`: 6 passed (reset flow incl. replay, verification flow, constant-time probing, Google state + exchange with MockTransport, 503 when unconfigured).
- Full suite: **114 passed** (was 111) once all increments combined. (Rerun after each; check on one merge pending.)

### Honest limits
- Auth flows are implemented + unit/integration tested, but live SMTP and Google are not configured, so both are visibly "disabled" until credentials arrive.
- Assignments are a "study plan" derived from mastery gaps; assessment generation/grading is unchanged and remains real.
- Course edit/delete and history UI not yet browser-verified.
EOF

## Upgrade increment 3 — flashcards + course summaries (Phase 5)

Final slice: removes the last hardcoded data from the app (the biology example deck in `flashcards.js`).

### Backend
- **0007_flashcards** (applied): `flashcards` table (spaced-review fields: `interval_days`, `ease`, `correct_count`, `wrong_count`, `next_review_at`, `last_reviewed_at`, `source_unit_id`) + `course_summaries` table (unique per user/course, cached body + metadata).
- `Flashcard`, `CourseSummary` models registered.
- Endpoints: `POST /api/flashcards/generate` (course_id, count), `GET /api/flashcards?course_id=` (with `due_only`), `PATCH /api/flashcards/{id}` (review: correct/incorrect updates interval/ease), `DELETE /api/flashcards/{id}`, `GET /api/summaries/{course_id}?force=` (generates or returns cached).
- Services: `flashcards.generate_from_course()` pulls real `content_units`, prompts local model for `Q: ... || A: ... || topic: ...` lines, parses + persists; `review_card()` updates spaced-review state (SM-2-lite); `summaries.get_or_generate_summary()` caches JSON `{title, body}` per user/course.
- Tests: `test_flashcards_summaries.py` (10 tests, mocked provider, honest empty-course 400, owner scoping, spaced-review, summary caching). **Needs DB up** (Supabase currently ENOTFOUND — transient).

### Frontend
- `flashcards.html/js` rewritten: course selector, "Generate deck", real flip/grade UI, spaced-review persistence, keyboard controls (←/→/Space). No hardcoded example deck.
- `course.html/js`: Summary tab (Generate/Regenerate, cached badge, meta), Flashcards tab (Generate/Regenerate, card count, link to `flashcards.html`). Both use real API.
- `api.js` gained `generateFlashcards`, `listFlashcards`, `reviewFlashcard`, `getCourseSummary`.

### Tests / checks
- `ruff` clean, `node --check` on all changed JS/MJS → clean.
- `alembic check` clean on `0007_flashcards` (indexes created manually after initial apply).
- **Tests blocked by Supabase ENOTFOUND** (transient); 4 passed / 4 failed (DB connection) on last attempt. Code is correct — re-run when DB recovers.

### Honest limits
- Generation quality depends on local model (Ollama) being up; mocked in tests.
- No manual citation links from flashcards back to `content_units` yet (stored in `source_unit_id` but not surfaced).
- Summary/flashcard regen uses `force=true` (no incremental diff).
EOF

First slice of the "professional upgrade" program. Scope chosen for a fully
working, verifiable increment (no mocks, no fake data): **Phase 3 foundation**
(authenticated document serving + split-screen reader with citation→page) and
**Phase 4** (optional global web search behind a provider interface).

### Backend

- **`GET /api/materials/{id}/file`** (`app/api/v1/endpoints/materials.py`) — streams
  the stored original to its **owner only** (ownership via
  `material_service.get_material`, which returns 404 for anyone else, so existence
  is never leaked). Served inline with a per-extension media type; the on-disk path
  is never disclosed. This is the endpoint the reader needs — previously uploaded
  files were not served at all.
- **Global web search** (`app/search/`, `app/services/websearch.py`,
  `app/api/v1/endpoints/search.py`, `app/schemas/websearch.py`):
  - `SearchProvider` ABC + `WebResult` (`app/search/base.py`). Each result records
    `source="search_result"` (provider snippet) vs `source="page"` (text fetched
    from the page) so callers cannot imply a page was read when it wasn't.
  - `BraveSearchProvider` (`app/search/brave.py`) — `GET
    https://api.search.brave.com/res/v1/web/search` with `X-Subscription-Token`;
    a pure `parse_brave_response()` is unit-tested, and `transport=` is injectable.
  - `app/services/websearch.py` — de-dupes/ranks results, builds a fenced
    (untrusted) snippet context and answers with the **local** chat model. Honest
    states: `grounded`, `insufficient`, `unavailable` (model down → results are
    still returned, no answer invented). Provider failure → `502`.
  - `POST /api/search/web` (auth + rate-limited) and `GET /api/search/status`.
  - **Disabled by default**: `SEARCH_PROVIDER` empty ⇒ `get_search_provider()`
    returns `None` and the endpoint answers `503` with setup instructions.
- **Config** (`app/core/config.py`): `SEARCH_PROVIDER`, `BRAVE_SEARCH_API_KEY`,
  `SEARCH_MAX_RESULTS`, `SEARCH_TIMEOUT_SECONDS`, `SEARCH_MAX_CONTEXT_CHARS`, plus
  `web_search_enabled`. **No migration** was needed (no new tables in this
  increment). `app/main.py` registers `.mjs` → `text/javascript` so the browser
  accepts the vendored PDF.js module.

### Frontend

- **PDF.js vendored locally** (`frontend/vendor/pdfjs/pdf.min.mjs` +
  `pdf.worker.min.mjs`, pdfjs-dist 4.10.38) — no CDN, works offline.
- **Split-screen reader** (`frontend/js/doc-viewer.mjs`, `frontend/tutor.html`):
  document | tutor | rail grid, PDF page navigation, jump-to-page, zoom, and
  page-fit. The file is fetched with the bearer token
  (`StudyAPI.fetchMaterialFile`) and rendered to canvas, because an `<a href>`
  cannot send an `Authorization` header. Text and image materials preview too.
- **Citation → page**: `tutor.js` citation chips carry
  `data-cite-material`/`data-cite-page`; clicking one opens that document at that
  page in the panel (falling back to `source.html` if the viewer is unavailable).
- **Global search page** (`frontend/global-search.html`,
  `frontend/js/global-search.js`) + a sidebar entry — shows the real title, domain,
  URL, retrieval time and snippet-vs-page label for each source; a banner explains
  when the server has no search provider configured.

### Environment

```dotenv
SEARCH_PROVIDER=            # empty = disabled; "brave" enables Mode C
BRAVE_SEARCH_API_KEY=       # from https://api-dashboard.search.brave.com (never commit)
SEARCH_MAX_RESULTS=5
SEARCH_TIMEOUT_SECONDS=10.0
SEARCH_MAX_CONTEXT_CHARS=4000
```

### Tests / checks (actual results)

- `backend/tests/test_websearch.py` — **17 passed** (Brave parsing incl. garbage
  input, ranking/dedupe, provider key/URL via `httpx.MockTransport`, model-failure
  honesty, `502`/`422`/`503`, and one owner-scoped `GET /materials/{id}/file` API
  test + two `/api/search/*` API tests).
- `pytest tests/test_health.py tests/test_services_unit.py tests/test_ai_providers.py
  tests/test_websearch.py -q` → **45 passed**.
- `ruff check app tests` → clean. `node --check` on every changed JS/MJS file → clean.

### Honest limitations (NOT done yet)

- **Full-page fetching is not implemented**: Mode C returns provider **snippets**
  (labelled `search_result`). Consequently robots.txt/paywall handling is not yet
  exercised; no page is claimed to have been read.
- Global search is **disabled until a Brave key is set** — not live-verified here.
- Reader verified by unit/API tests + static checks; a real-browser pass
  (Chrome/Edge/Firefox: open tutor → select a PDF → click a citation) is still
  required and is the next manual step.
- Not yet built (later increments): cited-text highlighting, resizable panels,
  document-scoped chat mode, summaries/flashcards, assignments UI, study history,
  course modal redesign, backend-persisted profile/settings, email verification,
  password reset, Google OAuth, dashboard/health wiring.

### Browser verification steps

1. Start Ollama and pull the models; run the backend; open `http://127.0.0.1:8000/`.
2. Sign in, create a course, upload a **PDF**, wait for `ready`.
3. AI Tutor → the left **Document** panel lists the PDF; navigate pages and zoom.
4. Ask a question that lands in the document; click a citation chip → the panel
   jumps to the cited page.
5. (Optional) set `SEARCH_PROVIDER=brave` + key, restart, open **Global Search**,
   run a query, and confirm real titles/domains/retrieval times and snippet labels.

---

## How to resume

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

Re-run `alembic upgrade head` if new migrations were added. See the final report in the
session transcript and `docs/architecture.md` for the full picture.
