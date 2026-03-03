---
name: legacylens-constraints
description: Non-negotiable architectural guardrails for the LegacyLens RAG project. Use on EVERY LegacyLens task to prevent architectural violations. Triggers on any work involving src/, tests/, frontend/, evaluation/, or project configuration files in the LegacyLens workspace.
---

# LegacyLens Project Guardrails

## Pipeline Architecture

Custom RAG pipeline — NO LangChain, NO LlamaIndex, NO framework wrappers.

Build all pipeline stages from scratch using direct SDK calls:
- `voyageai` for embeddings
- `openai` for LLM generation
- `qdrant-client` for vector storage/search
- `cohere` for re-ranking

## Code Standards

- Python 3.11+ with type hints on every function signature and return type
- No `Any` types — use explicit typing everywhere
- Environment variables via `python-dotenv` through `src/config.py` — never hardcode keys
- Error handling: `try/except` with typed exceptions, not bare `except:`
- All imports use absolute paths from `src.` root

## Module Ownership

| Directory | Owns |
|-----------|------|
| `src/ingestion/` | File discovery, preprocessing, chunking, embedding, indexing |
| `src/retrieval/` | Hybrid search, re-ranking, context assembly |
| `src/generation/` | Prompt templates, LLM calls, streaming |
| `src/features/` | Feature router, 8 feature handlers |
| `src/api/` | FastAPI app, routes, Pydantic schemas |
| `src/cli/` | Click CLI, Rich formatting |
| `src/types/` | Dataclasses: `Chunk`, `ProcessedFile`, `EmbeddedChunk`, `QueryResponse`, `FeatureConfig` |
| `src/config.py` | All env vars, constants, codebase registry |
| `tests/` | Pytest — one `test_<module>.py` per source module |
| `frontend/` | Next.js 14, App Router, Tailwind CSS v4 |

Do not put logic in the wrong module. Retrieval code does not go in `src/ingestion/`. Feature logic does not go in `src/retrieval/`.

## Chunking Rules

- ALWAYS use structural boundaries (COBOL paragraphs, Fortran subroutines)
- NEVER use fixed-size chunking
- Token range: 64–768 tokens (adaptive)
- Tokenizer: `tiktoken` with `cl100k_base` encoding

## Embedding Rules

- Model: Voyage Code 2 via `voyageai` SDK
- Batch size: 128 texts per API call — never one-at-a-time
- Dimensions: 1536
- Retry with exponential backoff on timeout (3 attempts)

## Search & Retrieval Rules

- Hybrid search: dense + BM25 sparse via Qdrant native
- Re-ranking: metadata-first (free) → Cohere cross-encoder
- Context budget: 5,000 tokens total (2,000 top-1 expansion, 3,000 breadth)
- All answers must include `file:line` citations

## Completeness Requirements

- All 5 codebases: gnucobol, gfortran, lapack, blas, opencobol-contrib
- All 8 features: code_explanation, dependency_mapping, pattern_detection, impact_analysis, documentation_gen, translation_hints, bug_pattern_search, business_logic
- Both interfaces: CLI (Click + Rich) AND Web (Next.js 14)
- LLM model configurable via `LEGACYLENS_LLM_MODEL` env var
- Fallback chain: GPT-4o → GPT-4o-mini on rate limit or timeout

## Commit Discipline

Conventional Commits only: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

Every commit on `main` must be deployable. Commit after every working feature increment.

## Chunk Metadata Schema

Every chunk payload must include all fields:

```python
{
    "file_path": str,
    "line_start": int,
    "line_end": int,
    "name": str,        # paragraph or subroutine name
    "division": str,    # COBOL division or Fortran module
    "chunk_type": str,  # "paragraph", "subroutine", "function", etc.
    "language": str,    # "cobol" or "fortran"
    "codebase": str,    # "gnucobol", "gfortran", etc.
    "dependencies": list[str],
}
```
