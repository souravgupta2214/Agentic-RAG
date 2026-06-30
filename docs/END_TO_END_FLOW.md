# End-to-End Flow — Interview Prep Application

Example topic used throughout: **Data Engineering** (with optional sub-topics).

---

## 1. System overview

```mermaid
flowchart TB
    subgraph user_grp [User CLI]
        CMD[python main.py]
    end

    subgraph app_grp [Application]
        MAIN[main.py]
        PIPE[InterviewPrepPipeline]
        CFG[config.yaml]
    end

    subgraph ext_grp [External services]
        DDG[DuckDuckGo Search]
        WEB[Interview websites]
        OLLAMA[Ollama Llama 3.2]
    end

    subgraph store_grp [Local persistence]
        STATE[search_state.json]
        CHROMA[Chroma vector DB]
        PDFOUT[data/pdfs]
    end

    CMD --> MAIN
    MAIN --> CFG
    MAIN --> PIPE
    PIPE --> STATE
    PIPE --> DDG
    DDG --> WEB
    WEB --> CHROMA
    PIPE --> CHROMA
    PIPE --> PDFOUT
    PIPE --> OLLAMA
    CHROMA --> OLLAMA
```

---

## 2. Decision flow (every run)

When you run the app, it first decides **whether to hit the internet**.

```mermaid
flowchart TD
    START([User runs CLI]) --> LIST{list searched flag?}
    LIST -->|Yes| SHOW[Print topics from state]
    SHOW --> END1([Exit])

    LIST -->|No| KEY[Build topic_key]
    KEY --> PREV{Topic in state file?}
    PREV -->|No| WEB[Fetch web - Use Case 1]
    PREV -->|Yes| REF{refresh internet flag?}
    REF -->|No| CACHE[Use cache only - Use Case 2]
    REF -->|Yes| WEBNEW[Fetch NEW sites - Use Case 3]

    WEB --> MERGE
    WEBNEW --> MERGE
    CACHE --> MERGE[Chroma plus PDF LLM merge]

    MERGE --> OUT([PDF output])
```

| Condition | Web? | Source of content |
|-----------|------|-------------------|
| First time for topic | Yes | DuckDuckGo → scrape → Chroma |
| Topic exists, no `--refresh-internet` | No | Chroma + existing PDF |
| Topic exists + `--refresh-internet` | Yes (new URLs only) | New sites → append Chroma + merge with PDF |

---

## 3. Detailed pipeline (web fetch path)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CLI as main.py
    participant P as Pipeline
    participant S as SearchState
    participant D as DuckDuckGo
    participant SC as Scraper
    participant DD as Dedup
    participant V as Chroma
    participant L as Llama 3.2
    participant PDFW as PDF Writer

    U->>CLI: topic Data Engineering subtopic Spark
    CLI->>P: run pipeline
    P->>S: check has_searched

    alt First run or refresh internet
        P->>D: search exclude visited if refresh
        D-->>P: 5 URLs
        P->>SC: scrape each URL to text
        SC-->>P: Documents
        P->>DD: remove duplicate text
        DD-->>P: unique Documents
        P->>V: embed and store in Chroma
        P->>S: register_search and visited_urls
    end

    P->>PDFW: load existing PDF text if any
    P->>V: similarity_search on topic
    V-->>P: relevant chunks
    P->>L: merge to JSON Q and A
    L-->>P: InterviewQA list
    P->>PDFW: generate_interview_pdf
    PDFW-->>U: output PDF path
```

---

## 4. Use cases — Data Engineering

### Use Case 1 — First-time topic (web + new PDF)

**Goal:** User wants interview questions for Data Engineering for the first time.

```bash
python main.py --topic "Data Engineering" --num-sites 5
```

```mermaid
flowchart LR
    A[Search query] --> B[5 new URLs]
    B --> C[Scrape and dedup]
    C --> D[Chroma collection]
    D --> E[LLM merge]
    E --> F[PDF file]
    G[search_state.json] -.-> D
