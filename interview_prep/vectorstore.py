"""Chroma vector store for cached interview content."""

from __future__ import annotations

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from interview_prep.config import Settings


def _collection_name(topic_key: str) -> str:
    safe = topic_key.replace(":", "_").replace(" ", "_")[:63]
    return f"interview_{safe}"


class InterviewVectorStore:
    def __init__(
        self,
        settings: Settings,
        embeddings: Embeddings,
        topic_key: str,
    ) -> None:
        self.settings = settings
        self.topic_key = topic_key
        self._collection = _collection_name(topic_key)
        self._embeddings = embeddings
        self._store = self._open_store()

    def _open_store(self) -> Chroma:
        return Chroma(
            collection_name=self._collection,
            embedding_function=self._embeddings,
            persist_directory=str(self.settings.chroma_persist_dir),
        )

    def _reset_store(self) -> None:
        client = chromadb.PersistentClient(
            path=str(self.settings.chroma_persist_dir)
        )
        try:
            client.delete_collection(self._collection)
        except Exception:
            pass
        self._store = self._open_store()
        print(
            f"Reset Chroma collection '{self._collection}' for new embedding model."
        )

    def add_documents(self, documents: list[Document]) -> int:
        if not documents:
            return 0
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        chunks = splitter.split_documents(documents)
        for chunk in chunks:
            chunk.metadata["topic_key"] = self.topic_key
        try:
            self._store.add_documents(chunks)
        except Exception as exc:
            if "dimension" not in str(exc).lower():
                raise
            self._reset_store()
            self._store.add_documents(chunks)
        return len(chunks)

    def similarity_search(self, query: str, k: int | None = None) -> list[Document]:
        limit = k if k is not None else self.settings.chroma_search_k
        return self._store.similarity_search(query, k=limit)

    def context_from_documents(
        self,
        documents: list[Document],
        *,
        max_chars: int | None = None,
    ) -> str:
        cap = max_chars if max_chars is not None else self.settings.max_context_chars
        parts: list[str] = []
        total = 0
        for doc in documents:
            source = doc.metadata.get("source", "unknown")
            block = f"[Source: {source}]\n{doc.page_content}"
            if total + len(block) > cap:
                remaining = cap - total
                if remaining > 200:
                    parts.append(block[:remaining])
                break
            parts.append(block)
            total += len(block)
        return "\n\n".join(parts)

    def get_context(self, query: str, k: int | None = None) -> str:
        try:
            docs = self.similarity_search(query, k=k)
            return self.context_from_documents(docs)
        except Exception as exc:
            if "dimension" in str(exc).lower():
                print(
                    "Note: Chroma index used a different embedding model; "
                    "reading stored chunks directly for migration."
                )
                return self.get_stored_context_fallback()
            raise

    def get_stored_context_fallback(self) -> str:
        """Read chunks without similarity search (e.g. embedding model changed)."""
        raw = self._store.get()
        if not raw or not raw.get("documents"):
            return ""
        docs: list[Document] = []
        for i, text in enumerate(raw["documents"]):
            if not text:
                continue
            meta = {}
            if raw.get("metadatas") and i < len(raw["metadatas"]):
                meta = raw["metadatas"][i] or {}
            docs.append(Document(page_content=text, metadata=meta))
        # Prefer most recently added chunks (end of index)
        docs = docs[-self.settings.chroma_search_k * 2 :]
        return self.context_from_documents(docs)

    def has_content(self) -> bool:
        try:
            data = self._store.get()
            return bool(data and data.get("ids"))
        except Exception:
            return False
