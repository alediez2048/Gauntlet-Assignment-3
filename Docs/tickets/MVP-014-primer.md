# MVP-014 Primer: CLI Integration via FastAPI Backend

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-013 (FastAPI query route integration) should be complete before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-014 implements the first production CLI path by routing CLI queries through the FastAPI backend instead of duplicating retrieval/rerank/generation logic in the CLI layer.

In prior tickets, the pipeline stages were implemented in backend modules and wired behind API routes:

- retrieval (`src/retrieval/search.py`)
- reranking (`src/retrieval/reranker.py`)
- prompt and generation (`src/generation/prompts.py`, `src/generation/llm.py`)
- API orchestration (`src/api/routes.py` + `/api/query` and optional `/api/stream`)

MVP-014 should make CLI a thin client that calls API contracts and renders results.

### Why It Matters

- **Interface parity:** backend behavior remains consistent across web and CLI consumers.
- **Single orchestration boundary:** retrieval/rerank/generation stays centralized in API routes.
- **Lower maintenance cost:** CLI no longer risks drift from backend runtime logic.
- **Deployment readiness:** CLI can target local or remote API using one client contract.

---

## What Was Already Done

- MVP-009 hybrid retrieval complete (`src/retrieval/search.py`)
- MVP-010 reranker complete (`src/retrieval/reranker.py`)
- MVP-011 prompt builders complete (`src/generation/prompts.py`)
- MVP-012 LLM runtime complete (`src/generation/llm.py`)
- MVP-013 API routes complete:
  - `POST /api/query`
  - optional `POST /api/stream`
  - baseline `GET /api/health`, `GET /api/codebases`
- Existing placeholders currently available for CLI integration:
  - `src/api/client.py`
  - `src/cli/main.py`
  - `tests/test_cli.py`

---

## MVP-014 Contract (Critical Reference)

### CLI Query Behavior

CLI should call the same API contract used by web clients.

Primary request path:

```http
POST /api/query
```

Recommended request payload:

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

Optional streaming path:

```http
POST /api/stream
```

Expected CLI orchestration behavior:

1. parse CLI args/options
2. build typed API request payload
3. call `/api/query` (or `/api/stream` when requested)
4. render answer + citations/confidence clearly in terminal
5. surface deterministic, actionable errors

---

## What MVP-014 Must Accomplish

### Goal

Implement a CLI integration layer that sends queries to FastAPI endpoints and renders response contracts without re-implementing retrieval/reranking/generation in CLI modules.

### Deliverables Checklist

#### A. API Client Module (`src/api/client.py`)

- [ ] Add typed request helper for `/api/query`
- [ ] Add typed helper for optional `/api/stream`
- [ ] Use configurable base URL (`LEGACYLENS_API_URL` from `src/config.py`)
- [ ] Implement deterministic timeout and transport error mapping
- [ ] Parse JSON response into stable shape compatible with `QueryResponse` fields
- [ ] Keep this module as transport-only client logic (no retrieval/rerank/generation logic)

#### B. CLI Entry/Command Layer (`src/cli/main.py`)

- [ ] Implement query command that accepts:
  - query text
  - `--feature`
  - `--codebase`
  - `--top-k`
  - `--language`
  - `--model`
  - optional `--stream`
- [ ] Call API client (`src/api/client.py`) rather than backend pipeline modules directly
- [ ] Render response output including:
  - answer text
  - confidence
  - model
  - citations/chunk references
  - latency where available
- [ ] Add deterministic non-zero exits for invalid input/transport/API failures
- [ ] Keep CLI layer thin (no business logic duplication from API route layer)

#### C. Tests (`tests/test_cli.py`)

- [ ] TDD first: add tests before CLI implementation
- [ ] Add tests for:
  - successful CLI query path (mocked API client)
  - option passthrough for `feature`, `codebase`, `top_k`, `language`, `model`
  - validation for blank query
  - transport/API failure handling and user-facing error output
  - optional stream-mode behavior if implemented
- [ ] Minimum: 8+ focused tests

#### D. Documentation

- [ ] Add MVP-014 implementation entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document CLI->API assumptions (base URL, timeout, error mapping)
- [ ] Document any stream UX decisions (`--stream` behavior, fallback)

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before implementation:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-014-cli-api-integration`
- Never commit directly to `main`.
- Use Conventional Commits (`test:`, `feat:`, `fix:`, `docs:`).
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-014-cli-api-integration`

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/api/client.py` | Implement API transport helpers for query/stream |
| `src/cli/main.py` | Implement CLI command(s) that call API client |
| `tests/test_cli.py` | Add CLI integration tests |
| `Docs/tickets/DEVLOG.md` | Add MVP-014 completion entry |

### Files You Should NOT Modify

- `src/retrieval/search.py` (MVP-009 scope)
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/generation/prompts.py` (MVP-011 scope)
- `src/generation/llm.py` (MVP-012 scope)
- `src/api/routes.py` and `src/api/schemas.py` for behavior changes unless bugfix required
- ingestion modules in `src/ingestion/*`

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/api/routes.py` | API query/stream behavior and error semantics |
| `src/api/schemas.py` | Request/response shape expected by backend |
| `src/api/app.py` | API baseline and route wiring |
| `src/config.py` | `LEGACYLENS_API_URL`, features list, defaults |
| `src/types/responses.py` | `QueryResponse`, `RetrievedChunk`, `Confidence` contracts |
| `tests/test_api.py` | Expected API contract behavior that CLI should consume |

---

## Suggested Implementation Pattern

### API Client Usage

```python
payload = {
    "query": query,
    "feature": feature,
    "codebase": codebase,
    "top_k": top_k,
    "language": language,
    "model": model,
}
response = post_query(payload)
```

### CLI Command Flow

```python
if stream:
    for token in stream_query(payload):
        render_stream_token(token)
else:
    result = post_query(payload)
    render_query_response(result)
```

### Error Mapping

- CLI validation errors -> user-friendly message + non-zero exit
- API HTTP 4xx -> actionable usage/config feedback
- API HTTP 5xx / transport failures -> backend/runtime failure messaging

---

## Edge Cases to Handle

1. blank query input from CLI args
2. invalid `top_k` from CLI options
3. unreachable API host / timeout
4. API returns non-JSON or unexpected payload shape
5. API returns validation errors from `/api/query` (422/400 semantics)
6. API returns runtime error (`500`) with stage-prefixed detail
7. stream endpoint interrupted mid-response
8. non-ASCII query input and terminal output rendering

---

## Definition of Done for MVP-014

- [ ] CLI query command implemented via API client (no backend logic duplication)
- [ ] typed API client helpers implemented for `/api/query` (and optional `/api/stream`)
- [ ] CLI tests added and passing in `tests/test_cli.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-014 implementation entry
- [ ] feature branch pushed and PR opened for review

---

## Estimated Time: 60-100 minutes

| Task | Estimate |
|------|----------|
| Define API client helpers | 15-25 min |
| Write failing CLI tests | 15-25 min |
| Implement CLI command wiring | 20-35 min |
| Error handling and edge-case pass | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-014: What Comes Next

- **MVP-015:** deployment hardening and production smoke tests.
- **MVP-016+:** UX improvements, richer output formatting, and feature-specific command ergonomics.

MVP-014 should leave CLI as a thin backend consumer so all clients share a single, reliable orchestration path.

