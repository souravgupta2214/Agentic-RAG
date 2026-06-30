"""Load existing PDFs and generate formatted interview PDFs."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from interview_prep.models import InterviewQA


def load_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _safe_filename(text: str) -> str:
    return re.sub(r"[^\w\-]+", "-", text.strip().lower()).strip("-")


def generate_interview_pdf(
    topic: str,
    subtopic: str | None,
    items: list[InterviewQA],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
    )
    level_style = ParagraphStyle(
        "Level",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1a5276"),
        spaceBefore=10,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Heading3"],
        fontSize=10,
        textColor=colors.HexColor("#2874a6"),
        spaceBefore=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    source_style = ParagraphStyle(
        "Source",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=12,
    )

    story: list = []
    heading = f"Interview Questions: {topic}"
    if subtopic:
        heading += f" — {subtopic}"
    story.append(Paragraph(_escape(heading), title_style))
    story.append(Spacer(1, 8))

    for idx, item in enumerate(items, 1):
        story.append(
            Paragraph(_escape(f"Question {idx} — Level: {item.level}"), level_style)
        )
        story.append(Paragraph("<b>Question</b>", label_style))
        story.append(Paragraph(_escape(item.question), body_style))
        story.append(Paragraph("<b>Answer</b>", label_style))
        story.append(Paragraph(_escape(item.answer), body_style))
        story.append(Paragraph("<b>Source</b>", label_style))
        story.append(Paragraph(_escape(item.source), source_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return output_path


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
