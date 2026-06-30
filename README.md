# Interview Prep PDF Generator

Generate interview question PDFs from web research using **LangChain**, **Ollama**, and **Chroma**.

The current implementation is optimized for repeatable runs:

- **PDF is output only**
- **Q&A JSON store is the source of truth**
- **Refresh runs process only new websites**
- **Question-level dedupe prevents repeats across refreshes**

## Features

1. Search the web by topic and sub-topic.
2. Scrape pages in parallel and extract usable text.
3. Remove duplicate source text before storage.
4. Store source chunks in **Chroma** for retrieval and migration support.
5. Persist canonical questions in `data/qa/*.json`.
6. Extract only a **bounded number of new Q&A items per run**.
7. Deduplicate questions across refreshes with normalized hash + embedding similarity.
8. Track visited URLs so `--refresh-internet` prefers new websites.
9. Export a formatted PDF with `Level`, `Question`, `Answer`, and `Source`.
10. Support fast cache-only runs that regenerate PDF from the stored Q&A set.

## Why the implementation changed

The earlier design re-read the generated PDF and merged everything again on every refresh. That became slow and unstable as the PDF grew.

The new design avoids that:

- `data/qa/*.json` stores the long-term question bank.
- `data/pdfs/*.pdf` is regenerated from that store.
- `--refresh-internet` only processes **new scraped text** from new URLs.
- The LLM call is capped by `pipeline.max_new_questions_per_run`.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/)

Pull the required models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

`llama3.2` is used for Q&A extraction. `nomic-embed-text` is used for faster embeddings.

## Install

This folder is a `uv` workspace member of your home project, so dependencies install into `~/.venv`.

```bash
cd ~
uv sync

cd Desktop/sourav
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" -n 3
```

## Interpreter setup

In Cursor / VS Code, use:

`/Users/ayushisouravgupta/.venv/bin/python`

If import squiggles remain after `uv sync`, reload the window.

## Recommended runtime targets

### Best settings for about 3 minutes

| Run type | Recommendation |
|---------|----------------|
| First run | `-n 3` |
| Refresh with new sites | `--refresh-internet -n 3` |
| Faster refresh | `--refresh-internet -n 2` |
| Cache-only PDF export | omit `--refresh-internet` |

### What to expect

| Scenario | Typical behavior |
|---------|------------------|
| First run / refresh | Web + scrape + embed + bounded LLM extract |
| Cache-only run | No web, no extraction LLM, PDF export from Q&A store |
| Embedding model changed | Chroma collection may be reset automatically for that topic |

## Configuration

Main settings live in `config.yaml`.

| Section | Purpose |
|---------|---------|
| `paths.pdf_output_dir` | Generated PDFs |
| `paths.qa_store_dir` | Canonical Q&A JSON files |
| `paths.state_file` | Search history and visited URLs |
| `paths.chroma_persist_dir` | Chroma persistence |
| `llm.*` | Chat model for extraction |
| `embeddings.*` | Embedding model for Chroma and question dedupe |
| `web.request_timeout_seconds` | Per-request timeout |
| `web.scrape_workers` | Parallel scraper worker count |
| `dedup.similarity_threshold` | Source-text dedupe |
| `dedup.question_similarity_threshold` | Cross-refresh question dedupe |
| `vectorstore.chunk_size` | Chroma chunk size |
| `pipeline.chroma_search_k` | Number of chunks used for migration / lookup |
| `pipeline.max_context_chars` | Max chars sent to extraction LLM |
| `pipeline.max_new_questions_per_run` | Upper bound of new Q&A items per run |
| `pipeline.max_questions_per_topic` | Cap on stored questions per topic |

Environment overrides use the `INTERVIEW_` prefix.

## Usage

### First run

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" -n 3
```

### Refresh from new sites only

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" --refresh-internet -n 3
```

### Cache-only PDF export

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark"
```

### List searched topics

```bash
uv run python main.py --list-searched
```

## Current architecture

```text
User CLI
  -> Pipeline
     -> SearchState (visited URLs, search count)
     -> [optional] DDGS search
     -> [optional] parallel scraper
     -> [optional] text dedupe
     -> [optional] Chroma storage
     -> [optional] bounded LLM extract from new batch only
     -> QAStore JSON (canonical question bank)
     -> PDF export
```

## Data flow

### First run / refresh

1. Search new websites.
2. Scrape and dedupe page text.
3. Store chunks in Chroma.
4. Send only this batch to the LLM.
5. Deduplicate new questions against the existing Q&A store.
6. Save the updated Q&A store.
7. Regenerate the PDF.

### Cache-only run

1. Skip web.
2. Skip extraction LLM.
3. Load Q&A JSON store.
4. Export PDF directly.

## Question dedupe strategy

Questions do not rely only on URL memory.

They are deduplicated using:

1. normalized question text
2. stable question hash
3. embedding similarity against the stored question bank

When the same question appears on another site, the app keeps one canonical question and appends the new source URL.

## PDF format

Each PDF block contains:

- `Question level`
- `Question`
- `Answer`
- `Source`

Sources may contain multiple URLs joined together when duplicate questions are merged from multiple websites.

## Data directories

```text
data/
  chroma/            # Source chunks and vector index
  pdfs/              # Generated PDFs
  qa/                # Canonical question bank JSON
  search_state.json  # Topics, visited URLs, search count
```

## End-to-end flow docs

Detailed diagrams and use cases:

- [docs/END_TO_END_FLOW.md](docs/END_TO_END_FLOW.md)
- [docs/END_TO_END_FLOW.pdf](docs/END_TO_END_FLOW.pdf)

Regenerate the PDF version after editing the markdown:

```bash
uv run python scripts/generate_flow_pdf.py
```
