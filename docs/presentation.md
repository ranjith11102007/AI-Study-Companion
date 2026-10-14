# Presentation Outline (StudyMate AI)

A ~12-slide walkthrough. Speaker notes in italics.

1. **Title** — StudyMate AI: a local-first, source-grounded study companion.
   *No cloud AI, no paid APIs by default: inference runs on your machine via
   Ollama. An optional hosted mode can use a free OpenAI-compatible API.*

2. **Problem** — Generic chatbots hallucinate and can't cite your course
   material; cloud tutors cost money and leak data.

3. **Goal** — Tutor + adaptive assessment + learner model, grounded **only** in
   the student's indexed material, fully local.

4. **Architecture** — FastAPI · PostgreSQL + pgvector · Ollama · static SPA.
   *Show `docs/architecture.md` diagram.*

5. **Ingestion** — upload PDF/image/text → extract (pypdf / Tesseract) → chunk →
   embed (nomic-embed-text, 768-dim) → `ready`. *Honest: PPTX/video are not yet
   supported.*

6. **Grounded tutoring** — embed question → pgvector cosine search scoped to the
   course → fenced `<source>` context → local chat model → citations attached
   from the sources actually used. Insufficient evidence ⇒ say so.

7. **Citations** — each citation is a real `content_units` row (material, page/
   slide/timestamp, excerpt), resolvable and owner-scoped. *Claim-level
   entailment is not machine-proven — we say "grounded", not "verified".*

8. **Assessments** — the model drafts questions from the sources; a validation
   layer rejects malformed items (bad MCQ keys, non-numeric numerics, missing
   rubrics) and de-duplicates by fingerprint. Short answers are marked
   **not machine-verified**.

9. **Grading** — MCQ exact, numeric within tolerance, short answer by a
   transparent keyword-overlap rubric (labelled heuristic). Attempts can be
   submitted once; answer keys never leak before submission.

10. **Learner model** — Bayesian Knowledge Tracing per topic; weak topics need
    evidence; recommendations (`weak_topic` / `diagnostic` / `revision`) rebuilt
    from real state.

11. **Evaluation** — deterministic offline harness: hit@3 = 1.00, citation
    correctness = 1.00, unsupported detection = 1.00 (see `docs/evaluation.md`).

12. **Limitations & roadmap** — no claim-level verification, no lecture-video
    simple rate limiting, no MFA; next: reranker/NLI verifier, more formats,
    richer knowledge graph.

*Close: run the demo script (`docs/demo-script.md`) live.*
