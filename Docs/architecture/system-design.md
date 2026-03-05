# LegacyLens — System Design

## 1. System Overview

LegacyLens is a custom RAG (Retrieval-Augmented Generation) pipeline that makes legacy COBOL and Fortran codebases queryable through natural language. Users ask questions like "How does DGETRF perform LU factorization?" or "What does the CALCULATE-INTEREST paragraph do?" and receive answers grounded in retrieved code chunks, with file:line citations and confidence scores.

**Key design decisions:**

- **Custom pipeline** — No LangChain or LlamaIndex. Every stage (preprocessing, chunking, embedding, search, reranking, generation) is purpose-built for legacy code. This keeps the stack lean, predictable, and fully controllable.
- **Language-aware processing** — COBOL and Fortran have different syntax and structure. COBOL uses fixed-format columns and paragraph boundaries; Fortran uses fixed/free form and SUBROUTINE/FUNCTION boundaries. Each language has its own preprocessor and chunker.
- **Adaptive chunking** — Chunks are sized 64–768 tokens on structural boundaries (paragraphs, subroutines), not arbitrary sliding windows. This preserves logical units and improves retrieval relevance.
- **Hybrid search** — Dense vectors (Voyage Code 2) plus BM25 keyword matching, fused with query-adaptive weighting. Identifier-heavy queries (e.g., "DGETRF") boost BM25; semantic queries boost dense.
- **Layered re-ranking** — Metadata scoring (paragraph name, division, codebase) runs first (free). Cohere cross-encoder runs second when configured, blended 40/60 with metadata scores. Graceful fallback to metadata-only when Cohere is unavailable.

---

## 2. Ingestion Pipeline

Raw source files are discovered, preprocessed, chunked, embedded, and indexed into Qdrant. The pipeline runs offline per codebase via runner scripts (e.g., `scripts/run_ingest_lapack.py`).

### Data Flow

```
[COBOL Sources] ──┐
[Fortran Sources] ─┤
                   ▼
        ┌─────────────────────┐
        │  Language Detection  │  (.cob → COBOL, .f → Fortran)
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Preprocessing      │  COBOL: col strip, encoding, comments
        │                     │  Fortran: fixed/free form, comments
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Chunking           │  COBOL: paragraph boundaries
        │                     │  Fortran: SUBROUTINE/FUNCTION
        │                     │  Adaptive 64-768 tokens
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Metadata Extraction │  file_path, line_start, line_end,
        │                     │  paragraph_name, division, codebase
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Batch Embedding    │  Voyage Code 2, 128 texts/call
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Qdrant Storage     │  Hybrid index, payload metadata
        └─────────────────────┘
```

### Module Reference

| Module | File | Purpose |
|--------|------|---------|
| Language detector | `src/ingestion/detector.py` | Route files by extension (.cob/.cbl/.cpy → COBOL; .f/.f90/.f77/.f95 → Fortran) |
| COBOL preprocessor | `src/ingestion/cobol_parser.py` | Fixed-format column stripping (cols 1–6, 73–80), comment extraction, continuation handling |
| Fortran preprocessor | `src/ingestion/fortran_parser.py` | Fixed/free form detection, encoding (chardet + UTF-7 guard), comment and continuation handling |
| COBOL chunker | `src/ingestion/cobol_chunker.py` | Paragraph-boundary chunking, adaptive 64–768 tokens, dependency extraction |
| Fortran chunker | `src/ingestion/fortran_chunker.py` | SUBROUTINE/FUNCTION/MODULE boundary chunking, adaptive sizing |
| Embedder | `src/ingestion/embedder.py` | Voyage Code 2, batch 128, timeout retry |
| Indexer | `src/ingestion/indexer.py` | Qdrant upsert with payload indexes on paragraph_name, division, file_path, language, codebase |
| Orchestrator | `src/ingestion/ingest.py` | Reusable `ingest_codebase()` with rate-limit-aware embedding |

### Design Details

- **Chunk size:** Adaptive 64–768 tokens on structural boundaries. Small adjacent chunks are merged; oversized chunks are split on line boundaries.
- **COBOL fixed-format:** Cols 1–6 (sequence numbers) and 73–80 stripped; col 7 indicates comment/continuation; cols 7–72 preserved.
- **Fortran format:** Extension-based default (`.f`/`.f77` = fixed, `.f90`/`.f95` = free) with 20-line heuristic override on conflict.
- **Encoding:** chardet with 0.7 confidence threshold; explicit None-encoding guard for chardet 7.0 compatibility.
- **Empty chunks:** Filtered before embedding (Voyage rejects empty strings).

---

## 3. Retrieval Pipeline

Each query flows through: embed → hybrid search → rerank → context assembly → generation.

### Data Flow