```

**What happens**

1. DuckDuckGo returns 5 sites (e.g. GeeksforGeeks, InterviewBit, Medium, etc.).
2. Text extracted, near-duplicates removed (~85% similarity threshold).
3. Chunks embedded (Llama 3.2 embeddings) and stored in Chroma.
4. LLM produces structured Q&A: Level | Question | Answer | Source.
5. PDF saved; state records topic + visited URLs.

**Sample PDF block**

| Field | Example |
|-------|---------|
| Level | Medium |
| Question | What is the difference between ETL and ELT? |
| Answer | ETL transforms before load; ELT loads raw data first… |
| Source | https://example.com/data-engineering-interview |

---

### Use Case 2 — Same topic, offline / fast regenerate (cache only)

**Goal:** User already ran once; wants an updated PDF without waiting for web or using Ollama only on merge.

```bash
python main.py --topic "Data Engineering"
```

```mermaid
flowchart LR
    A["Topic in state?"] -->|Yes| B["Skip web"]
    B --> C["Chroma similarity search"]
    B --> D["Load existing PDF text"]
    C --> E["LLM merge"]
    D --> E
    E --> F[Overwrite same PDF path]
```

**What happens**

- No HTTP to interview sites.
- Retrieves best-matching chunks from Chroma for `"Data Engineering interview questions..."`.
- Reads prior PDF from `data/pdfs/data-engineering.pdf` if present.
- LLM deduplicates and reformats → new PDF at same path.

**When to use:** Quick refresh of formatting, tweak LLM output, or re-run after fixing Ollama — without new content.

---

### Use Case 3 — Sub-topic (narrower scope)

**Goal:** Focus on Apache Spark within Data Engineering.

```bash
python main.py --topic "Data Engineering" --subtopic "Apache Spark" --num-sites 5
```

```mermaid
flowchart TB
    T1[topic_key data engineering apache spark]
    T2[Separate Chroma collection]
    T3[Separate PDF file]
    T1 --> T2 --> T3
```

**Note:** Sub-topic is a **different cache key** from the parent topic. Parent and sub-topic each have their own Chroma collection, state entry, and PDF.

---

### Use Case 4 — Refresh internet (new websites + append)

**Goal:** User finished first PDF; wants **more questions from new sources**, merged into one PDF.

```bash
python main.py --topic "Data Engineering" --subtopic "Apache Spark" \
  --refresh-internet --num-sites 5
```

```mermaid
flowchart TD
    V[visited_urls from state] --> X[Exclude those URLs]
    X --> Q[Rotated search query]
    Q --> N[Pick 5 NEW URLs]
    N --> S[Scrape dedup append Chroma]
    S --> M[LLM merge new and old content]
    M --> P[Updated PDF]
```

**What happens**

1. Skips all URLs in `visited_urls` for that topic.
2. Uses alternate search phrasing (rotates each `search_count`).
3. Appends new chunks to existing Chroma collection (does not wipe old data).
4. LLM merges old PDF + new web content without duplicate questions.
5. Adds new URLs to `visited_urls`.

---

### Use Case 5 — Refresh but no new sites left

**Goal:** User runs `--refresh-internet` again but search has no unseen URLs.

```mermaid
flowchart TD
    A[refresh internet flag] --> B[Search with exclude list]
    B --> C{New URLs found?}
    C -->|No| D["Warning: no new websites"]
    D --> E[Regenerate PDF from cache only]
    C -->|Yes| F["Normal Use Case 4 flow"]
