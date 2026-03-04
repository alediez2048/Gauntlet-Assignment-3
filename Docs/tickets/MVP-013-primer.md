# MVP-013 Primer: FastAPI Query Route Integration

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-012 (LLM runtime module) should be complete before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-013 implements the first end-to-end API orchestration path by wiring retrieval, reranking, prompt generation, and LLM runtime behind a FastAPI query endpoint.

In prior tickets, the pipeline pieces were implemented in isolation:

- retrieval (`src/retrieval/search.py`)
- reranking (`src/retrieval/reranker.py`)
- prompt builders (`src/generation/prompts.py`)
- LLM runtime (`src/generation/llm.py`)

MVP-013 composes those modules in API routes so clients can call one endpoint and receive a complete `QueryResponse`.

### Why It Matters

- **First user-facing integration:** backend endpoint enables real application queries.
- **Contract boundary:** defines stable request/response schema for CLI and frontend.
- **Reliability:** centralizes request validation and error handling.
- **Pipeline progression:** MVP-014 (CLI) should call this backend instead of duplicating runtime logic.

---

## What Was Already Done

- MVP-009 hybrid retrieval complete (`src/retrieval/search.py`)
- MVP-010 metadata-first reranking complete (`src/retrieval/reranker.py`)
- MVP-011 prompt builders complete (`src/generation/prompts.py`)
- MVP-012 LLM runtime complete (`src/generation/llm.py`)
- `QueryResponse` / `RetrievedChunk` / `Confidence` already exist in `src/types/responses.py`
- API app baseline exists (`src/api/app.py`) with:
  - `GET /api/health`
  - `GET /api/codebases`
- API placeholder files currently empty:
  - `src/api/routes.py`
  - `src/api/schemas.py`
  - `src/api/client.py`

---

## MVP-013 Route Contract (Critical Reference)

### Primary Route

```python
POST /api/query
```

Request body (suggested):

```json
{
  "query": "What does MAIN-LOGIC do?",
  "feature": "code_explanation",
  "codebase": "gnucobol",
  "top_k": 10,
  "language": "cobol",
  "model": null
}
```

Response: JSON representation of `QueryResponse`.

### Optional Route (Strongly Recommended)

```python
POST /api/stream
```

- Streams text chunks from `stream_answer(...)` as SSE/plain text.
- Must keep the same pipeline assembly and validation behavior as `/api/query`.

Expected orchestration behavior:

1. validate request payload
2. call `hybrid_search(...)`
3. call `rerank_chunks(...)`
4. call `generate_answer(...)` (or `stream_answer(...)`)
5. return stable response shape and actionable errors

---

## What MVP-013 Must Accomplish

### Goal

Implement API-layer orchestration in `src/api/` so a single POST request runs the full query pipeline and returns deterministic, citation-ready answers.

### Deliverables Checklist

#### A. API Schemas (`src/api/schemas.py`)

- [ ] Add typed Pydantic request schema for `/api/query`:
  - `query: str` (required)
  - `feature: str = "code_explanation"`
  - `codebase: str | None = None`
  - `top_k: int = 10`
  - `language: str = "cobol"`
  - `model: str | None = None`
- [ ] Add response schema (or deterministic serializer helper) compatible with `QueryResponse`
- [ ] Ensure validation errors are deterministic and user-facing

#### B. Route Handlers (`src/api/routes.py`)

- [ ] Implement `POST /api/query` route
- [ ] Route orchestration order:
  - retrieval -> rerank -> generation
- [ ] Pass through optional filters/params (`codebase`, `top_k`, `feature`, `language`, `model`)
- [ ] Return `QueryResponse` payload with citations/confidence/model/latency included
- [ ] Add typed error handling:
  - request validation errors -> 422/400
  - pipeline/runtime failures -> 500 with actionable message
- [ ] Keep route layer thin; no ingestion logic, no prompt-template mutation

#### C. App Wiring (`src/api/app.py`)

- [ ] Register API router from `src/api/routes.py`
- [ ] Preserve existing:
  - `GET /api/health`
  - `GET /api/codebases`
- [ ] Avoid changing deployment/runtime entrypoint behavior

#### D. Tests (`tests/test_api.py`)

