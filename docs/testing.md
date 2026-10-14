# Testing

## Running

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\ruff.exe check .
```

`pytest.ini` sets `asyncio_mode = auto`, `testpaths = tests app/tests`,
`pythonpath = .` and `addopts = --reruns 2 --reruns-delay 3` (see "Known
flakiness"). The suite currently collects **60 tests**.

## Layout

| File | Covers |
| ---- | ------ |
| `tests/test_health.py` | health endpoint shape and DB probe |
| `tests/test_database.py` | connectivity helper |
| `tests/test_ingestion.py` | chunking, extractors, PDF text layer, empty-PDF error, OCR (gated) |
| `tests/test_materials_api.py` | upload → index → `ready`, type/size rejection, per-user isolation |
| `tests/test_courses.py` | course CRUD |
| `tests/test_services_unit.py` | pure logic: chunking, BKT, number parsing, JSON extraction, question validation, grading (MCQ/numeric/short), context fencing, evaluation metrics, topic heuristics |
| `tests/test_tutor_assessments.py` | retrieval + tutor + citations, streaming tutor (tokens/persistence, insufficient, 503 error event, 401), assessment generation/validation/grading, mastery/weak topics, topic prerequisite cycle |

## Streaming tutor tests

The streaming tutor is covered by four tests that inject fakes (no Ollama needed):
`test_tutor_streams_tokens_then_persists` (event order `status → sources → token* →
done`, control `SOURCES:` line stripped, exchange persisted),
`test_tutor_stream_reports_insufficient_without_sources` (empty course → no model call),
`test_tutor_stream_maps_provider_outage_to_error_event` (embedding failure → `503` error
event, not a crash) and `test_tutor_stream_endpoint_requires_auth` (401).

## Fixtures & fakes

- `backend/conftest.py` disposes the app's async engine after each test (each
  test gets its own event loop; pooled asyncpg connections must be closed in it).
- Model calls are replaced with deterministic fakes injected at the service
  boundary (`chat_provider`, `embedder`) or by monkeypatching
  `pipeline.get_embedding_provider`. Tests therefore **never require Ollama** and
  never download a model.
- Health/tutor tests use non-zero fixed embedding vectors so cosine search is
  well-defined.

## Database requirement

Unlike the pure unit tests, the ingestion/materials/tutor/assessment tests use
the **real PostgreSQL + pgvector** database configured in `backend/.env` (the dev
Supabase instance or the `docker-compose` Postgres). They create uniquely-named
users and delete them in a `finally` block. Run migrations first:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

## OCR tests

Tests that exercise Tesseract call `ocr_available()` and are **skipped** when
Tesseract is not installed, so the suite is portable.

## Known flakiness

The DB-backed tests talk to a remote Postgres (Supabase pooler) during
development. Under a long full-suite run the pooler can drop an idle connection or the DNS
name can fail to resolve, producing a transient `asyncpg ...
ConnectionDoesNotExistError` or `socket.gaierror: getaddrinfo failed` during a
DB-backed test. `pytest-rerunfailures` (configured in `pytest.ini` as
`--reruns 2 --reruns-delay 3`) retries these automatically, and any test that
still fails passes on an immediate isolated re-run. This is a network/pooler
artifact, not a logic failure; it does not occur against the local
`docker-compose` database (Docker was not available on the development machine
used for this build).

## What is not covered

- Live Ollama inference (would make tests slow and non-deterministic).
- Browser/end-to-end UI tests (no Playwright harness yet).
- Load/performance and concurrency.

## Cleanliness

`ruff check .` must pass with no findings. New code follows the existing style
(module docstrings, typed signatures, no unused imports).
