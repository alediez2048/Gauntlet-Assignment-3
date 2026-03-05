# G4-020 Primer: Architecture Document

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 4, 2026
**Previous work:** All phases complete through G4-008. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-020 creates the system architecture document at `Docs/architecture/system-design.md`. This is a **documentation-only ticket** — no code changes.

The document should explain how LegacyLens works at every layer, with enough detail for a technical reviewer or new developer to understand the system end-to-end.

---

## Architecture Overview

LegacyLens is a custom RAG pipeline (no LangChain/LlamaIndex) that makes legacy COBOL and Fortran codebases queryable through natural language. Every stage from parsing to generation is purpose-built.

### System Stack

| Layer | Technology |
|-------|-----------|
| Embeddings | Voyage Code 2 (1536 dimensions, batch 128) |
| Vector DB | Qdrant Cloud |
| Search | Hybrid dense + BM25 (Qdrant native) |
| Re-ranking | Metadata-first (free) + Cohere cross-encoder |
| Generation | GPT-4o (fallback: GPT-4o-mini) |
| API | FastAPI on Render |
| Frontend | Next.js 14 on Vercel |
| CLI | Click + Rich |

### Indexed Codebases

| Codebase | Language | Points in Qdrant | Source |
|----------|----------|-----------------|--------|
| gnucobol | COBOL | 3 | GnuCOBOL compiler |
| gfortran | Fortran | ~13,800 (pending) | GCC test suite |
| lapack | Fortran | 12,515 | Reference-LAPACK |
| blas | Fortran | 814 | Netlib BLAS 3.12.0 |
| opencobol-contrib | COBOL | 3,893 | OpenCOBOL contrib samples |

### 8 Features

All implemented via prompt differentiation in `src/generation/prompts.py`:

1. `code_explanation` — Explain what code does
2. `dependency_mapping` — Map CALL/PERFORM/USE chains
3. `pattern_detection` — Identify common code patterns
4. `impact_analysis` — Analyze change impact
5. `documentation_gen` — Generate documentation
6. `translation_hints` — Map to modern language equivalents
7. `bug_pattern_search` — Find potential issues
8. `business_logic` — Extract business rules

---

## Document Structure

Create `Docs/architecture/system-design.md` with the following sections:

### 1. System Overview
- What LegacyLens does (1-2 paragraphs)
- Key design decisions (custom pipeline, no LangChain, why)
- High-level data flow diagram (ASCII art or markdown)

### 2. Ingestion Pipeline
Document the flow: raw source → preprocessor → chunker → embedder → indexer

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Language detector | `src/ingestion/detector.py` | 108 | Route files to correct pipeline by extension |
| COBOL preprocessor | `src/ingestion/cobol_parser.py` | 209 | Fixed-format column stripping, comment extraction, continuation handling |
| Fortran preprocessor | `src/ingestion/fortran_parser.py` | 313 | Fixed/free form detection, encoding detection with UTF-7 guard |
| COBOL chunker | `src/ingestion/cobol_chunker.py` | 459 | Paragraph-boundary chunking, adaptive 64-768 tokens |
| Fortran chunker | `src/ingestion/fortran_chunker.py` | 498 | SUBROUTINE/FUNCTION/MODULE boundary chunking |
| Embedder | `src/ingestion/embedder.py` | 213 | Voyage Code 2, batch 128, timeout retry |
| Indexer | `src/ingestion/indexer.py` | 232 | Qdrant upsert with payload indexes |
| Orchestrator | `src/ingestion/ingest.py` | 259 | Reusable `ingest_codebase()` with rate limiting |

Key design details to document:
- Chunk size: adaptive 64-768 tokens on structural boundaries (not arbitrary windows)
- COBOL fixed-format: cols 1-6 stripped (sequence numbers), col 7 indicators, cols 73-80 stripped
- Fortran: extension-based format detection (`.f`/`.f77` = fixed, `.f90`/`.f95` = free)
- Encoding: chardet with ASCII fast-path and UTF-7 override guard
- Empty chunk filtering before embedding

