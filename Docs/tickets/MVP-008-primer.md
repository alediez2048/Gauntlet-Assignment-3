# MVP-008 Primer: Qdrant Indexer Module

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-007 (batch embedding module) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-008 implements the **Qdrant indexer module** that stores `EmbeddedChunk` vectors and metadata payloads into a single shared vector collection.

In MVP-007, chunks become deterministic `EmbeddedChunk` objects. In MVP-008, those objects must be validated, transformed into Qdrant points, and upserted in deterministic batches with retrieval-ready payload indexes.

### Why It Matters

- **Storage foundation:** Retrieval cannot start until vectors are indexed in Qdrant.
- **Performance:** Batch upserts are required for throughput and cost control.
- **Retrieval readiness:** Payload indexes unlock fast metadata filtering in MVP-009.
- **Contract quality:** IDs, dimensions, and payload shape must be stable before search.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- MVP-007 embedding is implemented (`src/ingestion/embedder.py`)
- Dataclasses already exist in `src/types/chunks.py`:
  - `Chunk`
  - `EmbeddedChunk`
- Qdrant config constants already exist in `src/config.py`:
  - `QDRANT_URL`
  - `QDRANT_API_KEY`
  - `QDRANT_COLLECTION_NAME`
  - `EMBEDDING_DIMENSIONS`
- `requirements.txt` already includes `qdrant-client`

---

## Indexing Contract (Critical Reference)

MVP-008 should consume `EmbeddedChunk` values and persist Qdrant points with strict invariants:

```python
PointStruct(
    id=embedded_chunk.chunk_id,          # deterministic ID from MVP-007
    vector=embedded_chunk.embedding,     # length == 1536
    payload={...},                       # retrieval-ready metadata + content
)
```

Suggested public contract:

```python
index_chunks(
    embedded_chunks: list[EmbeddedChunk],
    collection_name: str = QDRANT_COLLECTION_NAME,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> int
```

Hard requirements from project rules:

- Vector database: Qdrant (`qdrant-client`)
- Single shared collection across codebases
- Vector dimensions: 1536 (`EMBEDDING_DIMENSIONS`)
- Payload indexes required on:
  - `paragraph_name`
  - `division`
  - `file_path`
  - `language`
  - `codebase`
- Batch upsert only (no one-point calls in a loop)
- No LangChain, no LlamaIndex

---

## What MVP-008 Must Accomplish

### Goal

Implement a production-ready indexing module in `src/ingestion/indexer.py` that creates/validates Qdrant collection structure and upserts `EmbeddedChunk` records in deterministic batches.

### Deliverables Checklist

#### A. Indexing Logic (`src/ingestion/indexer.py`)

- [ ] Create public indexing API:
  - `index_chunks(embedded_chunks: list[EmbeddedChunk], collection_name: str = QDRANT_COLLECTION_NAME, batch_size: int = EMBEDDING_BATCH_SIZE) -> int`
- [ ] Build `QdrantClient` from config (`QDRANT_URL`, `QDRANT_API_KEY`)
- [ ] Ensure collection exists with correct vector configuration:
  - size: `EMBEDDING_DIMENSIONS`
  - distance: cosine
- [ ] Create payload indexes idempotently for required fields:
  - `paragraph_name`, `division`, `file_path`, `language`, `codebase`
- [ ] Convert each `EmbeddedChunk` to a deterministic `PointStruct`:
  - `id = chunk_id`
  - `vector = embedding`
  - `payload = normalized metadata + content fields`
- [ ] Upsert points in **batch mode only**
- [ ] Preserve input ordering for deterministic processing and testability
- [ ] Validate vector dimensions before upsert
- [ ] Handle empty input safely (`[] -> 0`, no upsert calls)
- [ ] Use typed exceptions (no bare `except`)
- [ ] Keep module ingestion-only:
  - no retrieval ranking logic
  - no generation logic
  - no API route logic

#### B. Unit Tests (`tests/test_indexer.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test return contract:
  - returns upserted point count (`int`)
- [ ] Test collection behavior:
  - creates collection when missing
  - does not recreate when already present
  - uses `EMBEDDING_DIMENSIONS` and cosine distance
