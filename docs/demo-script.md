# Demo Script (≈5 minutes)

Prereqs: `docker compose up -d db` (or a configured `DATABASE_URL`),
`ollama serve`, `ollama pull llama3.2:3b`, `ollama pull nomic-embed-text`,
backend running, migrations applied (`alembic upgrade head`).
Open <http://127.0.0.1:8000/> — the landing page — then **Sign in**.

### 0. Readiness (20s)
- Open **Settings**. Point out the dependency panel: database, pgvector, Ollama,
  OCR, storage — each shown honestly as ok / degraded / unavailable.
- If Ollama is stopped, show it as `degraded` and note the app still runs.

### 1. Sign up + course (30s)
- From the landing page click **Create free account**, sign up, create a course "Biology 101".

### 2. Upload & index (60s)
- Upload a short PDF and a `.txt` note. Show the status move
  `pending → processing → ready` and the real `content_unit_count`.
- Mention: extraction is real (pypdf text layer / Tesseract for images /
  python-pptx for slides), not simulated. Video is rejected with a clear message.

### 3. Grounded tutor with citations (90s)
- Ask a question covered by the material.
- Show the answer **and** the citation chips (material + page). Click a citation →
  the source viewer opens the exact stored passage.
- Ask something **not** covered → show the honest "insufficient" state (no
  fabrication).

### 3b. Prompt-injection aside (optional, 20s)
- Mention that document text is fenced and treated as untrusted.

### 3. Assessment (60s)
- Generate a 5-question quiz from the material. Show `generation_notes`.
- Point out that short-answer questions are labelled "not machine-verified".

### 4. Take the quiz (60s)
- Answer a few; answer one numeric close to the tolerance. Submit once.
- Results page: score, per-question feedback, explanations, and citation links.

### 5. Learner model (45s)
- Open **Progress**: per-topic mastery bars built from your answers (not fake).
- Open **Recommendations**: reasons reflect your actual weak/untested topics.
- Note: a topic you never answered shows as *untested*, not *weak*.

### 4. Wrap (15s)
- Run the evaluation endpoint or show `docs/evaluation.md` numbers.
- State limits plainly: no claim-level verification, no lecture-video ingestion yet.

**Fallback if Ollama is down:** the readiness panel and the honest 503 messages
on tutor/assessment still demonstrate the degraded-state handling.
