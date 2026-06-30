# End-to-End Flow — Interview Prep Application

Example topic used throughout: **Data Engineering / PySpark**.

This document reflects the **current implementation**, where:

- the **Q&A JSON store** is the source of truth
- the **PDF is export only**
- refresh runs process **new sites only**
- question dedupe happens **across all refreshes**

---

## 1. System overview

```mermaid
flowchart TB
    subgraph user_grp [User CLI]
        CMD[uv run python main.py]
    end

    subgraph app_grp [Application]
        MAIN[main.py]
        PIPE[InterviewPrepPipeline]
        CFG[config.yaml]
    end

    subgraph ext_grp [External services]
        DDGS[DDGS Search]
        WEB[Interview websites]
        OLLAMA[Ollama]
    end

    subgraph store_grp [Local persistence]
        STATE[search_state.json]
        CHROMA[Chroma]
        QASTORE[data/qa json]
        PDFOUT[data/pdfs]
    end

    CMD --> MAIN
    MAIN --> PIPE
    MAIN --> CFG
    PIPE --> STATE
    PIPE --> DDGS
    DDGS --> WEB
    WEB --> CHROMA
    PIPE --> CHROMA
    PIPE --> QASTORE
    PIPE --> PDFOUT
    PIPE --> OLLAMA
```

---

## 2. High-level design change

### Old approach

```text
web + old PDF + old cache -> one large LLM merge -> PDF
```

Problems:

- prompt grows after each refresh
- duplicate questions slip through
- long runs become slow and unstable

### New approach

```text
new web batch only -> bounded LLM extract -> dedupe vs Q&A store -> save JSON -> export PDF
```

Benefits:

- bounded LLM work per refresh
- no need to re-read old PDF
- cache-only runs skip LLM entirely

---

## 3. Decision flow (every run)

```mermaid
flowchart TD
    START([Run CLI]) --> LIST{list searched flag}
    LIST -->|Yes| SHOW[Print search history]
    SHOW --> END1([Exit])

    LIST -->|No| PREV{Topic already searched}
    PREV -->|No| FIRST[First run]
    PREV -->|Yes| REF{refresh internet flag}
    REF -->|No| CACHE[Cache only export]
    REF -->|Yes| NEWWEB[Search new websites only]

    FIRST --> EXTRACT
    NEWWEB --> EXTRACT
    CACHE --> EXPORT
    EXTRACT --> DEDUPE
    DEDUPE --> EXPORT[Export PDF from Q&A store]
```

| Condition | Web? | LLM? | Main source |
|-----------|------|------|-------------|
| First run | Yes | Yes | New scraped batch |
| Refresh | Yes | Yes | New scraped batch only |
| Cache-only | No | No | Existing `data/qa/*.json` |

---

## 4. Detailed runtime flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CLI as main.py
    participant P as Pipeline
    participant S as SearchState
    participant D as DDGS
    participant SC as Scraper
    participant V as Chroma
    participant L as Llama 3.2
    participant Q as QAStore
    participant PDF as PDF Writer

    U->>CLI: topic Data Engineering, subtopic pyspark
    CLI->>P: run
    P->>S: check topic_key

    alt First run or refresh
        P->>D: search new URLs
        D-->>P: N results
        P->>SC: scrape in parallel
        SC-->>P: Documents
        P->>V: store chunks
        P->>S: save visited URLs
        P->>L: extract bounded Q and A from this batch
        L-->>P: candidate questions
        P->>Q: add, dedupe, merge sources
    else Cache-only run
        P->>Q: load stored questions
    end

    P->>PDF: export all stored questions
    PDF-->>U: PDF path
```

---

## 5. Key data stores

```mermaid
flowchart LR
    WEB[Scraped web text] --> CHROMA[Chroma chunks]
    CHROMA --> LLM[Bounded extract]
    LLM --> QASTORE[Q and A JSON store]
    QASTORE --> PDF[Generated PDF]