- [ ] TDD first: write endpoint tests before route implementation
- [ ] Add tests for:
  - successful `/api/query` response contract
  - blank query validation
  - pipeline stage invocation order (mock-based)
  - codebase/top_k passthrough
  - failure mapping to proper HTTP status and message
- [ ] Add optional streaming tests if `/api/stream` is implemented
- [ ] Minimum: 8+ focused tests for MVP-013

#### E. Documentation

- [ ] Add MVP-013 implementation entry in `Docs/tickets/DEVLOG.md`
- [ ] Document route assumptions and error mapping
- [ ] Document any streaming behavior decisions

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before ticket implementation:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-013-fastapi-query-endpoint`
- Never commit directly to `main`.
- Use Conventional Commits (`test:`, `feat:`, `fix:`, `docs:`).
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-013-fastapi-query-endpoint`

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/api/schemas.py` | Add request/response API schemas |
| `src/api/routes.py` | Implement `/api/query` (and optional `/api/stream`) |
| `src/api/app.py` | Wire router into FastAPI app |
| `tests/test_api.py` | Add endpoint tests for MVP-013 |
| `Docs/tickets/DEVLOG.md` | Add MVP-013 completion entry |

### Files You Should NOT Modify

- `src/retrieval/search.py` (MVP-009 scope)
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/generation/prompts.py` (MVP-011 scope)
- `src/generation/llm.py` (MVP-012 scope, unless bugfix is required)
- `src/cli/*` (MVP-014 scope)
- ingestion modules in `src/ingestion/*`

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/api/app.py` | Existing app instance and baseline routes |
| `src/retrieval/search.py` | Retrieval API and input contract |
| `src/retrieval/reranker.py` | Rerank API and behavior |
| `src/generation/llm.py` | Generation runtime contract |
| `src/types/responses.py` | `QueryResponse` and `RetrievedChunk` fields |
| `tests/test_generation.py` | Runtime behavior expectations for generation |

---

## Suggested Implementation Pattern

### Route Orchestration

```python
results = hybrid_search(query=req.query, top_k=req.top_k, codebase=req.codebase)
reranked = rerank_chunks(query=req.query, chunks=results, feature=req.feature)
response = generate_answer(
    query=req.query,
    chunks=reranked,
    feature=req.feature,
    language=req.language,
    model=req.model,
)
```

### Error Mapping

- deterministic request validation errors -> `HTTPException(status_code=422 or 400, ...)`
- typed pipeline runtime errors -> `HTTPException(status_code=500, detail=...)`
- unexpected exceptions -> `HTTPException(status_code=500, detail="Internal server error")`

### Output Behavior

- API should preserve `QueryResponse` fields exactly:
  - `answer`, `chunks`, `query`, `feature`, `confidence`, `model`, `latency_ms`, optional `codebase_filter`
- no post-processing that strips citations or confidence line from answer text

---

## Edge Cases to Handle

1. blank query in request body
2. invalid `top_k` value (<= 0)
3. unsupported/unknown feature value
4. empty retrieval results (generation still runs with insufficient-evidence guidance)
5. retrieval failure (Qdrant/Voyage errors)
6. reranker failure path (metadata-only fallback behavior should remain intact)
7. generation primary/fallback failure propagation
8. non-ASCII query input

---

## Definition of Done for MVP-013

- [ ] `/api/query` implemented and wired into app router
- [ ] endpoint returns deterministic `QueryResponse`-compatible payloads
- [ ] API tests added and passing in `tests/test_api.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-013 entry
- [ ] branch pushed and PR opened for review

---

## Estimated Time: 75-120 minutes

| Task | Estimate |
|------|----------|
| Define Pydantic schemas | 10-20 min |
| Write failing API tests | 20-35 min |
| Implement routes + app wiring | 25-40 min |
| Error mapping + edge-case fixes | 10-20 min |
| DEVLOG update | 5-10 min |

---

## After MVP-013: What Comes Next

- **MVP-014:** CLI integration should call the API backend rather than duplicating retrieval/generation orchestration.
- **MVP-015:** deployment hardening once query route behavior is stable and smoke-tested.

MVP-013 should leave a clean API orchestration boundary so all clients share the same backend behavior.

