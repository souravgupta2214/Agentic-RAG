"""Question-level deduplication across refreshes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interview_prep.qa_store import StoredQuestion

_PREFIX_RE = re.compile(
    r"^(what is|what are|explain|describe|define|how do you|how would you)\s+",
    re.IGNORECASE,
)


def normalize_question(text: str) -> str:
    t = text.lower().strip()
    t = _PREFIX_RE.sub("", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def question_hash(text: str) -> str:
    return hashlib.sha256(normalize_question(text).encode()).hexdigest()[:16]


def merge_sources(sources: list[str]) -> str:
    seen: list[str] = []
    for s in sources:
        s = s.strip()
        if s and s not in seen:
            seen.append(s)
    return " | ".join(seen) if seen else "Web"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class _QuestionVectors:
    ids: list[str]
    vectors: list[list[float]]


def build_existing_vectors(
    existing: list[StoredQuestion],
    embeddings,
) -> _QuestionVectors:
    ids = [q.id for q in existing]
    if not existing:
        return _QuestionVectors(ids=[], vectors=[])
    vectors = embeddings.embed_documents([q.question for q in existing])
    return _QuestionVectors(ids=ids, vectors=vectors)


def is_duplicate_question(
    question: str,
    existing: list[StoredQuestion],
    embeddings,
    threshold: float,
    *,
    cached: _QuestionVectors | None = None,
) -> int | None:
    """Return index of duplicate in existing, or None."""
    norm = normalize_question(question)
    new_id = question_hash(question)
    for i, item in enumerate(existing):
        if item.id == new_id or normalize_question(item.question) == norm:
            return i

    if not existing:
        return None

    cache = cached or build_existing_vectors(existing, embeddings)
    new_vec = embeddings.embed_query(question)
    for i, vec in enumerate(cache.vectors):
        if _cosine_similarity(new_vec, vec) >= threshold:
            return i
    return None
