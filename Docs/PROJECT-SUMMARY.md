# LegacyLens — Project Summary

**What we built, why we built it this way, and the decisions that shaped each layer.**

---

## The Problem

Enterprise organizations maintain millions of lines of COBOL and Fortran code that power critical infrastructure — banking, logistics, scientific computing. The developers who wrote this code are retiring. The developers inheriting it can't read it. Traditional search tools don't understand the structure of 1960s-era programming languages. There is no "go to definition" for a COBOL paragraph. There is no IDE with Fortran subroutine analysis.

LegacyLens makes these codebases queryable through natural language. Ask a question in English, get a cited answer pointing to the exact file and line number.

---

## What We Built

A **custom RAG (Retrieval-Augmented Generation) pipeline** — from raw COBOL/Fortran source files all the way to a deployed web UI. No LangChain. No LlamaIndex. Every layer hand-built for the problem domain.

| Layer | What It Does | Key Technology |
|-------|-------------|----------------|
| **Preprocessing** | Strips COBOL column formatting (cols 1-6, 73-80), detects encoding, separates comments | chardet, custom parsers |
| **Chunking** | Splits code on language-native boundaries (COBOL paragraphs, Fortran subroutines) | tiktoken, adaptive 64-768 tokens |
| **Embedding** | Converts chunks into 1536-dim vectors in batches of 128 | Voyage Code 2 |
| **Storage** | Indexes vectors + rich metadata in a hybrid-capable vector database | Qdrant Cloud |
| **Retrieval** | Runs dual-channel search (dense semantic + sparse BM25) with query-adaptive weighting | Qdrant native hybrid |
| **Re-ranking** | Metadata-first boosts (paragraph name, division, dependencies) + Cohere cross-encoder | Cohere Rerank v3 |
| **Generation** | Produces cited answers with confidence levels using structured, language-aware prompts | GPT-4o with fallback to GPT-4o-mini |
| **API** | FastAPI backend serving all 8 features via a unified `/api/query` endpoint | FastAPI, deployed on Render |
| **CLI** | Terminal interface with Rich formatting for developer workflows | Click + Rich |
| **Web UI** | Dark-themed Next.js interface with feature selection, example queries, and citation display | Next.js 14, Tailwind, deployed on Vercel |

### The 8 Code Understanding Features

Every feature uses the same RAG backbone but with different retrieval strategies and prompt templates:

1. **Code Explanation** — plain English explanations with file:line citations
2. **Dependency Mapping** — trace PERFORM/CALL chains between paragraphs
3. **Pattern Detection** — find structurally similar code across the codebase
4. **Impact Analysis** — what breaks if this code changes?
5. **Documentation Generation** — auto-generate docs for undocumented code
6. **Translation Hints** — modern Python equivalents with caveats
7. **Bug Pattern Search** — detect anti-patterns with severity levels
8. **Business Logic Extraction** — identify business rules in plain English

---

## Why We Built It This Way

### Custom Pipeline Over Frameworks

The rules were explicit: no LangChain, no LlamaIndex. But this constraint turned out to be an advantage. Legacy COBOL has fixed-format column semantics (sequence numbers in cols 1-6, code in 7-72, identification in 73-80) that no generic chunker handles. Fortran has two completely different formatting modes (fixed-form and free-form) that must be detected per-file. A framework's "text splitter" would destroy the structure we need to preserve. Building custom meant every layer is optimized for the actual problem.

### Language-Specific Chunking Over Token Windows

Generic RAG systems chunk by token count or character windows. We chunk on **structural boundaries**: COBOL paragraphs (detected via Area A naming conventions in cols 8-11) and Fortran subroutines/functions (detected via `SUBROUTINE`/`FUNCTION`/`END` markers). This means every chunk is a semantically coherent unit — a complete paragraph or subroutine — not an arbitrary slice that cuts through a statement mid-sentence. Chunk sizes adapt between 64 and 768 tokens: small paragraphs get merged with their neighbors, oversized ones get split on period/statement boundaries.

### Hybrid Search Over Dense-Only

Pure semantic search misses identifier-heavy queries. If a developer asks "What does CALCULATE-INTEREST do?", the name `CALCULATE-INTEREST` is a specific identifier — you want exact lexical matching, not just semantic similarity. Our retrieval runs both channels simultaneously:

- **Dense (Voyage Code 2)** — semantic understanding of the query's meaning
- **Sparse (BM25)** — lexical matching on exact terms and identifiers

The weights adapt per-query: identifier-heavy queries (uppercase symbols, hyphens) favor BM25 (0.6 sparse / 0.4 dense); natural language queries favor dense (0.7 dense / 0.3 sparse). Results from both channels are normalized, fused, and deduplicated.

### Layered Re-ranking Over Single-Pass

Retrieval returns candidates. Re-ranking makes them precise. We use two layers:

1. **Metadata-first (free)** — boosts chunks where the paragraph name matches query terms, where the division is relevant (PROCEDURE DIVISION for code questions), and where dependency chains overlap. This is instant and costs nothing.
2. **Cohere cross-encoder (paid, optional)** — blends metadata scores (40%) with Cohere relevance scores (60%) for cross-encoder precision. Falls back gracefully if the API key is missing or the service errors.

### Voyage Code 2 Over General-Purpose Embeddings

We embed code, not prose. Voyage Code 2 is trained specifically on source code, producing 1536-dimensional vectors that capture programming semantics (control flow, variable relationships, call patterns) better than general-purpose text embeddings. All embedding calls use batch mode (128 texts per API call) to minimize latency and API cost.

### Single Qdrant Collection Over Per-Codebase Collections

