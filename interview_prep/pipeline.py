"""Orchestrate web fetch, vector cache, Q&A store, and PDF generation."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from interview_prep.config import Settings
from interview_prep.dedup import deduplicate_documents
from interview_prep.llm_factory import create_chat_model, create_embeddings
from interview_prep.models import extract_qa_from_batch
from interview_prep.pdf_io import generate_interview_pdf
from interview_prep.qa_store import QAStore
from interview_prep.scraper import scrape_search_results
from interview_prep.state import SearchState
from interview_prep.vectorstore import InterviewVectorStore
from interview_prep.web_search import (
    build_search_query,
    normalize_url,
    search_interview_urls,
)


@dataclass
class PipelineResult:
    pdf_path: str
    question_count: int
    used_web: bool
    used_cache: bool
    message: str
    added_this_run: int = 0


class InterviewPrepPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.settings.ensure_dirs()
        self.state = SearchState(self.settings.state_file)
        self.llm = create_chat_model(self.settings)
        self.embeddings = create_embeddings(self.settings)

    def run(
        self,
        topic: str,
        subtopic: str | None = None,
        num_sites: int = 3,
        *,
        refresh_internet: bool = False,
    ) -> PipelineResult:
        topic_key = self.settings.topic_key(topic, subtopic)
        pdf_path = self.settings.pdf_path_for(topic, subtopic)
        query = build_search_query(topic, subtopic)

        qa_store = QAStore(self.settings.qa_store_path_for(topic, subtopic), topic_key)
        vector_store = InterviewVectorStore(
            self.settings, self.embeddings, topic_key
        )
        previously_searched = self.state.has_searched(topic_key)
        should_fetch_web = refresh_internet or not previously_searched

        used_web = False
        new_documents: list[Document] = []

        if should_fetch_web:
            record = self.state.get(topic_key)
            refresh_index = record.search_count if record and refresh_internet else 0
            exclude_urls: set[str] = set()
            if refresh_internet:
                exclude_urls = self.state.get_visited_urls(topic_key)
                if exclude_urls:
                    print(
                        f"Refresh: skipping {len(exclude_urls)} previously visited site(s), "
                        "searching for new sources."
                    )
            search_query = build_search_query(
                topic, subtopic, refresh_index=refresh_index
            )
            print(f"Searching web ({num_sites} new sites) for: {search_query}")
            search_results = search_interview_urls(
                topic,
                subtopic,
                num_sites,
                self.settings,
                exclude_urls=exclude_urls if refresh_internet else None,
                refresh_index=refresh_index,
            )
            if not search_results:
                if refresh_internet and (
                    vector_store.has_content() or len(qa_store) > 0
                ):
                    print(
                        "No new websites found. Exporting PDF from question store."
                    )
                elif not vector_store.has_content() and len(qa_store) == 0:
                    return PipelineResult(
                        pdf_path=str(pdf_path),
                        question_count=0,
                        used_web=False,
                        used_cache=False,
                        message="No web results found and no cached data.",
                    )
            else:
                new_documents = scrape_search_results(search_results, self.settings)
                new_documents = deduplicate_documents(new_documents, self.settings)
                if new_documents:
                    added = vector_store.add_documents(new_documents)
                    print(f"Stored {added} chunks in Chroma for '{topic_key}'.")
                    used_web = True
                fetched_urls = [normalize_url(r.url) for r in search_results]
                self.state.register_search(
                    topic,
                    subtopic,
                    topic_key,
                    pdf_path,
                    web_fetched=True,
                    new_urls=fetched_urls,
                )
        else:
            print(
                f"Using cached data for '{topic_key}'. "
                "Pass --refresh-internet to fetch new content."
            )
            self.state.register_search(
                topic,
                subtopic,
                topic_key,
                pdf_path,
                web_fetched=False,
            )

        used_cache = bool(vector_store.has_content() or len(qa_store) > 0)
        added_this_run = 0

        if new_documents:
            batch_context = vector_store.context_from_documents(new_documents)
            print(
                f"Extracting up to {self.settings.max_new_questions_per_run} "
                "new Q&A from this batch..."
            )
            candidates = extract_qa_from_batch(
                self.llm,
                topic,
                subtopic,
                batch_context,
                max_items=self.settings.max_new_questions_per_run,
                existing_question_lines=qa_store.question_titles_for_prompt(),
            )
            if not candidates:
                print(
                    "Warning: LLM returned no parseable Q&A from this batch. "
                    "PDF still updated from existing question store."
                )
            added_this_run, skipped = qa_store.add_items(
                candidates, self.embeddings, self.settings
            )
            print(f"Added {added_this_run} new question(s), skipped {skipped} duplicate(s).")
        elif len(qa_store) == 0 and vector_store.has_content():
            print("Migrating from Chroma cache (one-time extract)...")
            batch_context = vector_store.get_context(query)[
                : min(4000, self.settings.max_context_chars)
            ]
            candidates = extract_qa_from_batch(
                self.llm,
                topic,
                subtopic,
                batch_context,
                max_items=self.settings.max_new_questions_per_run,
                existing_question_lines="(none)",
            )
            added_this_run, skipped = qa_store.add_items(
                candidates, self.embeddings, self.settings
            )
            print(f"Added {added_this_run} question(s), skipped {skipped} duplicate(s).")
        elif not should_fetch_web and len(qa_store) > 0:
            print("Cache-only run: exporting PDF from question store (no LLM).")

        items = qa_store.all_items()
        if not items:
            return PipelineResult(
                pdf_path=str(pdf_path),
                question_count=0,
                used_web=used_web,
                used_cache=used_cache,
                message="No questions in store. Check Ollama or try --refresh-internet.",
                added_this_run=added_this_run,
            )

        generate_interview_pdf(topic, subtopic, items, pdf_path)
        print(f"PDF written to: {pdf_path} ({len(items)} total questions)")

        return PipelineResult(
            pdf_path=str(pdf_path),
            question_count=len(items),
            used_web=used_web,
            used_cache=used_cache,
            message="Success",
            added_this_run=added_this_run,
        )