```

### Responsibilities

| Store | Purpose |
|------|---------|
| `search_state.json` | search history, visited URLs, refresh count |
| `data/chroma/` | source text chunks for retrieval and migration |
| `data/qa/*.json` | canonical question bank |
| `data/pdfs/*.pdf` | export artifact only |

---

## 6. Use cases — Data Engineering / PySpark

### Use Case 1 — First run

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" -n 3
```

```mermaid
flowchart LR
    A[3 new URLs] --> B[Parallel scrape]
    B --> C[Text dedupe]
    C --> D[Chroma store]
    D --> E[LLM extract max new items]
    E --> F[Question dedupe]
    F --> G[QAStore JSON]
    G --> H[PDF export]
```

What happens:

1. Search up to 3 sites.
2. Scrape with multiple workers.
3. Store chunks in Chroma.
4. Extract a bounded number of questions from this batch.
5. Save only unique questions into the Q&A store.
6. Export PDF from the full store.

---

### Use Case 2 — Cache-only export

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark"
```

```mermaid
flowchart LR
    A[Topic already exists] --> B[Skip web]
    B --> C[Skip extraction LLM]
    C --> D[Load Q and A store]
    D --> E[Export PDF]
```

What happens:

- no web search
- no scraping
- no extraction LLM
- very fast PDF regeneration

This is the preferred run when content already exists and you only need the PDF again.

---

### Use Case 3 — Refresh with new websites only

```bash
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" --refresh-internet -n 3
```

```mermaid
flowchart TD
    A[visited URLs] --> B[Exclude seen URLs]
    B --> C[Search different wording]
    C --> D[Scrape new websites]
    D --> E[Store new chunks]
    E --> F[Extract only from this batch]
    F --> G[Dedupe vs full Q and A store]
    G --> H[Append only unique questions]
    H --> I[Export updated PDF]
```

What happens:

1. URLs already seen are excluded.
2. New search wording is rotated.
3. Only the new batch is sent to the extraction LLM.
4. New questions are deduped against all historical questions.
5. PDF is regenerated from the updated Q&A store.

---

### Use Case 4 — No new URLs found

```mermaid
flowchart TD
    A[refresh internet] --> B[search with exclude list]
    B --> C{new URLs found}
    C -->|No| D[keep existing Q and A store]
    D --> E[export PDF only]
    C -->|Yes| F[normal refresh flow]
```

---

### Use Case 5 — Embedding model changed

Example: previous Chroma built with `llama3.2`, current config uses `nomic-embed-text`.

```mermaid
flowchart LR
    A[Chroma dimension mismatch] --> B[Fallback read or reset collection]
    B --> C[Migrate or rebuild chunks]
    C --> D[Continue with current embedding model]
```

What happens in the app:

- migration path can read stored chunks directly
- new inserts can reset that topic's Chroma collection when dimensions differ
- the Q&A store remains the stable source of truth

---

## 7. How duplicate questions are prevented

```mermaid
flowchart LR
    A[New candidate question] --> B[Normalize text]
    B --> C[Hash compare]
    C -->|match| DUP[Duplicate]
    C -->|no match| D[Embedding similarity]
    D -->|high similarity| DUP
    D -->|new| ADD[Add to Q and A store]
```

When a duplicate is found:

- sources are merged
- the better / longer answer can replace the old one
- only one canonical question stays in the store

This works across the first refresh and the nth refresh, even when websites are different.

---

## 8. Performance constraints and tuning

### Recommended operating point

| Run type | Recommended setting |
|---------|---------------------|
| First run | `-n 3` |
| Refresh | `--refresh-internet -n 3` |
| Faster refresh | `--refresh-internet -n 2` |
| Cache-only | omit `--refresh-internet` |

### Why this usually stays near 3 minutes

```mermaid
flowchart LR
    A[3 websites] --> B[Parallel scrape]
    B --> C[Fewer chunks from larger chunk size]
    C --> D[Fast embeddings with nomic-embed-text]
    D --> E[LLM capped by max_new_questions_per_run]
    E --> F[Export PDF]
```

Settings that support this:

- `web.scrape_workers: 3`
- `web.request_timeout_seconds: 15`
- `vectorstore.chunk_size: 2000`
- `pipeline.max_context_chars: 6000`
- `pipeline.max_new_questions_per_run: 10`
- `embeddings.model: nomic-embed-text`

---

## 9. Example journey

```mermaid
flowchart LR
    A[First run -n 3] --> B[Refresh -n 3]
    B --> C[Refresh -n 2]
    C --> D[Cache only export]
    D --> E[List searched topics]
```

| Step | Command | Result |
|------|---------|--------|
| 1 | `uv run python main.py -t "Data Engineering" -s "pyspark" -n 3` | first Q&A store + PDF |
| 2 | `uv run python main.py -t "Data Engineering" -s "pyspark" --refresh-internet -n 3` | adds only unique new questions |
| 3 | `uv run python main.py -t "Data Engineering" -s "pyspark" --refresh-internet -n 2` | smaller bounded refresh |
| 4 | `uv run python main.py -t "Data Engineering" -s "pyspark"` | fast PDF export from store |
| 5 | `uv run python main.py --list-searched` | inspect search history |

---

## 10. Component map

```mermaid
flowchart TB
    subgraph cli_grp [CLI]
        M[main.py]
    end

    subgraph core_grp [Core]
        P[pipeline.py]
        C[config.py]
        ST[state.py]
        QA[qa_store.py]
        QD[question_dedup.py]
    end

    subgraph ingest_grp [Ingest]
        WS[web_search.py]
        SCR[scraper.py]
        DED[dedup.py]
        VS[vectorstore.py]
    end

    subgraph intelligence_grp [LLM]
        LF[llm_factory.py]
        MOD[models.py]
    end

    subgraph output_grp [Output]
        PDF[pdf_io.py]
    end

    M --> P
    P --> C
    P --> ST
    P --> QA
    P --> QD
    P --> WS
    P --> SCR
    P --> DED
    P --> VS
    P --> MOD
    P --> PDF
    MOD --> LF
    VS --> LF
    QD --> LF
```

---

## 11. Files on disk

```text
data/
├── chroma/
│   └── chroma.sqlite3
├── pdfs/
│   └── data-engineering_pyspark.pdf
├── qa/
│   └── data-engineering_pyspark.json
└── search_state.json
```

---

## 12. Prerequisites checklist

```mermaid
flowchart LR
    A[uv sync] --> B[ollama pull llama3.2]
    B --> C[ollama pull nomic-embed-text]
    C --> D[ollama serve]
    D --> E[uv run python main.py ...]
```

```bash
cd ~
uv sync
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
cd Desktop/sourav
uv run python main.py --topic "Data Engineering" --subtopic "pyspark" -n 3
```

---

## 13. Quick reference

| Intent | Command shape |
|--------|---------------|
| First run | `-t TOPIC -s SUBTOPIC -n 3` |
| Refresh from new sites | `-t TOPIC -s SUBTOPIC --refresh-internet -n 3` |
| Faster refresh | `--refresh-internet -n 2` |
| Cache-only export | same topic, no refresh flag |
| List topic history | `--list-searched` |
