# Grounding, Evidence and Citations

The tutor must answer **only** from the material a student has indexed for a
course, and every answer must be traceable to real stored sources. This document
describes exactly how that is enforced and where the limits are.

## Pipeline

`POST /api/tutor/ask` → `app/services/tutor.py::answer_question` (the streaming
variant `POST /api/tutor/ask/stream` → `stream_answer` runs the exact same steps
and only differs in delivery: it emits `status → sources → token* → done`):

1. **Ownership** — the course is loaded with `Course.user_id == user_id`, else
   `404`. No cross-tenant access is possible. (The streaming endpoint checks
   ownership before opening the stream and returns a normal `404`.)
2. **Retrieval** — `app/services/retrieval.py::retrieve` embeds the question with
   the local embedding model and runs a pgvector cosine search restricted to
   `ContentUnit.course_id == course_id`. It returns at most `retrieval_top_k`
   chunks whose cosine similarity is `≥ retrieval_min_score`. This is applied at
   the database level, so the model never sees other users' content.
3. **Evidence sufficiency** — if **zero** chunks pass the threshold, the tutor
   does not call the model at all. It returns
   `evidence_status = "insufficient"` with an honest message and no citations.
4. **Fenced context** — `retrieval.build_context` wraps each passage in
   `<source id="N" material="..." location="..."> … </source>` and trims to
   `tutor_max_context_chars`. Passages are treated as **untrusted evidence**.
5. **Generation** — the local chat model is called with a system prompt that:
   - restricts answers to the numbered sources;
   - forbids following instructions found inside sources;
   - forbids inventing facts and requires saying so when sources are insufficient;
   - asks for inline `[n]` markers and a final `SOURCES: …` line.
6. **Citation attachment** — the answer is parsed for the sources it actually
   used (`SOURCES:` line, falling back to inline `[n]` markers). Only those
   chunks become citations; the control line is stripped from the answer. If
   none are named, all retrieved chunks are attached as the considered set.

## Citation payload

Each citation is built from real stored columns only — never fabricated:

```json
{
  "content_unit_id": 123,
  "material_id": 7,
  "material_title": "lecture-03.pdf",
  "material_type": "pdf",
  "page_number": 4,
  "slide_number": null,
  "start_timestamp": null,
  "end_timestamp": null,
  "excerpt": "…first ~320 characters of the chunk…",
  "score": 0.81
}
```

`GET /api/citations/{content_unit_id}` resolves a citation back to its full text
and location, and is **owner-scoped** (a non-owner gets `404`).

## What is guaranteed

- Every citation references a `content_units` row that exists and is owned by
  the requesting user.
- Page/slide/timestamp fields are copied from the stored chunk metadata; if a
  format provides no location, the field is `null` (rendered as "excerpt").
- Answers with no supporting material are labelled `insufficient`.

## What is *not* guaranteed (honest limitations)

- **Claim-level entailment is not verified.** The app does not run a
  natural-language-inference model to prove that each sentence is entailed by
  the cited passage. Citations indicate the passages the model *used*, not a
  machine-checked proof of every statement. This is why the UI labels answers
  "source-grounded" rather than "verified".
- **Small local models can still hallucinate** despite instructions. Keep
  `tutor_temperature` low and prefer a capable local chat model.
- **Semantic similarity ≠ factual support.** A retrieved passage can be
  topically related without containing the answer; the prompt instructs the
  model to say so, and `insufficient` is returned when nothing clears the floor.
- **Prompt injection** in uploaded documents is mitigated (fencing + explicit
  system instruction) but not eliminated. Treat uploaded files as untrusted.

## Improving grounding

- Raise `retrieval_min_score` to demand stronger matches (more `insufficient`
  results, fewer weak citations).
- Raise `retrieval_top_k` / `tutor_max_context_chars` to give the model more
  evidence at the cost of speed and context length.
- Add a cross-encoder reranker or an NLI verifier as a future step; it is not
  implemented today.
