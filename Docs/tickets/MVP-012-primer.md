# MVP-012 Primer: LLM Generation Module

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-011 (prompt template layer) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-012 implements the **LLM invocation layer** that consumes MVP-011 prompts and returns grounded answers.

In MVP-011, prompt construction was isolated into deterministic builders in `src/generation/prompts.py`. In MVP-012, we wire those prompt messages into OpenAI chat completions with model fallback handling and output parsing, so downstream API/CLI routes can call generation without duplicating runtime logic.

### Why It Matters

- **Runtime boundary:** prompt design is complete; this ticket handles model transport and failure handling.
- **Reliability:** fallback from GPT-4o to GPT-4o-mini prevents single-model outages from failing queries.
- **Contract stability:** generation output must align with `QueryResponse` + confidence/citation expectations.
- **Pipeline sequencing:** MVP-013 API routes and MVP-014 CLI rely on this module as the generation backend.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- MVP-007 embedding is implemented (`src/ingestion/embedder.py`)
- MVP-008 indexing is implemented (`src/ingestion/indexer.py`)
- MVP-009 hybrid search is implemented (`src/retrieval/search.py`)
- MVP-010 reranking is implemented (`src/retrieval/reranker.py`)
- MVP-011 prompt templates are implemented (`src/generation/prompts.py`)
- Response dataclasses already exist in `src/types/responses.py`:
  - `RetrievedChunk`
  - `Confidence`
  - `QueryResponse`
- Model configuration already exists in `src/config.py`:
  - `LLM_MODEL`
  - `LLM_FALLBACK_MODEL`
  - `OPENAI_API_KEY`
- Generation module placeholder exists:
  - `src/generation/llm.py`
- Generation tests already exist:
  - `tests/test_generation.py` (currently MVP-011 prompt tests)

---

## LLM Module Contract (Critical Reference)

MVP-012 should define stable generation APIs in `src/generation/llm.py`:

```python
generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
    model: str | None = None,
) -> QueryResponse
```

Optional/strongly recommended streaming contract (for MVP-013/MVP-014 readiness):

```python
stream_answer(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
    model: str | None = None,
) -> Iterator[str]
```

Expected behavior:

- build messages via `src/generation/prompts.py` (`build_messages(...)`)
- call OpenAI chat completions with configurable model (default `LLM_MODEL`)
- fallback to `LLM_FALLBACK_MODEL` on timeout/rate-limit style failures
- parse confidence label (`HIGH`, `MEDIUM`, `LOW`) from model output
- keep citations grounded in `file:line` format (or `file:start-end` if returned that way)
- avoid retrieval, rerank, API route, or CLI logic in this module

Hard requirements from project rules:

- Generation ownership: `src/generation/llm.py`
- LLM model configurable via `LEGACYLENS_LLM_MODEL` env var
- Fallback chain: GPT-4o -> GPT-4o-mini
- All answers must include citation-ready references and confidence level
- No LangChain, no LlamaIndex

---

## What MVP-012 Must Accomplish

### Goal

Implement a production-ready LLM runtime module in `src/generation/llm.py` that converts query + retrieved chunks into a `QueryResponse` using MVP-011 prompt builders and OpenAI chat completions with robust fallback behavior.

### Deliverables Checklist

#### A. LLM Runtime Logic (`src/generation/llm.py`)

- [ ] Create public generation API:
  - `generate_answer(...) -> QueryResponse`
  - optional `stream_answer(...) -> Iterator[str]` for upcoming route/CLI use
- [ ] Validate inputs:
  - blank query raises deterministic error
  - `chunks is None` raises deterministic error
- [ ] Build message payload using `build_messages(...)` from MVP-011
- [ ] Implement OpenAI client creation from `OPENAI_API_KEY`
- [ ] Implement non-streaming chat completion path
- [ ] Implement fallback behavior:
  - primary model from `model` arg or `LLM_MODEL`
  - fallback to `LLM_FALLBACK_MODEL` on timeout/rate-limit-like failure
