#!/usr/bin/env python3
"""Convert docs/END_TO_END_FLOW.md to PDF (renders Mermaid via browser)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import markdown
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "END_TO_END_FLOW.md"
DEFAULT_OUTPUT = ROOT / "docs" / "END_TO_END_FLOW.pdf"

MERMAID_PLACEHOLDER = "<!--MERMAID_BLOCK_{i}-->"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Interview Prep — End-to-End Flow</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.3/dist/mermaid.min.js"></script>
  <style>
    @page {{ size: A4; margin: 18mm; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 11pt;
      line-height: 1.45;
      color: #1a1a1a;
      padding: 0 8px;
    }}
    h1 {{ font-size: 22pt; border-bottom: 2px solid #2874a6; padding-bottom: 6px; }}
    h2 {{ font-size: 16pt; color: #1a5276; margin-top: 1.4em; page-break-after: avoid; }}
    h3 {{ font-size: 13pt; color: #2874a6; page-break-after: avoid; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }}
    th, td {{ border: 1px solid #bdc3c7; padding: 6px 8px; text-align: left; }}
    th {{ background: #ebf5fb; }}
    code {{ background: #f4f6f7; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }}
    pre:not(.mermaid) {{
      background: #f8f9fa;
      border: 1px solid #dfe6e9;
      border-radius: 4px;
      padding: 10px;
      font-size: 8.5pt;
      white-space: pre-wrap;
    }}
    .mermaid {{
      background: #fff;
      border: 1px solid #d5dbdb;
      border-radius: 4px;
      padding: 12px;
      margin: 1em 0;
      text-align: center;
      page-break-inside: avoid;
    }}
    .mermaid-error {{
      color: #c0392b;
      font-size: 9pt;
      padding: 8px;
      border: 1px solid #e74c3c;
      background: #fdf2f2;
    }}
    hr {{ border: none; border-top: 1px solid #dfe6e9; margin: 1.5em 0; }}
  </style>
</head>
<body>
{body}
<script>
  mermaid.initialize({{
    startOnLoad: false,
    theme: "default",
    securityLevel: "loose",
    flowchart: {{ useMaxWidth: true, htmlLabels: false }},
    sequence: {{ useMaxWidth: true }}
  }});
  document.addEventListener("DOMContentLoaded", async () => {{
    const nodes = document.querySelectorAll(".mermaid");
    for (const node of nodes) {{
      try {{
        const id = "m" + Math.random().toString(36).slice(2, 9);
        const {{ svg }} = await mermaid.render(id, node.textContent.trim());
        node.innerHTML = svg;
      }} catch (err) {{
        node.outerHTML =
          '<div class="mermaid-error">Diagram error: ' + err.message + '</div>';
      }}
    }}
    window.__mermaidDone = true;
  }});
</script>
</body>
</html>
"""


def _extract_mermaid_blocks(md_text: str) -> tuple[str, list[str]]:
    """Pull mermaid fences out before markdown runs; keep source unescaped."""
    blocks: list[str] = []
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

    def repl(match: re.Match) -> str:
        blocks.append(match.group(1).strip())
        return MERMAID_PLACEHOLDER.format(i=len(blocks) - 1)

    stripped = pattern.sub(repl, md_text)
    return stripped, blocks


def _restore_mermaid_blocks(html: str, blocks: list[str]) -> str:
    for i, code in enumerate(blocks):
        # Raw diagram text inside div — do NOT HTML-escape (mermaid parses it)
        safe = code.replace("</div>", "</ div>")
        div = f'<div class="mermaid">\n{safe}\n</div>'
        html = html.replace(MERMAID_PLACEHOLDER.format(i=i), div)
        # markdown may wrap placeholder in <p> tags
        html = html.replace(f"<p>{MERMAID_PLACEHOLDER.format(i=i)}</p>", div)
    return html


def markdown_to_html(md_path: Path) -> str:
    raw = md_path.read_text(encoding="utf-8")
    without_mermaid, mermaid_blocks = _extract_mermaid_blocks(raw)

    body = markdown.markdown(
        without_mermaid,
        extensions=[FencedCodeExtension(), TableExtension(), "nl2br"],
    )
    body = _restore_mermaid_blocks(body, mermaid_blocks)
    return HTML_TEMPLATE.format(body=body)


def html_to_pdf(html: str, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.wait_for_function("window.__mermaidDone === true", timeout=120_000)
        page.wait_for_timeout(500)
        page.pdf(
            path=str(output_path),
            format="A4",
            margin={"top": "18mm", "right": "15mm", "bottom": "18mm", "left": "15mm"},
            print_background=True,
        )
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert flow markdown to PDF")
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    print(f"Converting {args.input} → {args.output}")
    html = markdown_to_html(args.input)
    html_to_pdf(html, args.output)
    print(f"PDF written: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
