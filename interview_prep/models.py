"""Data models and LLM extraction for interview Q&A."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class InterviewQA:
    level: str
    question: str
    answer: str
    source: str


EXTRACT_SYSTEM_PROMPT = """You are an expert technical interview coach.
Extract interview questions and answers ONLY from the provided source text.

Rules:
- Use only facts present in the source text; do not invent topics.
- Assign level: Easy, Medium, or Hard.
- Each item needs question, answer, and source URL (use "Web" if unknown).
- Output ONLY a valid JSON array. No markdown fences, no commentary.

Schema per item:
{"level": "Easy|Medium|Hard", "question": "...", "answer": "...", "source": "..."}
"""


def parse_qa_json(raw: str) -> list[InterviewQA]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    items: list[InterviewQA] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        q = str(entry.get("question", "")).strip()
        a = str(entry.get("answer", "")).strip()
        if not q or not a:
            continue
        items.append(
            InterviewQA(
                level=str(entry.get("level", "Medium")).strip() or "Medium",
                question=q,
                answer=a,
                source=str(entry.get("source", "Web")).strip() or "Web",
            )
        )
    return items


def extract_qa_from_batch(
    llm: BaseChatModel,
    topic: str,
    subtopic: str | None,
    batch_context: str,
    *,
    max_items: int,
    existing_question_lines: str,
) -> list[InterviewQA]:
    """Extract new Q&A from one web batch only (bounded LLM call)."""
    label = topic if not subtopic else f"{topic} / {subtopic}"
    user_content = f"""Topic: {label}

Extract up to {max_items} interview Q&A items from the source text below.
Do NOT repeat any question that already exists in the list.

--- Already in question bank (do not duplicate) ---
{existing_question_lines}

--- New source text (this batch only) ---
{batch_context}
"""

    response = llm.invoke(
        [
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    content = (
        response.content if isinstance(response.content, str) else str(response.content)
    )
    items = parse_qa_json(content)
    return items[:max_items]