- [ ] Parse model output into:
  - answer text
  - confidence (`Confidence.HIGH | MEDIUM | LOW`)
  - citations (best-effort extraction in `file:line` or `file:start-end` forms)
- [ ] Build and return `QueryResponse` with:
  - original query
  - feature
  - chunks (as provided)
  - confidence enum
  - model actually used
  - latency (ms)
- [ ] Keep module generation-only:
  - no retrieval logic
  - no reranking logic
  - no API route logic
  - no CLI command logic

#### B. Unit Tests (`tests/test_generation.py`)

- [ ] TDD first: write tests before implementation changes
- [ ] Add tests for return contract:
  - `generate_answer` returns `QueryResponse`
  - response `model`, `feature`, `query`, `chunks` fields are populated correctly
- [ ] Add tests for validation:
  - blank query deterministic error
  - `chunks is None` deterministic error
- [ ] Add tests for prompt integration:
  - generation calls `build_messages(...)` exactly once with expected values
- [ ] Add tests for fallback behavior:
  - primary model success path
  - fallback model path on simulated timeout/rate limit
- [ ] Add tests for confidence parsing:
  - output containing `Confidence: HIGH|MEDIUM|LOW` maps correctly
  - missing/invalid label falls back deterministically (recommended: `LOW`)
- [ ] Add tests for citation extraction:
  - extracts at least `file:line` or `file:start-end` references when present
- [ ] Add tests for deterministic behavior:
  - same mocked completion + same inputs -> same `QueryResponse`
- [ ] Minimum: 10+ focused tests for MVP-012 additions

#### C. Integration Expectations

- [ ] Consumes `RetrievedChunk` list from retrieval/rerank unchanged in shape
- [ ] Consumes prompt contracts from MVP-011 unchanged in signature
- [ ] Produces `QueryResponse` compatible with upcoming API/CLI layers
- [ ] Keeps citation/confidence behavior aligned with project response standards

#### D. Documentation

- [ ] Add MVP-012 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document fallback behavior and failure assumptions
- [ ] Document helper signatures introduced in `llm.py`
- [ ] Record any streaming support assumptions if implemented

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-012-llm-generation-module`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-012-llm-generation-module`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/generation/llm.py` | Implement OpenAI runtime, fallback, parsing, and `QueryResponse` construction |
| `tests/test_generation.py` | Add LLM runtime tests (alongside existing prompt tests) |
| `Docs/tickets/DEVLOG.md` | Add MVP-012 completion entry (after done) |

### Files You May Need to Create

| File | Why |
|------|-----|
| `src/generation/__init__.py` | Optional exports if generation symbols are re-exported |

### Files You Should NOT Modify

- `src/retrieval/search.py` (MVP-009 scope)
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/generation/prompts.py` (MVP-011 contract should remain stable unless bugfix required)
- `src/api/*` (MVP-013 scope)
- `src/cli/*` (MVP-014 scope)
- `src/ingestion/*` modules (MVP-003 through MVP-008 are complete)
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/generation/prompts.py` | Upstream prompt message contract from MVP-011 |
| `src/types/responses.py` | `QueryResponse`, `RetrievedChunk`, `Confidence` contracts |
| `src/config.py` | `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_FALLBACK_MODEL` |
| `tests/test_generation.py` | Existing test style and fixtures |
| `.cursor/rules/rag-pipeline.mdc` | Citation/confidence generation constraints |
| `.cursor/rules/tdd.mdc` | Test-first workflow requirements |
| `.cursor/rules/code-patterns.mdc` | Typing and module ownership conventions |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - generation/citation/confidence constraints
- `.cursor/rules/tech-stack.mdc` - strict stack requirements
- `.cursor/rules/multi-codebase.mdc` - preserve future cross-codebase compatibility

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
    model: str | None = None,
) -> QueryResponse:
```

### Processing Flow

