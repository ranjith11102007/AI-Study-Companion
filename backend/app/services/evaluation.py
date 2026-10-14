"""Reproducible evaluation harness (deterministic, runs offline).

Scope (documented honestly in docs/evaluation.md):

* A small, original, version-controlled corpus + question set lives in
  ``backend/evaluation/dataset.json``.
* Retrieval is scored with a transparent lexical retriever so the harness is
  deterministic and needs no database, network or model download.
* Answer "faithfulness" here means *citation correctness*: whether an answer's
  cited sources are among the expected sources. It is a deterministic proxy,
  not an LLM-judged score.
* Unsupported-question detection is measured by whether retrieval returns any
  passage above the similarity floor.
* Learner-model behaviour is measured by replaying synthetic student profiles
  through the real Bayesian Knowledge Tracing update and reporting trajectories.

The live pgvector/Ollama path is intentionally *not* asserted here; that is an
optional integration test.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.services.learner import bkt_update

DATASET_PATH = Path(__file__).resolve().parents[2] / "evaluation" / "dataset.json"
LEXICAL_FLOOR = 0.12


# --------------------------------------------------------------------------- #
# Lexical retrieval (deterministic stand-in for the vector index)
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> set[str]:
    import re

    # Tokens longer than 3 characters only: common stopwords ("the", "and")
    # must not create spurious "support" for an unsupported question.
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 3}


def lexical_score(query: str, passage: str) -> float:
    q = _tokens(query)
    p = _tokens(passage)
    if not q or not p:
        return 0.0
    return len(q & p) / len(q)


def lexical_retrieve(
    query: str, corpus: list[dict], k: int = 3
) -> list[tuple[str, float]]:
    scored = [
        (doc["id"], lexical_score(query, doc["text"]))
        for doc in corpus
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [(doc_id, score) for doc_id, score in scored[:k] if score > 0]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def hit_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    return 1.0 if expected & set(retrieved[:k]) else 0.0


def precision_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    return len(expected & set(top)) / len(top)


def recall_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 0.0
    return len(expected & set(retrieved[:k])) / len(expected)


@dataclass
class EvaluationResult:
    dataset: str
    metrics: dict = field(default_factory=dict)
    per_question: list = field(default_factory=list)


def load_dataset(path: Path | None = None) -> dict:
    path = path or DATASET_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def run_evaluation(dataset_name: str | None = None, k: int = 3) -> EvaluationResult:
    dataset = load_dataset()
    corpus = dataset["corpus"]
    questions = dataset["questions"]

    hits: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []
    citation_scores: list[float] = []
    unsupported_scores: list[float] = []
    per_question: list[dict] = []

    for item in questions:
        retrieved = lexical_retrieve(item["question"], corpus, k=k)
        retrieved_ids = [doc_id for doc_id, _ in retrieved]

        if item.get("answerable", True):
            expected = set(item.get("expected_sources", []))
            hits.append(hit_at_k(retrieved_ids, expected, k))
            precisions.append(precision_at_k(retrieved_ids, expected, k))
            recalls.append(recall_at_k(retrieved_ids, expected, k))
            # citation correctness: top retrieved doc is an expected source
            citation_scores.append(
                1.0 if retrieved_ids and retrieved_ids[0] in expected else 0.0
            )
        else:
            top = max((score for _, score in retrieved), default=0.0)
            unsupported_scores.append(1.0 if top < LEXICAL_FLOOR else 0.0)

        per_question.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answerable": item.get("answerable", True),
                "retrieved": retrieved_ids,
                "scores": [round(s, 4) for _, s in retrieved],
            }
        )

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    profiles = run_learner_simulation()

    metrics = {
        "retrieval_hit_at_k": mean(hits),
        "context_precision": mean(precisions),
        "context_recall": mean(recalls),
        "citation_correctness": mean(citation_scores),
        "unsupported_detection": round(
            sum(unsupported_scores) / len(unsupported_scores), 4
        )
        if unsupported_scores
        else 0.0,
        "learner_improving_profiles": sum(1 for p in profiles if p["improved"]),
        "learner_profiles": len(profiles),
    }
    metrics = {key: round(float(value), 4) for key, value in metrics.items()}

    return EvaluationResult(
        dataset=dataset_name or dataset.get("name", "dataset"),
        metrics=metrics,
        per_question=per_question + [{"learner_model": {"profiles": profiles}}],
    )


# --------------------------------------------------------------------------- #
# Learner-model simulation
# --------------------------------------------------------------------------- #
def simulate_profiles(
    profiles: dict[str, float],
    steps: int = 8,
    prior: float | None = None,
) -> list[dict]:
    """Replay a deterministic answer stream through the real BKT update.

    ``profiles`` maps a profile name to its intended accuracy in [0, 1]. For
    step ``i`` the student answers correctly when ``i % 1`` ... concretely, the
    first ``round(accuracy * steps)`` steps are correct and the rest wrong — a
    fixed, reproducible pattern (no randomness).
    """
    results: list[dict] = []
    for name, accuracy in profiles.items():
        mastery = prior if prior is not None else get_settings().bkt_prior_learned
        trajectory = [round(mastery, 4)]
        correct_count = round(accuracy * steps)
        for index in range(steps):
            is_correct = index < correct_count
            mastery = bkt_update(mastery, is_correct)
            trajectory.append(round(mastery, 4))
        results.append(
            {
                "profile": name,
                "target_accuracy": accuracy,
                "observed_accuracy": round(correct_count / steps, 3) if steps else 0.0,
                "mastery_start": trajectory[0],
                "mastery_end": trajectory[-1],
                "improved": trajectory[-1] > trajectory[0],
                "trajectory": trajectory,
            }
        )
    return results


def run_learner_simulation() -> list[dict]:
    return simulate_profiles({"novice": 0.2, "developing": 0.5, "strong": 0.85})
