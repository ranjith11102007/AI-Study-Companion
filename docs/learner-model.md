# Learner Model

The learner model maintains a per-student, per-topic mastery estimate using
**Bayesian Knowledge Tracing (BKT)**, updated only from *graded* assessment
responses. It powers the mastery view, weak-topic detection and recommendations.

Implementation: `app/services/learner.py`. Tables: `topic_mastery`,
`recommendations`.

## BKT update

For a mastery probability `P(L)` (the chance the topic is learned):

```
P(correct) = P(L)·(1 − slip) + (1 − P(L))·guess

correct:    P(L | obs) = P(L)·(1 − slip) / P(correct)
incorrect:  P(L | obs) = P(L)·slip     / (1 − P(correct))

P(L) ← P(L | obs) + (1 − P(L | obs))·learn
```

| Parameter | Setting | Default | Meaning |
| --------- | ------- | ------- | ------- |
| prior | `bkt_prior_learned` | 0.30 | starting mastery for a new topic |
| learn | `bkt_learn_rate` | 0.20 | probability of learning per opportunity |
| guess | `bkt_guess` | 0.20 | P(correct \| not learned) |
| slip | `bkt_slip` | 0.10 | P(incorrect \| learned) |
| threshold | `bkt_mastery_threshold` | 0.70 | "mastered" cut-off |

Every graded question calls `record_evidence(...)`, which updates `mastery`,
increments `evidence_count` and `correct_count`, and stamps `last_practiced_at`.
Short-answer questions graded by the keyword heuristic still contribute — they
are real (if approximate) evidence.

## Weak vs untested

`weak_topics` deliberately requires **evidence**: a topic is weak only if
`evidence_count ≥ 2` **and** `mastery < bkt_mastery_threshold`. A topic with no
answers is *untested*, never *weak*. This avoids mislabelling brand-new topics.

## Recommendations

`generate_recommendations` rebuilds a student's list from real state:

| kind | condition | priority |
| ---- | --------- | -------- |
| `weak_topic` | evidence ≥ 2 and mastery < threshold | scaled by the mastery gap and evidence |
| `diagnostic` | topic appears in the course's questions but has no graded evidence | 0.5 |
| `revision` | topic practised but idle for ≥ 2 days' worth of recency | 0.5→low |

Priorities are relative ranks used for ordering; they are not calibrated
probabilities.

## Honest limitations

- BKT assumes a single skill per topic and independent opportunities; real
  learning has prerequisites and transfer. Topics here are coarse labels.
- Parameters are sensible defaults, **not fit** to each student; with little
  data mastery moves quickly. `evidence_count` is always shown so students can
  judge confidence.
- Topic labels come from generated questions (and the editable topic graph), so
  quality depends on the source material and the local model.
- There is no forgetting curve beyond the simple `revision` recency rule.

## Inspecting it

- `GET /api/courses/{id}/mastery` → topics, weak, strong, untested.
- `GET /api/courses/{id}/recommendations` (add `?refresh=true` to rebuild).
- `backend/app/services/evaluation.py::simulate_profiles` replays synthetic
  students through the real update for reproducible trajectories.
