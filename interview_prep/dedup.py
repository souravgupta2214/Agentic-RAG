"""Remove near-duplicate content from scraped documents."""

from __future__ import annotations

import hashlib
from difflib import SequenceMatcher

from langchain_core.documents import Document

from interview_prep.config import Settings


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a[:2000]), _normalize(b[:2000])).ratio()


def deduplicate_documents(
    documents: list[Document],
    settings: Settings,
) -> list[Document]:
    if not documents:
        return []

    threshold = settings.dedup_similarity_threshold
    unique: list[Document] = []
    seen_hashes: set[str] = set()

    for doc in documents:
        h = _content_hash(doc.page_content)
        if h in seen_hashes:
            continue

        is_dup = False
        for kept in unique:
            if _similarity(doc.page_content, kept.page_content) >= threshold:
                is_dup = True
                break
        if is_dup:
            continue

        seen_hashes.add(h)
        unique.append(doc)

    return unique
