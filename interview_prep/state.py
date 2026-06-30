"""Persist which topics have been searched and when."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TopicRecord:
    topic: str
    subtopic: str | None
    topic_key: str
    pdf_path: str
    last_web_search: str | None
    search_count: int = 0
    visited_urls: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> TopicRecord:
        visited = data.get("visited_urls")
        if visited is None:
            visited = []
        return cls(
            topic=data["topic"],
            subtopic=data.get("subtopic"),
            topic_key=data["topic_key"],
            pdf_path=data["pdf_path"],
            last_web_search=data.get("last_web_search"),
            search_count=int(data.get("search_count", 0)),
            visited_urls=list(visited),
        )


class SearchState:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._records: dict[str, TopicRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        with self.state_file.open(encoding="utf-8") as f:
            raw = json.load(f)
        for key, data in raw.get("topics", {}).items():
            self._records[key] = TopicRecord.from_dict(data)

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "topics": {k: asdict(v) for k, v in self._records.items()},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def get(self, topic_key: str) -> TopicRecord | None:
        return self._records.get(topic_key)

    def has_searched(self, topic_key: str) -> bool:
        return topic_key in self._records

    def get_visited_urls(self, topic_key: str) -> set[str]:
        record = self._records.get(topic_key)
        if not record or not record.visited_urls:
            return set()
        return set(record.visited_urls)

    def register_search(
        self,
        topic: str,
        subtopic: str | None,
        topic_key: str,
        pdf_path: Path,
        *,
        web_fetched: bool,
        new_urls: list[str] | None = None,
    ) -> TopicRecord:
        now = datetime.now(timezone.utc).isoformat()
        existing = self._records.get(topic_key)
        merged_urls: list[str] = list(existing.visited_urls or []) if existing else []
        if new_urls:
            seen = set(merged_urls)
            for url in new_urls:
                if url not in seen:
                    merged_urls.append(url)
                    seen.add(url)

        if existing:
            record = TopicRecord(
                topic=topic,
                subtopic=subtopic,
                topic_key=topic_key,
                pdf_path=str(pdf_path),
                last_web_search=now if web_fetched else existing.last_web_search,
                search_count=existing.search_count + (1 if web_fetched else 0),
                visited_urls=merged_urls,
            )
        else:
            record = TopicRecord(
                topic=topic,
                subtopic=subtopic,
                topic_key=topic_key,
                pdf_path=str(pdf_path),
                last_web_search=now if web_fetched else None,
                search_count=1 if web_fetched else 0,
                visited_urls=merged_urls,
            )
        self._records[topic_key] = record
        self.save()
        return record
