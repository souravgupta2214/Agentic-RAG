#!/usr/bin/env python3
"""CLI for interview question PDF generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from interview_prep.config import Settings
from interview_prep.pipeline import InterviewPrepPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate interview question PDFs from web research and local cache. "
            "Uses LangChain, Chroma, and a configurable local LLM (default: Llama 3.2 via Ollama)."
        ),
    )
    parser.add_argument(
        "--topic",
        "-t",
        required=True,
        help="Main topic (e.g. Python, System Design)",
    )
    parser.add_argument(
        "--subtopic",
        "-s",
        default=None,
        help="Optional sub-topic (e.g. Decorators, Load Balancing)",
    )
    parser.add_argument(
        "--num-sites",
        "-n",
        type=int,
        default=3,
        help="Number of websites to browse on web fetch (default: 3, ~3 min target)",
    )
    parser.add_argument(
        "--refresh-internet",
        action="store_true",
        help="Force new web search and append to existing PDF/vector cache",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--list-searched",
        action="store_true",
        help="List topics already searched (from state file)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    settings = Settings.load(args.config)
    settings.ensure_dirs()

    if args.list_searched:
        from interview_prep.state import SearchState

        state = SearchState(settings.state_file)
        if not state._records:
            print("No topics searched yet.")
            return 0
        for key, rec in state._records.items():
            print(
                f"  {key} | PDF: {rec.pdf_path} | "
                f"web searches: {rec.search_count} | last: {rec.last_web_search}"
            )
        return 0

    pipeline = InterviewPrepPipeline(settings)
    result = pipeline.run(
        topic=args.topic,
        subtopic=args.subtopic,
        num_sites=args.num_sites,
        refresh_internet=args.refresh_internet,
    )

    print()
    print(f"Status: {result.message}")
    print(f"Questions: {result.question_count}")
    print(f"PDF: {result.pdf_path}")
    print(f"Used web this run: {result.used_web}")
    print(f"Used cache: {result.used_cache}")
    print(f"New questions this run: {result.added_this_run}")

    return 0 if result.question_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
