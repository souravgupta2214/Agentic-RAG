"""Load application settings from config.yaml and environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERVIEW_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    config_path: Path = Field(default=Path("config.yaml"))

    pdf_output_dir: Path = Field(default=Path("./data/pdfs"))
    qa_store_dir: Path = Field(default=Path("./data/qa"))
    state_file: Path = Field(default=Path("./data/search_state.json"))
    chroma_persist_dir: Path = Field(default=Path("./data/chroma"))

    llm_provider: str = Field(default="ollama")
    llm_model: str = Field(default="llama3.2")
    llm_base_url: str = Field(default="http://localhost:11434")
    llm_temperature: float = Field(default=0.2)

    embeddings_provider: str = Field(default="ollama")
    embeddings_model: str = Field(default="nomic-embed-text")
    embeddings_base_url: str = Field(default="http://localhost:11434")

    max_results_per_query: int = Field(default=10)
    request_timeout_seconds: int = Field(default=15)
    user_agent: str = Field(default="InterviewPrepBot/1.0")

    dedup_similarity_threshold: float = Field(default=0.85)
    question_dedup_threshold: float = Field(default=0.88)

    chunk_size: int = Field(default=2000)
    chunk_overlap: int = Field(default=100)
    chroma_search_k: int = Field(default=6)
    max_context_chars: int = Field(default=6000)
    max_new_questions_per_run: int = Field(default=8)
    max_questions_per_topic: int = Field(default=80)
    scrape_workers: int = Field(default=3)

    @classmethod
    def load(cls, config_path: Path | None = None) -> Settings:
        path = config_path or Path(os.getenv("INTERVIEW_CONFIG", "config.yaml"))
        raw = _load_yaml_config(path)

        paths = raw.get("paths", {})
        llm = raw.get("llm", {})
        emb = raw.get("embeddings", {})
        web = raw.get("web", {})
        dedup = raw.get("dedup", {})
        pipeline = raw.get("pipeline", {})
        vectorstore = raw.get("vectorstore", {})

        return cls(
            config_path=path,
            pdf_output_dir=Path(paths.get("pdf_output_dir", "./data/pdfs")),
            qa_store_dir=Path(paths.get("qa_store_dir", "./data/qa")),
            state_file=Path(paths.get("state_file", "./data/search_state.json")),
            chroma_persist_dir=Path(
                paths.get("chroma_persist_dir", "./data/chroma")
            ),
            llm_provider=llm.get("provider", "ollama"),
            llm_model=llm.get("model", "llama3.2"),
            llm_base_url=llm.get("base_url", "http://localhost:11434"),
            llm_temperature=float(llm.get("temperature", 0.2)),
            embeddings_provider=emb.get("provider", "ollama"),
            embeddings_model=emb.get("model", "nomic-embed-text"),
            embeddings_base_url=emb.get("base_url", "http://localhost:11434"),
            max_results_per_query=int(web.get("max_results_per_query", 10)),
            request_timeout_seconds=int(web.get("request_timeout_seconds", 15)),
            user_agent=web.get("user_agent", "InterviewPrepBot/1.0"),
            dedup_similarity_threshold=float(
                dedup.get("similarity_threshold", 0.85)
            ),
            question_dedup_threshold=float(
                dedup.get("question_similarity_threshold", 0.88)
            ),
            chunk_size=int(vectorstore.get("chunk_size", 2000)),
            chunk_overlap=int(vectorstore.get("chunk_overlap", 100)),
            chroma_search_k=int(pipeline.get("chroma_search_k", 6)),
            max_context_chars=int(pipeline.get("max_context_chars", 6000)),
            max_new_questions_per_run=int(
                pipeline.get("max_new_questions_per_run", 8)
            ),
            max_questions_per_topic=int(pipeline.get("max_questions_per_topic", 80)),
            scrape_workers=int(web.get("scrape_workers", 3)),
        )

    def ensure_dirs(self) -> None:
        self.pdf_output_dir.mkdir(parents=True, exist_ok=True)
        self.qa_store_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def topic_key(self, topic: str, subtopic: str | None) -> str:
        sub = (subtopic or "").strip().lower()
        base = topic.strip().lower()
        return f"{base}::{sub}" if sub else base

    def pdf_path_for(self, topic: str, subtopic: str | None) -> Path:
        safe = self.topic_key(topic, subtopic).replace("::", "_").replace(" ", "-")
        return self.pdf_output_dir / f"{safe}.pdf"

    def qa_store_path_for(self, topic: str, subtopic: str | None) -> Path:
        safe = self.topic_key(topic, subtopic).replace("::", "_").replace(" ", "-")
        return self.qa_store_dir / f"{safe}.json"
