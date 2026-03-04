# MVP-007 Primer: Batch Embedding Module

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-006 (COBOL metadata extraction) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-007 implements the **batch embedding module** that converts chunked code into vectors using Voyage Code 2.

In MVP-006, chunks are metadata-complete and dependency-aware. In MVP-007, those chunks must be embedded in deterministic batches and returned as `EmbeddedChunk` objects for indexing in MVP-008.

### Why It Matters

- **Retrieval foundation:** Dense vectors are required for semantic search quality.
- **Performance:** Batch embedding is mandatory for throughput and API cost control.
- **Pipeline readiness:** MVP-008 indexer expects stable `EmbeddedChunk` payloads.
- **Contract quality:** Dimensions, order, and IDs must be consistent before storage.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- Dataclasses already exist in `src/types/chunks.py`:
  - `Chunk`
  - `EmbeddedChunk`
- Embedding config constants already exist in `src/config.py`:
  - `EMBEDDING_MODEL`
  - `EMBEDDING_BATCH_SIZE`
  - `EMBEDDING_DIMENSIONS`
  - `VOYAGE_API_KEY`
- `requirements.txt` already includes `voyageai`

---

## Embedding Contract (Critical Reference)

MVP-007 should produce `EmbeddedChunk` outputs with strict invariants:

```python
EmbeddedChunk(
    chunk=Chunk(...),
    embedding=list[float],  # length == 1536
    chunk_id=str,           # deterministic ID for downstream indexing
)
```

Hard requirements from project rules:

- Model: Voyage Code 2 (`EMBEDDING_MODEL`)
- Batch size: 128 texts per API call (`EMBEDDING_BATCH_SIZE`)
- Vector dimensions: 1536 (`EMBEDDING_DIMENSIONS`)
- Retry on timeout with exponential backoff (3 attempts)
- No LangChain, no LlamaIndex

---

## What MVP-007 Must Accomplish

### Goal

Implement a production-ready embedding module in `src/ingestion/embedder.py` that embeds chunk content in batches and returns deterministic, validated `EmbeddedChunk` objects.

### Deliverables Checklist

#### A. Embedding Logic (`src/ingestion/embedder.py`)

- [ ] Create public embedding API:
  - `embed_chunks(chunks: list[Chunk], model: str = EMBEDDING_MODEL, batch_size: int = EMBEDDING_BATCH_SIZE) -> list[EmbeddedChunk]`
- [ ] Use `voyageai.Client` with `VOYAGE_API_KEY` from config
- [ ] Embed in **batch mode only** (never one API call per chunk)
- [ ] Use `input_type="document"` for chunk embeddings
- [ ] Preserve input chunk order in output `EmbeddedChunk` list
- [ ] Build deterministic `chunk_id` for each output
- [ ] Validate each embedding length equals `EMBEDDING_DIMENSIONS`
- [ ] Implement retry policy:
  - max 3 attempts
  - exponential backoff
  - typed exception handling (no bare except)
- [ ] Handle empty input safely (`[] -> []`)
- [ ] Keep module ingestion-only:
  - no Qdrant calls
  - no retrieval logic
  - no generation logic

#### B. Unit Tests (`tests/test_embedder.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test return contract:
  - returns `list[EmbeddedChunk]`
  - each item contains original `Chunk`
- [ ] Test batching:
  - 0 chunks -> 0 API calls
  - 1 chunk -> 1 API call
  - 257 chunks -> 3 API calls with sizes 128, 128, 1
- [ ] Test request shape:
  - model argument passed correctly
  - `input_type="document"` always used
- [ ] Test dimension validation:
  - 1536-length vectors pass
  - wrong-length vectors raise deterministic error
- [ ] Test deterministic IDs:
  - same chunk input yields same `chunk_id`
- [ ] Test retry behavior:
  - transient timeout recovers before 3rd attempt
  - permanent timeout fails after max retries
- [ ] Test order stability:
  - output vectors align with original chunk order
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Consumes real `list[Chunk]` output from `chunk_cobol(...)`
- [ ] Output is directly consumable by MVP-008 indexer
- [ ] No change to existing chunking contracts in MVP-006
- [ ] Works for chunks from both COBOL programs and copybooks

#### D. Documentation

