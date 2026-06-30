# Interview Prep PDF Generator

Generate interview question PDFs from web research, with **Chroma** vector caching and a **local LLM** (Meta Llama 3.2 via Ollama by default). Built with **LangChain**.

## Features

1. Search the web for interview Q&A by topic / sub-topic (`--num-sites` controls how many sites)
2. Scrape and extract text from pages
3. Deduplicate content from multiple sources
4. Store chunks in **Chroma** for reuse on later runs
5. **Q&A store** (`data/qa/*.json`) — source of truth; PDF is export only
6. Incremental extract from **new sites only** (bounded LLM per run)
7. Question-level dedupe across refreshes (hash + embedding similarity)
8. Write a formatted PDF: **Level → Question → Answer → Source**
8. **Remembers** what was already searched; skips the web unless you pass `--refresh-internet`
9. On `--refresh-internet`, fetches **new websites only** (visited URLs are stored in `search_state.json` and excluded; search query rotates each refresh)

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) with Llama 3.2:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

## Install

This folder is a **uv workspace member** of your home project (parent `~/pyproject.toml` lists `Desktop/sourav`). Dependencies install into **`~/.venv`**, not a separate `sourav/.venv`.

```bash
# From home directory (recommended)
cd ~
uv sync

# Run the app (from sourav folder)
cd Desktop/sourav
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" -n 3
```

### Target ~3 minutes per run

| Run type | Recommended command |
|----------|---------------------|
| First run / refresh | `-n 3` (default) |
| Faster refresh | `-n 2` |
| Cache-only (no web, no LLM) | same topic, omit `--refresh-internet` |

Tune `config.yaml` → `pipeline.max_new_questions_per_run` (default 8) and `embeddings.model: nomic-embed-text`.

**IDE setup:** In Cursor/VS Code, select interpreter: `~/ayushisouravgupta/.venv/bin/python`  
(Project `.vscode/settings.json` points there automatically.)

If imports still fail after `uv sync`, reload the window: Command Palette → **Developer: Reload Window**.

## Configuration

Edit `config.yaml`:

| Section | Purpose |
|---------|---------|
| `paths.pdf_output_dir` | Where PDFs are saved |
| `paths.chroma_persist_dir` | Chroma persistence |
| `paths.state_file` | Topics already searched |
| `llm.*` | Chat model (provider, model, base_url) |
| `embeddings.*` | Embedding model for Chroma |
| `dedup.similarity_threshold` | Text dedup sensitivity |

Environment overrides use prefix `INTERVIEW_` (see `.env.example`).

## Usage

```bash
# First run: fetches web, stores in Chroma, generates PDF
python main.py --topic "Python" --subtopic "Decorators" --num-sites 5

# Second run: uses Chroma + existing PDF (no web)
python main.py --topic "Python" --subtopic "Decorators"

# Force new web content and merge into PDF (skips previously visited URLs)
python main.py --topic "Python" --subtopic "Decorators" --refresh-internet --num-sites 3

# List cached topics
python main.py --list-searched
```

Output PDF example path: `data/pdfs/python_decorators.pdf`

## End-to-end flow (diagrams & use cases)

See **[docs/END_TO_END_FLOW.md](docs/END_TO_END_FLOW.md)** for Mermaid diagrams, all use cases, and a full **Data Engineering** walkthrough.

**PDF version:** [docs/END_TO_END_FLOW.pdf](docs/END_TO_END_FLOW.pdf)

Regenerate the PDF after editing the markdown:

```bash
uv run python scripts/generate_flow_pdf.py
```

## Architecture

```
User CLI
   │
   ▼
Pipeline ──► SearchState (JSON)     "already searched?"
   │
   ├─► [if needed] DuckDuckGo → Scraper → Dedup → Chroma
   │
   ├─► Load existing PDF text
   │
   ├─► Chroma similarity search
   │
   └─► LLM merge (unique Q&A JSON) → ReportLab PDF
```

## PDF format

Each question block contains:

- **Question level** (Easy / Medium / Hard)
- **Question**
- **Answer**
- **Source** (URL or "Cached PDF")

## Switching models

In `config.yaml`:

```yaml
llm:
  provider: ollama
  model: llama3.2
  base_url: http://localhost:11434

embeddings:
  provider: ollama
  model: llama3.2
```

For OpenAI (optional), set `provider: openai` and `OPENAI_API_KEY`.

## Data directories

```
data/
  pdfs/           # Generated PDFs
  chroma/         # Vector DB
  search_state.json
```

Add `data/` to `.gitignore` if you commit this repo.
