# MVP-009 Primer: Hybrid Search Module

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-008 (Qdrant indexer module) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-009 implements the **hybrid retrieval module** that combines dense semantic similarity with sparse/BM25 lexical matching.

In MVP-008, embedded chunks are indexed in Qdrant with retrieval-ready payload metadata. In MVP-009, user queries must be embedded, searched across both retrieval channels, fused deterministically, and returned as `RetrievedChunk` results for reranking in MVP-010.

### Why It Matters

- **Search quality foundation:** Dense vectors capture semantic meaning, while BM25 catches exact identifiers and legacy naming patterns.
- **Feature quality:** Every downstream feature depends on accurate top-k retrieval.
- **Pipeline sequencing:** MVP-010 reranking and MVP-013 query API both depend on a stable retrieval contract from this module.
- **Legacy code reality:** COBOL identifiers (for example, `CALCULATE-INTEREST`) often require lexical matching that dense-only retrieval misses.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- MVP-007 embedding is implemented (`src/ingestion/embedder.py`)
- MVP-008 indexing is implemented (`src/ingestion/indexer.py`)
- Qdrant payload indexes already exist for retrieval filters:
  - `paragraph_name`
  - `division`
  - `file_path`
  - `language`
  - `codebase`
- Response dataclasses already exist in `src/types/responses.py`:
  - `RetrievedChunk`
  - `Confidence`
  - `QueryResponse`
- Retrieval constants already exist in `src/config.py`:
  - `DEFAULT_TOP_K`
  - `QDRANT_COLLECTION_NAME`
  - `QDRANT_URL`
  - `QDRANT_API_KEY`
  - `EMBEDDING_MODEL`
  - `VOYAGE_API_KEY`
- `requirements.txt` already includes `qdrant-client` and `voyageai`

---

## Hybrid Retrieval Contract (Critical Reference)

MVP-009 should provide a stable public retrieval API that returns ranked `RetrievedChunk` values:

```python
hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    codebase: str | None = None,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> list[RetrievedChunk]
```

Expected output shape per result:

```python
RetrievedChunk(
    content=str,
    file_path=str,
    line_start=int,
    line_end=int,
    name=str,
    language=str,
    codebase=str,
    score=float,
    confidence=Confidence.HIGH | MEDIUM | LOW,
    metadata={...},
)
```

Hard requirements from project rules:

- Retrieval module ownership: `src/retrieval/search.py`
- Hybrid retrieval must use Qdrant-native dense + sparse/BM25 channels
- Query-adaptive weighting:
  - identifier-heavy query -> **0.6 BM25**, **0.4 dense**
  - semantic/natural-language query -> **0.7 dense**, **0.3 BM25**
- Respect shared collection strategy (`QDRANT_COLLECTION_NAME`)
- Respect metadata filtering via payload (`codebase`, `language`, etc.)
- No LangChain, no LlamaIndex

---

## What MVP-009 Must Accomplish

### Goal

Implement a production-ready hybrid retrieval module in `src/retrieval/search.py` that runs dense + BM25 search via Qdrant, applies deterministic fusion with adaptive weighting, and returns typed `RetrievedChunk` outputs.

### Deliverables Checklist

#### A. Retrieval Logic (`src/retrieval/search.py`)

- [ ] Create public retrieval API:
  - `hybrid_search(query: str, top_k: int = DEFAULT_TOP_K, codebase: str | None = None, collection_name: str = QDRANT_COLLECTION_NAME) -> list[RetrievedChunk]`
- [ ] Build Qdrant client from config (`QDRANT_URL`, `QDRANT_API_KEY`)
- [ ] Build Voyage client for query embedding from config (`VOYAGE_API_KEY`)
- [ ] Embed query with `input_type="query"` (not `document`)
- [ ] Run dense retrieval channel from query embedding
- [ ] Run sparse/BM25 retrieval channel through Qdrant-native search capability
- [ ] Fuse channel results with deterministic adaptive weights:
  - identifier query -> BM25-heavy
  - semantic query -> dense-heavy
- [ ] Apply optional `codebase` filter using Qdrant payload filter
- [ ] Return top-k ranked `RetrievedChunk` outputs
- [ ] Map Qdrant payload to `RetrievedChunk` fields with deterministic fallbacks
- [ ] Validate arguments:
  - non-empty query
  - `top_k > 0`
- [ ] Handle empty result sets safely (`[]`)
- [ ] Use typed exceptions (no bare `except`)
- [ ] Keep module retrieval-only:
  - no reranker logic (MVP-010)
  - no context assembly logic
  - no generation logic
  - no API route logic

#### B. Unit Tests (`tests/test_retrieval.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test return contract:
  - returns `list[RetrievedChunk]`
  - fields are correctly mapped from payload
- [ ] Test validation:
  - blank query raises deterministic error
  - `top_k <= 0` raises deterministic error
