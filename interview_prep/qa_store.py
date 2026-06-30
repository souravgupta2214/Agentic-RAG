"""Persistent Q&A store per topic (source of truth; PDF is export only)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.embeddings import Embeddings

from interview_prep.config import Settings
from interview_prep.models import InterviewQA
from interview_prep.question_dedup import (
    build_existing_vectors,
    is_duplicate_question,
    merge_sources,
    question_hash,
)


@dataclass
class StoredQuestion:
    id: str
    level: str
    question: str
    answer: str
    sources: list[str]

    def to_interview_qa(self) -> InterviewQA:
        return InterviewQA(
            level=self.level,
            question=self.question,
            answer=self.answer,
            source=merge_sources(self.sources),
        )

    @classmethod
    def from_interview_qa(cls, item: InterviewQA) -> StoredQuestion:
        sources = [s.strip() for s in item.source.split("|") if s.strip()]
        if not sources:
            sources = [item.source or "Web"]
        return cls(
            id=question_hash(item.question),
            level=item.level,
            question=item.question,
            answer=item.answer,
            sources=sources,
        )


class QAStore:
    def __init__(self, path: Path, topic_key: str) -> None:
        self.path = path
        self.topic_key = topic_key
        self._questions: list[StoredQuestion] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            data = json.load(f)
        for row in data.get("questions", []):
            self._questions.append(
                StoredQuestion(
                    id=row["id"],
                    level=row["level"],
                    question=row["question"],
                    answer=row["answer"],
                    sources=list(row.get("sources", [])),
                )
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "topic_key": self.topic_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "questions": [asdict(q) for q in self._questions],
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def __len__(self) -> int:
        return len(self._questions)

    def all_items(self) -> list[InterviewQA]:
        return [q.to_interview_qa() for q in self._questions]

    def question_titles_for_prompt(self, limit: int = 40) -> str:
        if not self._questions:
            return "(none)"
        lines = [f"- {q.question}" for q in self._questions[:limit]]
        if len(self._questions) > limit:
            lines.append(f"... and {len(self._questions) - limit} more")
        return "\n".join(lines)

    def add_items(
        self,
        candidates: list[InterviewQA],
        embeddings: Embeddings,
        settings: Settings,
    ) -> tuple[int, int]:
        """Returns (added_count, skipped_duplicate_count)."""
        added = 0
        skipped = 0
        cached = build_existing_vectors(self._questions, embeddings)
        for item in candidates:
            if len(self._questions) >= settings.max_questions_per_topic:
                break
            stored = StoredQuestion.from_interview_qa(item)
            dup_idx = is_duplicate_question(
                stored.question,
                self._questions,
                embeddings,
                settings.question_dedup_threshold,
                cached=cached,
            )
            if dup_idx is not None:
                existing = self._questions[dup_idx]
                for src in stored.sources:
                    if src not in existing.sources:
                        existing.sources.append(src)
                if len(stored.answer) > len(existing.answer):
                    existing.answer = stored.answer
                skipped += 1
                continue
            self._questions.append(stored)
            cached.ids.append(stored.id)
            cached.vectors.append(embeddings.embed_query(stored.question))
            added += 1
        if added or skipped:
            self.save()
        return added, skipped