### 3. Retrieval Pipeline
Document: query → embed → hybrid search → rerank → context

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Hybrid search | `src/retrieval/search.py` | 506 | Dense + BM25 via Qdrant, query-adaptive weighting |
| Re-ranker | `src/retrieval/reranker.py` | 374 | Metadata scoring (paragraph name, division) + Cohere cross-encoder |

Key design details:
- Hybrid search: dense vectors + BM25 keyword matching, fused with RRF
- Query-adaptive weighting: identifier-heavy queries boost BM25, semantic queries boost dense
- Re-ranking: metadata-first (free, always runs) → Cohere cross-encoder (optional, 40/60 blend)
- Confidence scoring: HIGH/MEDIUM/LOW based on reranker scores
- Codebase filter flows through all stages

### 4. Generation Pipeline

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Prompt builder | `src/generation/prompts.py` | 233 | Feature-specific system prompts, chunk formatting, citation rules |
| LLM client | `src/generation/llm.py` | 431 | GPT-4o with 4o-mini fallback, streaming support |

Key design details:
- Feature differentiation via prompt templates (not separate retrieval strategies)
- Citation enforcement: `file:start-end` format in system prompt
- Confidence labeling: model instructed to output HIGH/MEDIUM/LOW
- Fallback: GPT-4o → GPT-4o-mini on failure

### 5. API Layer

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| App | `src/api/app.py` | 47 | FastAPI app with CORS |
| Routes | `src/api/routes.py` | 145 | `/api/query`, `/api/stream`, `/api/health`, `/api/codebases` |
| Schemas | `src/api/schemas.py` | 140 | Pydantic request/response contracts |
| Client | `src/api/client.py` | 320 | Python API client |

### 6. Evaluation

- Ground truth: 27 queries across 5 codebases and 8 features
- Metric: precision@5 (at least one expected file/name in top-5 chunks)
- Result: **81.5%** overall (91.7% excluding gfortran which had 0 indexed chunks)
- Per-codebase: gnucobol 100%, opencobol-contrib 100%, blas 88%, lapack 86%

### 7. Deployment

- API: Render (Docker, `Dockerfile` in repo root)
- Frontend: Vercel (Next.js 14)
- Vector DB: Qdrant Cloud
- URL: `https://gauntlet-assignment-3.onrender.com`

### 8. Data Flow Diagram

Include an ASCII diagram showing the full request path:

```
User Query
    │
    ▼
FastAPI (/api/query)
    │
    ├─ Voyage Code 2 (embed query)
    │
    ├─ Qdrant (hybrid: dense + BM25)
    │       │
    │       ├─ codebase filter (optional)
    │       └─ top_k results
    │
    ├─ Reranker
    │       ├─ metadata scoring (paragraph, division)
    │       └─ Cohere cross-encoder (optional)
    │
    ├─ GPT-4o (generate answer)
    │       ├─ feature-specific system prompt
    │       ├─ formatted chunk context
    │       └─ citation + confidence rules
    │
    ▼
QueryResponse (answer, chunks, confidence, model)
```

---

## Deliverables

- [ ] `Docs/architecture/system-design.md` created
- [ ] All 8 sections covered
- [ ] Data flow diagram included
- [ ] Module table with file paths and line counts
- [ ] Evaluation metrics included
- [ ] No code changes

### Files to Create

| File | Action |
|------|--------|
| `Docs/architecture/system-design.md` | Create architecture document |

### Files to READ for Context

| File | Why |
|------|-----|
| `src/config.py` | All configuration constants |
| `src/ingestion/*.py` | Ingestion pipeline details |
| `src/retrieval/search.py` | Hybrid search implementation |
| `src/retrieval/reranker.py` | Re-ranking implementation |
| `src/generation/prompts.py` | Prompt templates |
| `src/generation/llm.py` | LLM client |
| `src/api/routes.py` | API endpoints |
| `src/api/schemas.py` | Request/response contracts |
| `Docs/tickets/DEVLOG.md` | Ingestion stats, evaluation results |
| `Dockerfile` | Deployment config |

### Files You Should NOT Modify

- Any source code in `src/`
- Test files
- Evaluation files
- Config files