- [ ] Test codebase filtering:
  - no filter -> query all
  - filter provided -> query filter includes `codebase`
- [ ] Test adaptive weighting:
  - identifier-like query selects BM25-heavy weights
  - semantic query selects dense-heavy weights
- [ ] Test fusion behavior:
  - duplicate chunk IDs across channels are deduped deterministically
  - final ranking is score-descending and deterministic
- [ ] Test top-k limiting:
  - returns at most `top_k` results
- [ ] Test no-result behavior:
  - both channels empty -> returns `[]`
- [ ] Test config failure behavior:
  - missing `QDRANT_URL` raises actionable error
  - missing `VOYAGE_API_KEY` raises actionable error
- [ ] Test Qdrant failures surface as typed retrieval errors
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Consumes payload schema written by MVP-008 indexer (`content`, `file_path`, lines, metadata fields)
- [ ] Works against shared collection (`QDRANT_COLLECTION_NAME`)
- [ ] Compatible with upcoming reranker contract in MVP-010
- [ ] Supports current single-codebase MVP while preserving multi-codebase filter contract
- [ ] No network access in unit tests (all retrieval clients mocked)

#### D. Documentation

- [ ] Add MVP-009 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document query-type heuristic and weighting assumptions
- [ ] Record helper signatures introduced in `search.py`
- [ ] Note any SDK-specific caveats around sparse/BM25 channel usage

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-009-hybrid-search`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-009-hybrid-search`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/retrieval/search.py` | Implement hybrid search, filtering, score fusion, and result mapping |
| `tests/test_retrieval.py` | Add focused unit tests for retrieval behavior |
| `Docs/tickets/DEVLOG.md` | Add MVP-009 completion entry (after done) |

### Files You May Need to Create

| File | Why |
|------|-----|
| `src/retrieval/__init__.py` | Package entry if `src/retrieval/` is created in this ticket |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 complete)
- `src/ingestion/cobol_parser.py` (MVP-004 complete)
- `src/ingestion/cobol_chunker.py` (MVP-005/006 complete)
- `src/ingestion/embedder.py` unless blocked by contract mismatch
- `src/ingestion/indexer.py` unless blocked by hard incompatibility
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/retrieval/context.py` (later scope)
- Generation modules (`src/generation/*`) for this ticket
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/responses.py` | `RetrievedChunk` output contract |
| `src/config.py` | retrieval constants and environment config |
| `src/ingestion/indexer.py` | exact payload schema currently stored in Qdrant |
| `src/ingestion/embedder.py` | query embedding client/retry style references |
| `requirements.txt` | dependency availability (`qdrant-client`, `voyageai`) |
| `.cursor/rules/rag-pipeline.mdc` | hybrid retrieval and weighting constraints |
| `.cursor/rules/multi-codebase.mdc` | codebase filtering expectations |
| `.cursor/rules/tdd.mdc` | test-first workflow requirements |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - hybrid retrieval architecture constraints
- `.cursor/rules/tech-stack.mdc` - Qdrant + Voyage + strict stack requirements
- `.cursor/rules/multi-codebase.mdc` - shared collection and filter behavior

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    codebase: str | None = None,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> list[RetrievedChunk]:
```

### Processing Flow

```python
def hybrid_search(query, top_k=DEFAULT_TOP_K, codebase=None, collection_name=QDRANT_COLLECTION_NAME):
    _validate_query_inputs(query, top_k)

    qdrant = _build_qdrant_client()
    voyage = _build_voyage_client()

    dense_vector = _embed_query(voyage, query)
    query_filter = _build_query_filter(codebase=codebase)

    dense_hits = _search_dense(
        client=qdrant,
        collection_name=collection_name,
        query_vector=dense_vector,
        query_filter=query_filter,
        limit=_channel_limit(top_k),
    )
    sparse_hits = _search_sparse_bm25(
        client=qdrant,
        collection_name=collection_name,
        query_text=query,
        query_filter=query_filter,
        limit=_channel_limit(top_k),
    )

    dense_weight, sparse_weight = _select_channel_weights(query)
    fused_hits = _fuse_channel_results(
        dense_hits=dense_hits,
        sparse_hits=sparse_hits,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        top_k=top_k,
    )

    return [_to_retrieved_chunk(hit) for hit in fused_hits]
```

Suggested helper responsibilities:

- `_validate_query_inputs(query: str, top_k: int) -> None`
- `_build_qdrant_client() -> QdrantClient`
- `_build_voyage_client() -> voyageai.Client`
- `_embed_query(client: voyageai.Client, query: str) -> list[float]`
- `_build_query_filter(codebase: str | None) -> Filter | None`
- `_is_identifier_query(query: str) -> bool`
- `_select_channel_weights(query: str) -> tuple[float, float]`
- `_search_dense(...) -> list[ScoredPoint]`
- `_search_sparse_bm25(...) -> list[ScoredPoint]`
- `_fuse_channel_results(...) -> list[ScoredPoint]`
- `_to_retrieved_chunk(point: ScoredPoint) -> RetrievedChunk`