- [ ] Add MVP-007 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document retry assumptions and error behavior
- [ ] Record helper signatures introduced in `embedder.py`

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-007-batch-embedding`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-007-batch-embedding`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/embedder.py` | Implement batch embedding and retry logic |
| `tests/test_embedder.py` | Add unit tests for batching/validation/retries |
| `Docs/tickets/DEVLOG.md` | Add MVP-007 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 complete)
- `src/ingestion/cobol_parser.py` (MVP-004 complete)
- `src/ingestion/cobol_chunker.py` (MVP-005/006 complete)
- `src/config.py` unless blocked by missing constants
- Retrieval modules (`src/retrieval/*`) for this ticket
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/chunks.py` | `Chunk` and `EmbeddedChunk` contracts |
| `src/config.py` | Embedding model, batch size, dimensions, API key |
| `src/ingestion/cobol_chunker.py` | Real upstream chunk shape and metadata |
| `requirements.txt` | `voyageai` dependency availability |
| `.cursor/rules/tech-stack.mdc` | Required embedding tech stack |
| `.cursor/rules/tdd.mdc` | Test-first workflow requirements |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - embedding constraints and architecture
- `.cursor/rules/tech-stack.mdc` - Voyage Code 2 + SDK requirements
- `.cursor/rules/multi-codebase.mdc` - preserve cross-codebase compatibility

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def embed_chunks(
    chunks: list[Chunk],
    model: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> list[EmbeddedChunk]:
```

### Processing Flow

```python
def embed_chunks(chunks, model=EMBEDDING_MODEL, batch_size=EMBEDDING_BATCH_SIZE):
    if not chunks:
        return []

    client = _build_voyage_client()
    texts = [chunk.content for chunk in chunks]
    vectors = []

    for batch in _batched(texts, batch_size):
        vectors.extend(
            _embed_batch_with_retry(
                client=client,
                texts=batch,
                model=model,
                input_type="document",
            )
        )

    return _attach_vectors(chunks, vectors)
```

Suggested helper responsibilities:

- `_build_voyage_client() -> voyageai.Client`
- `_batched[T](items: list[T], size: int) -> list[list[T]]`
- `_embed_batch_with_retry(...) -> list[list[float]]`
- `_validate_dimensions(vectors: list[list[float]]) -> None`
- `_build_chunk_id(chunk: Chunk) -> str`
- `_attach_vectors(chunks: list[Chunk], vectors: list[list[float]]) -> list[EmbeddedChunk]`

### Deterministic Chunk ID Strategy

Use a stable format that downstream indexing can trust:

```text
{codebase}:{file_path}:{line_start}
```

If collisions are observed later (for example, after split behavior changes), expand the key in MVP-008 rather than introducing non-deterministic UUIDs here.

### Retry Strategy

- Attempt embedding call up to 3 times for transient failures
- Backoff schedule example: 0.5s, 1.0s, 2.0s
- Re-raise typed exception after final attempt
- Avoid swallowing errors silently

---

## Edge Cases to Handle

1. **Empty chunk list:** Return empty list, no client call
2. **Whitespace-only chunk content:** Deterministic handling (embed or fail fast consistently)
3. **Final partial batch:** Correctly process batch sizes not divisible by 128
4. **Dimension mismatch:** Raise explicit error with expected vs actual size
5. **Timeout / transient API errors:** Retry up to 3 attempts then fail
6. **Order drift risk:** Ensure vectors map to input chunks in exact order
7. **Missing API key:** Fail clearly with actionable error message

---

## Test Fixture Suggestions

```python
@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            content="MAIN-LOGIC.\n    PERFORM INIT-DATA.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=10,
            line_end=11,
            chunk_type="paragraph",
            language="cobol",
            codebase="gnucobol",
            name="MAIN-LOGIC",
            division="PROCEDURE",
            token_count=18,
            metadata={"paragraph_name": "MAIN-LOGIC"},
        ),
        Chunk(
            content="INIT-DATA.\n    MOVE 1 TO WS-COUNT.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=20,
            line_end=21,
            chunk_type="paragraph",
            language="cobol",
            codebase="gnucobol",
            name="INIT-DATA",
            division="PROCEDURE",
            token_count=16,
            metadata={"paragraph_name": "INIT-DATA"},
        ),
    ]
```

Mocking guidance:

- Use a fake `voyageai.Client` in tests
- Return deterministic vectors (`[0.01] * 1536`, etc.)
- Simulate timeout errors on first call to test retries
- Assert call counts and batch sizes directly

Core assertions:

- output length equals input chunk count
- each embedding vector has 1536 dimensions
- deterministic `chunk_id` values
- batch splitting follows configured batch size
- no network access in unit tests (all mocked)

---

## Definition of Done for MVP-007

- [ ] `src/ingestion/embedder.py` implemented with `embed_chunks()` and helper logic
- [ ] Embedding calls are batch-only and use Voyage Code 2 config
- [ ] Retry with exponential backoff implemented (3 attempts)
- [ ] All output vectors validated to 1536 dimensions
- [ ] Output is `list[EmbeddedChunk]` with deterministic `chunk_id`
- [ ] Unit tests added and passing in `tests/test_embedder.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-007 entry
- [ ] Work completed on `feature/mvp-007-batch-embedding` and merged via PR

---

## Estimated Time: 45-75 minutes

| Task | Estimate |
|------|----------|
| Review chunk contract + embedding constants | 10 min |
| Write failing embedder tests | 20 min |
| Implement batch embedder + retry logic | 20 min |
| Handle edge cases + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-007: What Comes Next

- **MVP-008:** Qdrant indexer with payload indexes and batched upserts
- **MVP-009:** Hybrid retrieval (dense + BM25) and reranking pipeline

MVP-007 should leave ingestion outputs vectorized, validated, and stable so indexing can be implemented without changing embedding contracts.