```python
def generate_answer(query, chunks, feature="code_explanation", language="cobol", model=None):
    _validate_generation_inputs(query=query, chunks=chunks)

    messages = build_messages(
        query=query,
        chunks=chunks,
        feature=feature,
        language=language,
    )

    selected_model = model or LLM_MODEL
    content, used_model = _complete_with_fallback(messages=messages, model=selected_model)

    confidence = _parse_confidence(content)
    citations = _extract_citations(content)

    return QueryResponse(
        answer=content,
        chunks=chunks,
        query=query,
        feature=feature,
        confidence=confidence,
        model=used_model,
        latency_ms=...,
    )
```

Suggested helper responsibilities:

- `_validate_generation_inputs(query: str, chunks: list[RetrievedChunk] | None) -> None`
- `_build_openai_client() -> OpenAI`
- `_complete_once(...) -> str`
- `_complete_with_fallback(...) -> tuple[str, str]`
- `_parse_confidence(text: str) -> Confidence`
- `_extract_citations(text: str) -> list[str]`
- `_now_ms() -> float`

### Output Parsing Strategy

Keep parsing deterministic and forgiving:

- confidence parser checks for exact labels `HIGH`, `MEDIUM`, `LOW` (case-insensitive match acceptable)
- if confidence label is absent, fallback to `Confidence.LOW`
- citation extractor collects unique patterns like:
  - `path/file.cob:120`
  - `path/file.cob:120-148`
- preserve first-seen citation order

### Fallback Strategy

- primary model: `model` argument or `LLM_MODEL`
- fallback model: `LLM_FALLBACK_MODEL`
- fallback only on transport/runtime failures (timeout/rate-limit style), not on validation errors
- if both models fail, raise typed `GenerationError` with actionable message

---

## Edge Cases to Handle

1. **Blank query:** deterministic validation error
2. **`chunks is None`:** deterministic validation error
3. **Empty chunk list:** still allow generation (prompt already carries insufficient-evidence guidance)
4. **Primary model timeout/rate limit:** fallback model invoked once
5. **Fallback model also fails:** typed generation error propagated
6. **Missing confidence label in model output:** deterministic fallback to `LOW`
7. **No citations present in output:** return empty list safely (no crash)
8. **Malformed OpenAI response shape:** typed parse/runtime error
9. **Non-ASCII source/context content:** no crash in message submission/parsing

---

## Test Fixture Suggestions

Use fake chat-completion responses and monkeypatch the OpenAI client to avoid network dependency.

```python
mock_content = (
    "The paragraph initializes counters.\n"
    "Citations: data/raw/gnucobol/sample.cob:10-11\n"
    "Confidence: HIGH"
)
```

Core assertions:

- `generate_answer(...)` returns `QueryResponse`
- `response.model` reflects primary or fallback model used
- `response.confidence` maps to `Confidence.HIGH | MEDIUM | LOW`
- `response.answer` contains model text
- citations are extracted deterministically when present
- same mocked input/output yields identical response structure

---

## Definition of Done for MVP-012

- [ ] `src/generation/llm.py` implemented with stable generation APIs
- [ ] OpenAI runtime path implemented with configurable model + fallback model
- [ ] Confidence parsing and citation extraction implemented deterministically
- [ ] Unit tests added and passing in `tests/test_generation.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-012 entry
- [ ] Work completed on `feature/mvp-012-llm-generation-module` and merged via PR

---

## Estimated Time: 60-90 minutes

| Task | Estimate |
|------|----------|
| Review prompt/runtime contracts + config | 10-15 min |
| Write failing LLM module tests | 20-30 min |
| Implement generation + fallback + parsing | 20-30 min |
| Edge-case handling + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-012: What Comes Next

- **MVP-013:** FastAPI query route wiring retrieval + rerank + prompt + generation
- **MVP-014:** CLI route integration with the same backend generation flow

MVP-012 should leave generation runtime deterministic and transport-safe so MVP-013 can focus on request/response orchestration instead of model internals.

