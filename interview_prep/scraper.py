"""Extract text content from web pages."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from interview_prep.config import Settings
from interview_prep.web_search import SearchResult


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str


def _clean_text(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw)
    return text.strip()


def scrape_url(url: str, settings: Settings) -> ScrapedPage | None:
    headers = {"User-Agent": settings.user_agent}
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else url
    paragraphs = [
        p.get_text(strip=True) for p in soup.find_all(["p", "li", "h1", "h2", "h3"])
    ]
    text = _clean_text(" ".join(p for p in paragraphs if len(p) > 30))
    if len(text) < 100:
        text = _clean_text(soup.get_text(separator=" "))
    if len(text) < 50:
        return None

    return ScrapedPage(url=url, title=title, text=text[:30000])


def scrape_search_results(
    results: list[SearchResult],
    settings: Settings,
) -> list[Document]:
    documents: list[Document] = []
    workers = max(1, min(settings.scrape_workers, len(results) or 1))

    def _scrape_one(result: SearchResult) -> Document | None:
        page = scrape_url(result.url, settings)
        if page is None:
            if result.snippet:
                return Document(
                    page_content=result.snippet,
                    metadata={"source": result.url, "title": result.title},
                )
            return None
        return Document(
            page_content=page.text,
            metadata={"source": page.url, "title": page.title},
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scrape_one, r): r for r in results}
        for future in as_completed(futures):
            doc = future.result()
            if doc is not None:
                documents.append(doc)

    return documents
