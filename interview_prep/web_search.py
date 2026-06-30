"""Search the web for interview questions related to a topic."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from ddgs import DDGS

from interview_prep.config import Settings

# Rotated on each refresh so DuckDuckGo tends to surface different pages.
_REFRESH_QUERY_SUFFIXES = (
    "interview questions and answers",
    "technical interview questions",
    "coding interview FAQ",
    "interview preparation guide",
    "common interview questions",
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def normalize_url(url: str) -> str:
    """Canonical form for comparing / excluding URLs."""
    parsed = urlparse(url.strip().lower())
    host = parsed.netloc.removeprefix("www.")
    path = parsed.path.rstrip("/") or ""
    return f"{host}{path}"


def build_search_query(
    topic: str,
    subtopic: str | None,
    *,
    refresh_index: int = 0,
) -> str:
    parts = [topic.strip()]
    if subtopic:
        parts.append(subtopic.strip())
    suffix = _REFRESH_QUERY_SUFFIXES[refresh_index % len(_REFRESH_QUERY_SUFFIXES)]
    parts.append(suffix)
    return " ".join(parts)


def search_interview_urls(
    topic: str,
    subtopic: str | None,
    num_sites: int,
    settings: Settings,
    *,
    exclude_urls: set[str] | None = None,
    refresh_index: int = 0,
) -> list[SearchResult]:
    """
    Find interview URLs. When exclude_urls is set (refresh runs), skips
    previously visited sites and pulls deeper from search results.
    """
    exclude = exclude_urls or set()
    query = build_search_query(topic, subtopic, refresh_index=refresh_index)
    # Pull extra pages so we can skip already-visited URLs on refresh.
    fetch_limit = max(num_sites * 4, settings.max_results_per_query)
    results: list[SearchResult] = []
    seen_normalized: set[str] = set()

    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=fetch_limit):
            url = item.get("href", "").strip()
            if not url:
                continue
            norm = normalize_url(url)
            if norm in seen_normalized or norm in exclude:
                continue
            seen_normalized.add(norm)
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("body", ""),
                )
            )
            if len(results) >= num_sites:
                break

    return results