```

---

### Use Case 6 — List all prepared topics

```bash
python main.py --list-searched
```

**Example output**

```
data engineering | PDF: data/pdfs/data-engineering.pdf | web searches: 1 | last: 2026-05-23T...
data engineering::apache spark | PDF: .../data-engineering_apache-spark.pdf | web searches: 2 | ...
```

---

### Use Case 7 — Custom config / paths

**Goal:** Store PDFs on an external drive; use a different Ollama model.

Edit `config.yaml` or env vars, then run as usual:

```bash
python main.py --topic "Data Engineering" --config /path/to/config.yaml
```

```mermaid
flowchart LR
    CFG[config.yaml] --> PATHS[pdf and chroma paths]
    CFG --> LLM[llm.model llama3.2]
    CFG --> EMB[embeddings.model]
```

---

## 5. Data Engineering — example journey (all use cases)

```mermaid
flowchart LR
    UC1[UC1 First run main topic] --> UC3[UC3 Sub-topic Spark]
    UC3 --> UC2[UC2 Regenerate from cache]
    UC2 --> UC4a[UC4 Refresh internet]
    UC4a --> UC4b[UC4 Refresh again]
    UC4b --> UC6[UC6 List searched topics]
```

| Step | Command | Result |
|------|---------|--------|
| 1 | `python main.py -t "Data Engineering" -n 5` | First PDF + Chroma + 5 URLs in state |
| 2 | `python main.py -t "Data Engineering" -s "Apache Spark" -n 5` | Separate Spark PDF + cache |
| 3 | `python main.py -t "Data Engineering"` | PDF regenerated from cache (no web) |
| 4 | `python main.py -t "Data Engineering" --refresh-internet -n 5` | 5 **new** sites, merged PDF |
| 5 | `python main.py --list-searched` | See both topics and search counts |

---

## 6. Component map

```mermaid
flowchart TB
    subgraph cli_grp [CLI]
        M[main.py]
    end

    subgraph core_grp [Core]
        P[pipeline.py]
        C[config.py]
        ST[state.py]
    end

    subgraph ingest_grp [Ingest]
        WS[web_search.py]
        SCR[scraper.py]
        DED[dedup.py]
    end

    subgraph intel_grp [Intelligence]
        LF[llm_factory.py]
        MOD[models.py]
    end

    subgraph out_grp [Output]
        VS[vectorstore.py]
        PDFF[pdf_io.py]
    end

    M --> P
    P --> C
    P --> ST
    P --> WS
    P --> SCR
    P --> DED
    P --> VS
    P --> MOD
    P --> PDFF
    MOD --> LF
    VS --> LF
```

---

## 7. PDF output structure

Every generated PDF follows this repeating block:

```
┌─────────────────────────────────────────┐
│ Interview Questions: Data Engineering   │
│              — Apache Spark             │
├─────────────────────────────────────────┤
│ Question 1 — Level: Easy                │
│ Question                                │
│   What is RDD?                          │
│ Answer                                  │
│   Resilient Distributed Dataset is...   │
│ Source                                  │
│   https://...                           │
├─────────────────────────────────────────┤
│ Question 2 — Level: Hard                │
│ ...                                     │
└─────────────────────────────────────────┘
```

---

## 8. Files on disk (after Use Case 1 + 3)

```
data/
├── search_state.json          # topics, visited_urls, search_count
├── chroma/                    # persisted embeddings
│   └── (collections per topic_key)
└── pdfs/
    ├── data-engineering.pdf
    └── data-engineering_apache-spark.pdf
```

---

## 9. Prerequisites checklist

```mermaid
flowchart LR
    O[Ollama running] --> M[llama3.2 pulled]
    M --> RUN[python main.py ...]
    PY[Python 3.11+ + deps] --> RUN
```

```bash
ollama pull llama3.2
ollama serve
uv sync
python main.py --topic "Data Engineering" --num-sites 5
```

---

## 10. Quick reference

| Intent | Flags |
|--------|-------|
| New topic, fetch web | `--topic "Data Engineering" -n 5` |
| Sub-topic | add `--subtopic "Apache Spark"` |
| No web, use cache | same topic, **no** `--refresh-internet` |
| New websites only | `--refresh-internet -n 5` |
| See history | `--list-searched` |
