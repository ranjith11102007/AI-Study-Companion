# Evaluation

The evaluation harness (`app/services/evaluation.py`) is **deterministic and
offline**: it needs no database, no network and no model download, so it runs in
CI and produces the same numbers every time. It is exposed at
`POST /api/evaluate` and stored in the `evaluation_runs` table.

## Dataset

`backend/evaluation/dataset.json` is a small, **original** corpus (8 passages)
with 10 questions: single-source and multi-source answerable questions, plus
deliberately **unsupported** questions whose answers are absent from the corpus.

## Metrics

| Metric | Definition |
| ------ | ---------- |
| `retrieval_hit_at_k` | fraction of answerable questions whose expected source appears in the top-k retrieved passages |
| `context_precision` | expected sources / retrieved (top-k) |
| `context_recall` | expected sources found / expected sources |
| `citation_correctness` | fraction of answerable questions whose top retrieved passage is an expected source (a deterministic proxy for faithful citation) |
| `unsupported_detection` | fraction of unsupported questions whose best score falls below the relevance floor (i.e. correctly *not* answered) |
| `learner_improving_profiles` | how many of the 3 synthetic student profiles increase their BKT mastery over the session |

## Current results

Run with `k = 3` on the bundled dataset:

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

Interpretation:

- **Hit@3 = 1.00** — every answerable question retrieves at least one expected
  passage.
- **Context precision 0.57** — retrieval also returns some topically-adjacent but
  non-expected passages; that is expected without a reranker.
- **Context recall 0.96** — one expected source in a multi-source question is not
  always inside the top-3.
- **Citation correctness 1.00 / unsupported detection 1.00** — the top passage is
  an expected source for every answerable question, and no unsupported question
  is answered from the corpus.
- **Learner model 2/3 improving** — the "novice" profile (0% correct) is expected
  to *decrease* mastery, so 2 of 3 improving is the correct outcome, not a bug.

## What this does and does not measure

It validates the **metric pipeline and the retrieval/citation logic** over a
controlled corpus using a transparent lexical retriever. It does **not**:

- exercise the live pgvector index or the Ollama models (that is an optional
  integration path), or
- LLM-judge answer faithfulness. "Citation correctness" is a deterministic proxy,
  not an NLI proof (see `docs/grounding-and-citations.md`).

Extending the harness with a live-vector mode and an optional local NLI/LLM
judge is listed as future work. The harness never fabricates scores: it always
recomputes from the dataset.