### Query-Type Heuristic

Use a deterministic lexical heuristic for weight selection:

- treat query as **identifier-heavy** when one or more of these are true:
  - contains COBOL/legacy token patterns (`[A-Z0-9-]{4,}`)
  - contains underscores, hyphens, or exact symbol-like tokens
  - short query with mostly identifier tokens
- otherwise treat as **semantic/natural-language**

Weight selection target:

- identifier-heavy: `(dense=0.4, sparse=0.6)`
- semantic: `(dense=0.7, sparse=0.3)`

### Metadata Filter Strategy

Use payload filters so MVP and multi-codebase behavior share one path:

```python
if codebase is None:
    return None

return Filter(
    must=[
        FieldCondition(
            key="codebase",
            match=MatchValue(value=codebase),
        )
    ]
)
```

### Score Fusion Strategy

Prefer deterministic weighted fusion over implicit ordering:

- normalize channel scores to a comparable range per request
- combine by point ID:
  - `fused = (dense_norm * dense_weight) + (sparse_norm * sparse_weight)`
- dedupe by point ID (keep max fused score)
- stable tiebreakers:
  1. higher fused score
  2. higher dense score
  3. lexical point ID (or first-seen order)

If weighted native fusion in your Qdrant SDK path is unavailable, do **two Qdrant-native channel queries** and perform only the fusion arithmetic in Python. Do not implement your own BM25 engine.

---

## Edge Cases to Handle

1. **Blank query string:** Raise actionable validation error
2. **Non-positive `top_k`:** Raise deterministic validation error
3. **No retrieval hits:** Return `[]`, no downstream crash
4. **One channel empty:** Use available channel scores without failure
5. **Duplicate IDs across channels:** Deduplicate deterministically
6. **Missing payload fields:** Fallback from defaults without KeyError
7. **Unknown codebase filter:** Deterministic error or explicit empty-result behavior (document in tests)
8. **Qdrant timeout/network errors:** Surface as typed retrieval failure
9. **Voyage query embedding failure:** Surface as typed retrieval failure
10. **Very short identifier query:** Ensure BM25-heavy route is still selected

---

## Test Fixture Suggestions

```python
@pytest.fixture
def sample_dense_hit() -> object:
    return _FakeScoredPoint(
        point_id="gnucobol:data/raw/gnucobol/sample.cob:10",
        score=0.82,
        payload={
            "content": "MAIN-LOGIC. PERFORM INIT-DATA.",
            "file_path": "data/raw/gnucobol/sample.cob",
            "line_start": 10,
            "line_end": 11,
            "name": "MAIN-LOGIC",
            "paragraph_name": "MAIN-LOGIC",
            "division": "PROCEDURE",
            "chunk_type": "paragraph",
            "language": "cobol",
            "codebase": "gnucobol",
            "dependencies": ["INIT-DATA"],
        },
    )
```

Mocking guidance:

- Use fake Qdrant client with separate dense and sparse call tracking
- Use fake Voyage client for deterministic query vectors
- Stub query-type heuristic directly in some tests to isolate fusion logic
- Keep tests offline (no real Qdrant Cloud or Voyage calls)

Core assertions:

- output is `list[RetrievedChunk]`
- result fields map correctly from payload
- adaptive weights selected for query type
- `codebase` filter is propagated to Qdrant query filter
- final ordering and top-k truncation are deterministic
- retrieval errors are typed and actionable

---

## Definition of Done for MVP-009

- [ ] `src/retrieval/search.py` implemented with `hybrid_search()` and helper logic
- [ ] Dense + BM25 retrieval channels run through Qdrant-native search paths
- [ ] Query-adaptive weighting implemented (identifier BM25-heavy, semantic dense-heavy)
- [ ] Optional `codebase` filter applied via payload metadata filtering
- [ ] Results returned as `list[RetrievedChunk]` with correct field mapping
- [ ] Unit tests added and passing in `tests/test_retrieval.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-009 entry
- [ ] Work completed on `feature/mvp-009-hybrid-search` and merged via PR

---

## Estimated Time: 60-90 minutes

| Task | Estimate |
|------|----------|
| Review payload schema + retrieval constraints | 10-15 min |
| Write failing hybrid retrieval tests | 20-25 min |
| Implement search/filter/fusion logic | 20-25 min |
| Handle edge cases + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-009: What Comes Next

- **MVP-010:** Metadata-based reranking and confidence scoring
- **MVP-011:** COBOL-aware prompt template for citation-grounded generation

MVP-009 should leave the retrieval layer returning stable, high-signal candidate chunks so reranking and generation can be implemented without changing retrieval contracts.

