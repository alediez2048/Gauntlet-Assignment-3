# LegacyLens — System Design

## Data Flow

### Ingestion Pipeline (Offline, Per Codebase)

```
[COBOL Sources] ──┐
[Fortran Sources] ─┤
                   ▼
        ┌─────────────────────┐
        │  Language Detection  │
        │  (.cob → COBOL,     │
        │   .f → Fortran)     │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Preprocessing      │
        │  COBOL: col strip,  │
        │    encoding, comments│
        │  Fortran: free/fixed│
        │    form, comments   │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Chunking           │
        │  COBOL: paragraph   │
        │  Fortran: subroutine│
        │  Adaptive 64-768 tok│
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Metadata Extraction│
        │  file, lines, name, │
        │  division, language, │
        │  codebase, deps     │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Batch Embedding    │
        │  Voyage Code 2      │
        │  128 texts/call     │
        │  1536 dimensions    │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Qdrant Storage     │
        │  Hybrid index       │
        │  Payload metadata   │
        └─────────────────────┘
```

### Retrieval Pipeline (Online, Per Query)

```
[User Query via CLI or Web]
        │
        ▼
   ┌──────────┐    ┌──────────────┐    ┌─────────────┐
   │  Embed   │───▶│ Hybrid Search│───▶│  Re-rank    │
   │  Query   │    │ Dense+BM25   │    │ Meta+Cohere │
   └──────────┘    └──────────────┘    └──────┬──────┘
                                              ▼
                                    ┌─────────────────┐
                                    │ Context Assembly │
                                    │ Dynamic budget + │
                                    │ hierarchical exp │
                                    └────────┬────────┘
                                             ▼
                                    ┌─────────────────┐
                                    │ Feature Router   │
                                    │ 8 feature prompts│
                                    │ + GPT-4o stream  │
                                    └────────┬────────┘
                                             ▼
                                    ┌─────────────────┐
                                    │ Cited Answer +   │
                                    │ Confidence Score │
                                    │ → CLI or Web UI  │
                                    └─────────────────┘
```

## Component Ownership Map

| Component | Owner Module | External Dependency | Failure Mode |
|---|---|---|---|
| Language Detection | `src/ingestion/detector.py` | None (file extension) | Unknown extension → skip with warning |
| COBOL Preprocessor | `src/ingestion/cobol_parser.py` | chardet | Encoding corruption → log + skip |
| Fortran Preprocessor | `src/ingestion/fortran_parser.py` | chardet | Fixed/free form misdetection → fallback |
| COBOL Chunker | `src/ingestion/cobol_chunker.py` | tiktoken | Wrong paragraph boundaries → validation tests |
| Fortran Chunker | `src/ingestion/fortran_chunker.py` | tiktoken | Wrong subroutine boundaries → validation tests |
| Batch Embedder | `src/ingestion/embedder.py` | Voyage API | Timeout → retry with backoff, cache |
| Qdrant Indexer | `src/ingestion/indexer.py` | Qdrant Cloud | Connection failure → graceful error |
| Hybrid Search | `src/retrieval/search.py` | Qdrant Cloud | Latency spike → timeout + error |
| Re-ranking | `src/retrieval/reranker.py` | Cohere API | Fallback to metadata-only ranking |
| Context Assembly | `src/retrieval/context.py` | tiktoken | Token overflow → truncation logic |
| Feature Router | `src/features/router.py` | None | Unknown feature → default to Code Explanation |
| LLM Generation | `src/generation/llm.py` | OpenAI API | Timeout → fallback to GPT-4o-mini |
| FastAPI Backend | `src/api/app.py` | FastAPI/Uvicorn | Crash → auto-restart via Render |
| CLI Interface | `src/cli/main.py` | Click/Rich | N/A (local HTTP client) |
| Next.js Frontend | `frontend/` | Vercel | Cold start → cron keepalive |

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/query` | Main query (returns full JSON) |
| POST | `/api/query/stream` | SSE streaming query |
| GET | `/api/codebases` | List all 5 codebases with status |
| POST | `/api/ingest` | Trigger ingestion for a codebase |
| GET | `/api/health` | Health check (warms full stack) |
| GET | `/api/metrics` | Precision, latency, query count |
| GET | `/api/features` | List available features |

## Codebase Registry

| Name | Language | Extensions | Preprocessor | Chunker |
|---|---|---|---|---|
| gnucobol | COBOL | .cob, .cbl, .cpy | cobol | cobol_paragraph |
| gfortran | Fortran | .f, .f90, .f77, .f95 | fortran | fortran_subroutine |
| lapack | Fortran | .f, .f90 | fortran | fortran_subroutine |
| blas | Fortran | .f | fortran | fortran_subroutine |
| opencobol-contrib | COBOL | .cob, .cbl, .cpy | cobol | cobol_paragraph |

## 8 Code Understanding Features

| # | Feature | Retrieval | Architecture |
|---|---|---|---|
| 1 | Code Explanation | Standard hybrid search | Config-driven |
| 2 | Dependency Mapping | PERFORM/CALL regex + metadata filter | Config-driven |
| 3 | Pattern Detection | Top-30 search + LLM grouping | Custom module |
| 4 | Impact Analysis | Reverse metadata lookup + LLM | Custom module |
| 5 | Documentation Gen | Hierarchical context expansion | Config-driven |
| 6 | Translation Hints | Language-specific prompt (Python default) | Config-driven |
| 7 | Bug Pattern Search | 14-pattern checklist + LLM severity | Config-driven |
| 8 | Business Logic Extract | PROCEDURE DIVISION focus | Config-driven |

## Failure Modes

| Failure | Detection | Mitigation |
|---|---|---|
| Zero relevant results | Top score < threshold | Four-tier degradation: normal → partial → keyword → suggestions |
| Hallucinated citations | Citation validation | Structured prompt: answer ONLY from context |
| Embedding API timeout | Request timeout > 5s | Retry with backoff (3 attempts) + LRU cache |
| Qdrant connection failure | Connection error | Graceful error + health check + auto-reconnect |
| LLM rate limiting | 429 response | Auto-fallback to GPT-4o-mini + rate limiter |
| Encoding corruption | chardet confidence < 0.7 | Log warning → UTF-8 replace → skip |
| Fortran format misdetection | Parsing errors | Heuristic override + configurable override |
| Cross-codebase noise | Low precision on "all" | Diversity re-ranking + metadata filter |