- [ ] Test payload index creation:
  - required fields are indexed
  - index creation path is idempotent
- [ ] Test batching:
  - 0 chunks -> 0 upsert calls
  - 1 chunk -> 1 upsert call
  - 257 chunks -> 3 upsert calls (128, 128, 1)
- [ ] Test point mapping:
  - point IDs equal `chunk_id`
  - payload fields map correctly from `Chunk` + metadata
- [ ] Test dimension validation:
  - 1536-length vectors pass
  - wrong-length vectors raise deterministic error
- [ ] Test config failure behavior:
  - missing `QDRANT_URL` raises actionable error
- [ ] Test Qdrant client errors are surfaced as typed failures
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Consumes real `list[EmbeddedChunk]` output from `embed_chunks(...)`
- [ ] Supports deterministic IDs from MVP-007 without mutation
- [ ] Writes to one shared collection (`QDRANT_COLLECTION_NAME`)
- [ ] Payload supports upcoming retrieval/index filters (MVP-009+)
- [ ] Compatible with multi-codebase ingestion strategy

#### D. Documentation

- [ ] Add MVP-008 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document collection/index assumptions and idempotency behavior
- [ ] Record helper signatures introduced in `indexer.py`
- [ ] Note any SDK-specific caveats discovered during implementation

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-008-qdrant-indexer`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-008-qdrant-indexer`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/indexer.py` | Implement Qdrant client, collection/index setup, and batch upsert |
| `tests/test_indexer.py` | Add focused unit tests for indexing behavior |
| `Docs/tickets/DEVLOG.md` | Add MVP-008 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 complete)
- `src/ingestion/cobol_parser.py` (MVP-004 complete)
- `src/ingestion/cobol_chunker.py` (MVP-005/006 complete)
- `src/ingestion/embedder.py` unless blocked by contract mismatch
- `src/config.py` unless blocked by missing constants
- Retrieval modules (`src/retrieval/*`) for this ticket
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/chunks.py` | `Chunk` and `EmbeddedChunk` contracts |
| `src/config.py` | Qdrant URL/key/collection and embedding dimension constants |
| `src/ingestion/embedder.py` | Upstream contract and deterministic `chunk_id` assumptions |
| `src/ingestion/cobol_chunker.py` | Payload metadata shape (`paragraph_name`, `division`, etc.) |
| `requirements.txt` | `qdrant-client` dependency availability |
| `.cursor/rules/rag-pipeline.mdc` | Qdrant collection/index constraints |
| `.cursor/rules/multi-codebase.mdc` | Shared-collection metadata filtering constraints |
| `.cursor/rules/tdd.mdc` | Test-first workflow requirements |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - Qdrant storage constraints
- `.cursor/rules/tech-stack.mdc` - `qdrant-client` requirement
- `.cursor/rules/multi-codebase.mdc` - shared-collection behavior

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def index_chunks(
    embedded_chunks: list[EmbeddedChunk],
    collection_name: str = QDRANT_COLLECTION_NAME,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> int:
```

### Processing Flow

```python
def index_chunks(embedded_chunks, collection_name=QDRANT_COLLECTION_NAME, batch_size=EMBEDDING_BATCH_SIZE):
    if not embedded_chunks:
        return 0

    client = _build_qdrant_client()
    _ensure_collection(client, collection_name)
    _ensure_payload_indexes(client, collection_name)

    points = [_build_point(item) for item in embedded_chunks]

    for batch in _batched(points, batch_size):
        _upsert_batch(client, collection_name, batch)

    return len(points)
```

Suggested helper responsibilities:

- `_build_qdrant_client() -> QdrantClient`
- `_collection_exists(client: QdrantClient, collection_name: str) -> bool`
- `_ensure_collection(client: QdrantClient, collection_name: str) -> None`
- `_ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None`
- `_validate_embedding(embedding: list[float]) -> None`
- `_build_payload(embedded_chunk: EmbeddedChunk) -> dict[str, str | int | list[str]]`
- `_build_point(embedded_chunk: EmbeddedChunk) -> PointStruct`
- `_batched[T](items: list[T], size: int) -> list[list[T]]`
- `_upsert_batch(client: QdrantClient, collection_name: str, points: list[PointStruct]) -> None`

### Payload Strategy

Payload should keep retrieval/citation fields together in one record:

```python
{
    "content": chunk.content,
    "file_path": chunk.file_path,
    "line_start": chunk.line_start,
    "line_end": chunk.line_end,
    "paragraph_name": chunk.metadata.get("paragraph_name", chunk.name),
    "division": chunk.division,
    "chunk_type": chunk.chunk_type,
    "language": chunk.language,
    "codebase": chunk.codebase,
    "dependencies": chunk.dependencies,
}
```

### Collection / Index Strategy

- Collection name: `QDRANT_COLLECTION_NAME`
- Vector params: `size=EMBEDDING_DIMENSIONS`, `distance=COSINE`
- Required payload indexes:
  - `paragraph_name`
  - `division`
  - `file_path`
  - `language`
  - `codebase`

Create these idempotently so re-runs are safe.

---

## Edge Cases to Handle

1. **Empty input list:** Return `0`, no Qdrant calls
2. **Missing Qdrant URL:** Fail clearly with actionable configuration error
3. **Existing collection:** Do not recreate; continue safely
4. **Index already exists:** No fatal error on repeated setup
5. **Dimension mismatch:** Raise explicit error with expected vs actual size
6. **Duplicate `chunk_id`:** Deterministic upsert behavior (update/replace same point ID)
7. **Final partial batch:** Correctly process non-multiple batch sizes
8. **Qdrant API/network errors:** Propagate typed failure (do not swallow)
9. **Missing metadata key:** Fallback deterministically from `Chunk` fields where possible

---

## Test Fixture Suggestions

```python
@pytest.fixture
def sample_embedded_chunks() -> list[EmbeddedChunk]:
    chunk = Chunk(
        content="MAIN-LOGIC.\n    PERFORM INIT-DATA.",
        file_path="data/raw/gnucobol/sample.cob",
        line_start=10,
        line_end=11,
        chunk_type="paragraph",
        language="cobol",
        codebase="gnucobol",
        name="MAIN-LOGIC",
        division="PROCEDURE",
        dependencies=["INIT-DATA"],
        token_count=18,
        metadata={"paragraph_name": "MAIN-LOGIC"},
    )
    return [
        EmbeddedChunk(
            chunk=chunk,
            embedding=[0.01] * 1536,
            chunk_id="gnucobol:data/raw/gnucobol/sample.cob:10",
        )
    ]
```

Mocking guidance:

- Use a fake `QdrantClient` in tests
- Track calls to:
  - `get_collection`
  - `create_collection`
  - `create_payload_index`
  - `upsert`
- Simulate "collection missing" on first lookup
- Simulate API failure for error-path tests

Core assertions:

- output count equals number of input embedded chunks
- collection uses `EMBEDDING_DIMENSIONS` and cosine distance
- payload indexes include required fields
- point `id` equals `EmbeddedChunk.chunk_id`
- payload includes citation/retrieval fields
- batch splitting follows configured batch size
- no network access in unit tests (all mocked)

---

## Definition of Done for MVP-008

- [ ] `src/ingestion/indexer.py` implemented with `index_chunks()` and helper logic
- [ ] Qdrant collection setup is idempotent and dimension-correct
- [ ] Required payload indexes created for retrieval filters
- [ ] Upserts run in batches with deterministic point IDs
- [ ] Payload schema includes retrieval/citation-critical fields
- [ ] Unit tests added and passing in `tests/test_indexer.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-008 entry
- [ ] Work completed on `feature/mvp-008-qdrant-indexer` and merged via PR

---

## Estimated Time: 60-90 minutes

| Task | Estimate |
|------|----------|
| Review contracts + Qdrant constraints | 10-15 min |
| Write failing indexer tests | 20-25 min |
| Implement collection/index/upsert logic | 20-25 min |
| Handle edge cases + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-008: What Comes Next

- **MVP-009:** Hybrid retrieval (dense + BM25) over indexed vectors
- **MVP-010:** Metadata re-ranking and confidence scoring

MVP-008 should leave the ingestion pipeline with durable, query-ready vector storage so retrieval can be implemented without changing embedding/index contracts.