```
User Query (CLI or Web)
        │
        ▼
   ┌──────────┐    ┌──────────────┐    ┌─────────────┐
   │  Embed   │───▶│ Hybrid Search│───▶│  Re-rank    │
   │  Query   │    │ Dense+BM25   │    │ Meta+Cohere │
   └──────────┘    └──────────────┘    └──────┬──────┘
        │                   │                   │
        │                   │                   ▼
        │                   │          ┌─────────────────┐
        │                   │          │ Context Format  │
        │                   │          │ (prompts.py)    │
        │                   │          └────────┬────────┘
        │                   │                   │
        │                   │                   ▼
        │                   │          ┌─────────────────┐
        │                   │          │ GPT-4o Generate  │
        │                   │          │ Feature prompt + │
        │                   │          │ chunk context    │
        │                   │          └────────┬────────┘
        │                   │                   │
        ▼                   ▼                   ▼
   Voyage Code 2       Qdrant Cloud        QueryResponse
   (query embed)       (codebase filter)   (answer, chunks, confidence)
```

### Module Reference

| Module | File | Purpose |
|--------|------|---------|
| Hybrid search | `src/retrieval/search.py` | Dense + BM25 via Qdrant native, query-adaptive weighting, codebase filter |
| Re-ranker | `src/retrieval/reranker.py` | Metadata scoring (paragraph name, division, codebase) + Cohere cross-encoder (40/60 blend) |
| Context formatting | `src/generation/prompts.py` | Format chunks for LLM, dynamic token budget (5,000 total) |

### Design Details

- **Hybrid search:** Dense vectors and BM25 sparse vectors fused with weighted normalization. Identifier-heavy queries (e.g., "DGETRF") use 0.6 BM25 / 0.4 dense; semantic queries use 0.7 dense / 0.3 BM25.
- **Re-ranking:** Metadata-first (always runs, free) → Cohere cross-encoder (optional, when API key set). Scores blended 40% metadata, 60% Cohere. Confidence: HIGH/MEDIUM/LOW from normalized scores.
- **Codebase filter:** Optional `codebase` param flows through search and payload filter; isolates results to one codebase when set.

---

## 4. Generation Pipeline

| Module | File | Purpose |
|--------|------|---------|
| Prompt builder | `src/generation/prompts.py` | Feature-specific system prompts, chunk formatting, citation rules |
| LLM client | `src/generation/llm.py` | GPT-4o with GPT-4o-mini fallback, streaming support |

### Design Details

- **Feature differentiation:** All 8 features use the same retrieval path; differentiation is via prompt templates (not separate retrieval strategies).
- **Citation enforcement:** System prompt requires `file:start-end` format; model instructed to answer ONLY from provided context.
- **Fallback:** GPT-4o → GPT-4o-mini on failure or timeout.

---

## 5. API Layer

| Module | File | Purpose |
|--------|------|---------|
| App | `src/api/app.py` | FastAPI app, CORS, health and codebases endpoints |
| Routes | `src/api/routes.py` | `/api/query`, `/api/stream`, `/api/health`, `/api/codebases` |
| Schemas | `src/api/schemas.py` | Pydantic request/response contracts |

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/query` | Full RAG pipeline, returns JSON (answer, chunks, confidence) |
| POST | `/api/stream` | Same pipeline, streams answer tokens as text/plain |
| GET | `/api/health` | Health check |
| GET | `/api/codebases` | List indexed codebases with name, language, description |

---

## 6. Codebase Registry

| Name | Language | Chunks (approx) | Source |
|------|----------|------------------|--------|
| gnucobol | COBOL | 3 | GnuCOBOL compiler |
| opencobol-contrib | COBOL | 3,893 | OpenCOBOL contrib samples |
| lapack | Fortran | 12,515 | Reference-LAPACK |
| blas | Fortran | 814 | Netlib BLAS |
| gfortran | Fortran | varies | GCC Fortran test suite |

---

## 7. Eight Code Understanding Features

All implemented via prompt differentiation in `src/generation/prompts.py`:

| Feature | Description |
|---------|-------------|
| code_explanation | Plain English explanation of code |
| dependency_mapping | Map CALL/PERFORM/USE chains |
| pattern_detection | Identify common code patterns |
| impact_analysis | Analyze change impact |
| documentation_gen | Generate documentation |
| translation_hints | Map to modern language equivalents |
| bug_pattern_search | Find potential issues |
| business_logic | Extract business rules |

---

## 8. Evaluation

- **Ground truth:** 27 queries across 5 codebases and 6 features
- **Metric:** precision@5 (at least one expected file/name in top-5 chunks)
- **Result:** **81.5%** overall (22/27)
- **Per-codebase:** gnucobol 100%, opencobol-contrib 100%, blas 88%, lapack 86%, gfortran 0% (ingestion pending at eval time)

---

## 9. Deployment

| Component | Platform | URL |
|-----------|----------|-----|
| API | Render (Docker) | `https://gauntlet-assignment-3.onrender.com` |
| Frontend | Vercel (Next.js 14) | Vercel deployment URL |
| Vector DB | Qdrant Cloud | Configured via `QDRANT_URL`, `QDRANT_API_KEY` |

---

## 10. Failure Modes

| Failure | Mitigation |
|---------|------------|
| Zero relevant results | Structured prompt instructs model to say so; no hallucination |
| Embedding API timeout | Retry with backoff in embedder |
| Qdrant unreachable | Graceful error, health check |
| Cohere unavailable | Fallback to metadata-only reranking |
| LLM failure | Fallback to GPT-4o-mini |
| Encoding corruption | chardet confidence < 0.7 → skip or UTF-8 replace |