All 5 codebases live in one shared collection with `codebase` and `language` payload indexes. This lets users query across all codebases by default or filter to a specific one. Payload indexes make filtered queries O(1) rather than requiring cross-collection fan-out.

### API Route Proxy Over Direct Backend Calls

The Next.js frontend doesn't call the Render backend directly from the browser. Instead, API routes in `app/api/query/route.ts` proxy requests server-side. This keeps the backend URL private, adds a 45-second timeout to handle Render free-tier cold starts, and provides a clean error boundary between the frontend and backend.

---

## How We Built It — The Execution

### Phase 0: Configure Before You Code

Before writing a single line of business logic, we established the full architecture:

- **76 files** created in the initial scaffold commit — every module, test file, type definition, config, and deployment file in place
- **5 Cursor rules** enforcing non-negotiable constraints (no LangChain, type hints everywhere, adaptive chunking, hybrid search, etc.)
- **Typed dataclass pipeline** defined upfront: `ProcessedFile` → `Chunk` → `EmbeddedChunk` → `RetrievedChunk` → `QueryResponse` — this contract prevented type drift as modules were implemented independently across sessions
- **Post-scaffolding assessment** caught 5 risks before implementation started, including a scheduling error that had evaluation before features were built

### MVP Phase (Tickets 001-016): Bottom-Up Pipeline

Each ticket followed strict TDD: write tests first, confirm they fail, implement the minimum code to pass, refactor after green.

| Ticket | Module | Tests | What It Proved |
|--------|--------|-------|---------------|
| MVP-003 | Language Detector | 33 | Extension → language routing works for all 7 supported extensions |
| MVP-004 | COBOL Preprocessor | 25 | Column stripping, encoding detection, comment separation handle real GnuCOBOL files |
| MVP-005/006 | Paragraph Chunker + Metadata | 13 | Paragraph boundaries detected correctly, adaptive sizing works, metadata schema consistent |
| MVP-007 | Batch Embedder | 11 | Voyage API integration works, retry/backoff handles transient failures, order preserved across batches |
| MVP-008 | Qdrant Indexer | 12 | Collection setup is idempotent, payload indexes created, batch upsert works |
| MVP-009 | Hybrid Search | 15 | Dense + BM25 fusion works, adaptive weighting dispatches correctly, codebase filtering propagates |
| MVP-010 | Re-ranker | 12 | Metadata boosts work, confidence mapping is deterministic, Cohere fallback is graceful |
| MVP-011 | Prompt Templates | 13 | Citation instructions enforced, confidence labels required, context formatting deterministic |
| MVP-012 | LLM Generation | 12 | GPT-4o integration works, fallback to mini on failure, confidence parsing and citation extraction stable |

**Total: 180 tests passing** at the end of the MVP phase.

### Deployment: Render + Qdrant Cloud + Vercel

- **Backend** on Render free tier — Dockerfile with Python 3.11-slim + uvicorn, auto-deploy on push
- **Vectors** on Qdrant Cloud — 1GB free tier, shared collection with payload indexes
- **Frontend** on Vercel — Next.js 14 with API route proxies, `LEGACYLENS_API_URL` set server-side

The deployment-first approach (getting a live health endpoint on Render during Phase 0) prevented late-stage blocker cascades. By the time the full pipeline was ready, deployment was a configuration change, not a debugging session.

---

## Architecture Decisions Record

| Decision | Chosen | Alternative Considered | Why |
|----------|--------|----------------------|-----|
| No LangChain/LlamaIndex | Custom pipeline | Framework-based | Language-specific preprocessing needs (COBOL columns, Fortran forms) can't be handled by generic framework components |
| Qdrant over Pinecone/Weaviate | Qdrant Cloud | Pinecone, Weaviate | Native hybrid search (dense + sparse in one query), free 1GB tier, payload indexes for metadata filtering |
| Voyage Code 2 over OpenAI embeddings | Voyage Code 2 | text-embedding-3-small | Code-specialized model captures programming semantics better; 1536 dims matches Qdrant config |
| Paragraph-based over token-window chunking | Structural boundaries | Fixed-size windows | COBOL paragraphs and Fortran subroutines are semantic units; splitting mid-statement destroys meaning |
| Single collection over per-codebase | Shared + metadata | 5 separate collections | Cross-codebase queries work naturally; payload indexes make filtered queries fast |
| Config-driven features over class hierarchy | Feature config dict | ABC class per feature | 5 of 8 features need only different prompts; config entries avoid 5x class duplication |
| Metadata-first re-ranking over Cohere-only | Two-layer (meta + Cohere) | Cohere-only | Metadata boosts are free and instant; Cohere adds precision but costs money and latency |
| GPT-4o with mini fallback | Primary + fallback | Single model | Timeout/rate-limit resilience without user-visible failure |
| Next.js API proxy over direct calls | Server-side proxy | Browser → Render direct | Hides backend URL, adds timeout handling, provides clean error boundary |

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Codebases indexed | 1 (GnuCOBOL for MVP; 5 planned for G4) |
| Files processed | 799 COBOL source files |
| Lines of code ingested | 283,208 |
| Test count | 180 passing |
| Features implemented | 8 of 8 |
| Interfaces | 2 (CLI + Web) |
| Deployment targets | 3 (Render + Qdrant Cloud + Vercel) |

---

## What's Next

With the MVP web UI deployed and the full pipeline operational:

- **G4 Phase**: Ingest remaining 4 codebases (GNU Fortran, LAPACK, BLAS, OpenCOBOL Contrib), build evaluation dataset with 50+ ground truth queries, run precision metrics, complete architecture and cost analysis documents
- **GFA Phase**: Polish both interfaces, record demo video, final regression testing, submission
