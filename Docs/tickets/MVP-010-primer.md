# MVP-010 Primer: Metadata-Based Re-ranker

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-009 (hybrid search module) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-010 implements the **metadata-based reranker** that refines hybrid retrieval output using structural code metadata and assigns confidence levels.

In MVP-009, retrieval returns ranked chunks from dense + BM25 search. In MVP-010, those candidate chunks must be reranked with metadata signals (paragraph names, division intent, file and dependency hints), confidence must be normalized to `HIGH/MEDIUM/LOW`, and output order must be deterministic.

### Why It Matters

- **Precision lift:** Metadata-aware reranking improves top-k relevance without extra embedding cost.
- **Confidence contract:** Downstream API/UI expects stable confidence levels on retrieved context.
- **Legacy code alignment:** COBOL paragraph and division context is a strong ranking signal not captured by raw vector similarity alone.
- **Pipeline sequencing:** MVP-011/MVP-012 generation quality depends on better-ranked context.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- MVP-007 embedding is implemented (`src/ingestion/embedder.py`)
- MVP-008 indexing is implemented (`src/ingestion/indexer.py`)
- MVP-009 hybrid retrieval should be implemented (`src/retrieval/search.py`)
- Output dataclasses already exist in `src/types/responses.py`:
  - `RetrievedChunk`
  - `Confidence`
  - `QueryResponse`
- Feature config already models reranking behavior (`src/types/features.py`):
  - `FeatureConfig.rerank`
- Tech stack already includes `cohere` in `requirements.txt`

---

## Re-ranking Contract (Critical Reference)

MVP-010 should consume retrieved candidates and return a reranked list with confidence labels:

```python
rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    enable_cohere: bool = True,
) -> list[RetrievedChunk]
```

Expected behavior:

- preserve `RetrievedChunk` shape
- update `score` to reranked score
- update `confidence` to `HIGH`, `MEDIUM`, or `LOW`
- keep deterministic ordering for ties

Hard requirements from project rules:

- Retrieval ownership: `src/retrieval/reranker.py`
- Metadata-first reranking is required
- Cohere cross-encoder is second stage when available (with metadata fallback path)
- Confidence output must be `HIGH / MEDIUM / LOW`
- No LangChain, no LlamaIndex

---

## What MVP-010 Must Accomplish

### Goal

Implement a production-ready reranking module in `src/retrieval/reranker.py` that scores metadata relevance, optionally applies Cohere cross-encoder reranking, and returns deterministically ordered `RetrievedChunk` results with normalized confidence levels.

### Deliverables Checklist

#### A. Re-ranking Logic (`src/retrieval/reranker.py`)

- [ ] Create public reranking API:
  - `rerank_chunks(query: str, chunks: list[RetrievedChunk], feature: str = "code_explanation", enable_cohere: bool = True) -> list[RetrievedChunk]`
- [ ] Validate inputs:
  - blank query raises deterministic error
  - empty chunk list returns `[]`
- [ ] Implement metadata-first scoring pass using chunk metadata and query hints:
  - paragraph name boost
  - division routing boost
  - optional codebase/language alignment boost
  - optional dependency overlap boost
- [ ] Apply score normalization to comparable range (for deterministic confidence thresholds)
- [ ] Assign confidence labels (`HIGH`, `MEDIUM`, `LOW`) from normalized scores
- [ ] Implement deterministic sort:
  - score descending
  - stable tie-breakers (e.g., file_path then line_start)
- [ ] Add optional Cohere second-stage reranking:
  - enabled when `enable_cohere=True` and `COHERE_API_KEY` is configured
  - fallback to metadata-only ranking if Cohere is unavailable/fails
  - no silent swallow: preserve typed error context or explicit fallback path
- [ ] Preserve retrieval-only scope:
  - no query embedding logic
  - no hybrid search logic
  - no context assembly logic
  - no generation logic
  - no API route logic

#### B. Unit Tests (`tests/test_retrieval.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test return contract:
  - returns `list[RetrievedChunk]`
  - `score` and `confidence` updated as expected
- [ ] Test validation:
  - blank query raises deterministic error
  - empty chunk list returns `[]`
- [ ] Test metadata boosts:
  - paragraph-name match gets boosted
  - division-aware query boosts matching division chunks
  - non-matching chunks keep baseline score
- [ ] Test confidence mapping:
  - normalized scores map to `HIGH/MEDIUM/LOW` deterministically
- [ ] Test ordering:
  - score-descending output
  - deterministic tie behavior
- [ ] Test Cohere stage behavior:
  - enabled + configured path invoked correctly
  - missing API key triggers metadata-only fallback
  - Cohere error path handled deterministically
- [ ] Test no network access in unit tests (all clients mocked)
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Consumes `list[RetrievedChunk]` output from MVP-009 search module unchanged in shape
- [ ] Returns reranked chunks ready for context assembly and generation modules
- [ ] Confidence values align with UI/API expectations (`HIGH/MEDIUM/LOW`)
- [ ] Compatible with current MVP single-codebase flow and future multi-codebase routing

#### D. Documentation

- [ ] Add MVP-010 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document metadata boost strategy and confidence threshold assumptions
- [ ] Record helper signatures introduced in `reranker.py`
- [ ] Note Cohere fallback behavior and any SDK caveats

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-010-metadata-reranker`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-010-metadata-reranker`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/retrieval/reranker.py` | Implement metadata scoring, confidence normalization, optional Cohere pass |
| `tests/test_retrieval.py` | Add reranker-focused tests (or extend retrieval test classes) |
| `Docs/tickets/DEVLOG.md` | Add MVP-010 completion entry (after done) |

### Files You May Need to Create

| File | Why |
|------|-----|
| `src/retrieval/__init__.py` | Package entry if retrieval package is introduced in this ticket |

### Files You Should NOT Modify

- `src/ingestion/*` modules (MVP-003 through MVP-008 are complete)
- `src/retrieval/search.py` except contract-level compatibility fixes
- `src/retrieval/context.py` (later ticket scope)
- `src/generation/*` (MVP-011/012 scope)
- `src/api/*` (MVP-013 scope)
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/responses.py` | `RetrievedChunk` + `Confidence` contracts |
| `src/types/features.py` | feature-level `rerank` config expectation |
| `src/config.py` | env constants and top-k defaults |
| `src/retrieval/search.py` | upstream result shape from hybrid retrieval |
| `src/ingestion/indexer.py` | payload fields available for metadata boosts |
| `requirements.txt` | `cohere` dependency availability |
| `.cursor/rules/rag-pipeline.mdc` | layered reranking architecture constraints |
| `.cursor/rules/tdd.mdc` | test-first workflow requirements |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - layered reranking + confidence contract
- `.cursor/rules/tech-stack.mdc` - Cohere rerank API requirement
- `.cursor/rules/multi-codebase.mdc` - preserve metadata-driven cross-codebase behavior

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    enable_cohere: bool = True,
) -> list[RetrievedChunk]:
```

### Processing Flow

```python
def rerank_chunks(query, chunks, feature="code_explanation", enable_cohere=True):
    _validate_inputs(query=query, chunks=chunks)
    if not chunks:
        return []

    metadata_scored = _apply_metadata_rerank(query=query, chunks=chunks, feature=feature)
    metadata_normalized = _normalize_scores(metadata_scored)

    if enable_cohere and _cohere_enabled():
        metadata_normalized = _apply_cohere_rerank(
            query=query,
            chunks=metadata_normalized,
        )

    with_confidence = _assign_confidence(metadata_normalized)
    return _sort_chunks_deterministically(with_confidence)
```

Suggested helper responsibilities:

- `_validate_inputs(query: str, chunks: list[RetrievedChunk]) -> None`
- `_tokenize_query(query: str) -> set[str]`
- `_metadata_boost_for_chunk(query_tokens: set[str], chunk: RetrievedChunk) -> float`
- `_apply_metadata_rerank(...) -> list[RetrievedChunk]`
- `_normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]`
- `_build_cohere_client() -> cohere.ClientV2`
- `_apply_cohere_rerank(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]`
- `_confidence_from_score(score: float) -> Confidence`
- `_assign_confidence(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]`
- `_sort_chunks_deterministically(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]`

### Metadata Scoring Strategy

Keep metadata reranking deterministic and explainable:

- base score starts from upstream `chunk.score`
- add bounded boosts, for example:
  - paragraph-name exact token match: `+0.20`
  - division hint match (`PROCEDURE`, `DATA`, etc.): `+0.10`
  - file-path token overlap: `+0.05`
  - dependency token overlap: `+0.05`
- cap total metadata boost to avoid runaway ranking (for example `<= +0.30`)

The exact values can be tuned, but behavior must be deterministic and covered by tests.

### Confidence Normalization Strategy

Normalize to a stable range (for example, min-max across current candidate set), then map:

- `HIGH` if normalized score >= `0.75`
- `MEDIUM` if normalized score >= `0.45` and < `0.75`
- `LOW` otherwise

If all scores are equal, apply deterministic fallback normalization (for example all `0.5`) so confidence mapping remains stable.

### Cohere Second-Stage Strategy

Use metadata-first output as the input set for optional cross-encoder reranking:

- if `COHERE_API_KEY` missing -> skip Cohere and keep metadata ranking
- if Cohere call fails -> deterministic fallback to metadata ranking
- when Cohere succeeds:
  - blend Cohere relevance with metadata score (document blend rule)
  - preserve stable ordering ties with deterministic keys

Avoid adding hard dependencies on network in unit tests; mock all Cohere interactions.

---

## Edge Cases to Handle

1. **Empty chunk list:** Return `[]`, no scoring calls
2. **Blank query:** Raise deterministic validation error
3. **Missing metadata fields:** Fallback safely without KeyError
4. **Equal scores across all chunks:** Deterministic normalization fallback
5. **Tie scores after rerank:** Stable sort with deterministic tie-breakers
6. **Missing `COHERE_API_KEY`:** Metadata-only fallback (typed/explicit)
7. **Cohere API failure:** Metadata-only fallback without losing result ordering
8. **Very short identifier query:** Paragraph-name boosts still applied correctly
9. **Cross-codebase result mix:** Metadata boosts must not break ranking determinism

---

## Test Fixture Suggestions

```python
@pytest.fixture
def sample_retrieved_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            content="MAIN-LOGIC. PERFORM INIT-DATA.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=10,
            line_end=11,
            name="MAIN-LOGIC",
            language="cobol",
            codebase="gnucobol",
            score=0.62,
            metadata={"paragraph_name": "MAIN-LOGIC", "division": "PROCEDURE"},
        ),
        RetrievedChunk(
            content="INIT-DATA. MOVE 1 TO WS-COUNT.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=20,
            line_end=21,
            name="INIT-DATA",
            language="cobol",
            codebase="gnucobol",
            score=0.60,
            metadata={"paragraph_name": "INIT-DATA", "division": "PROCEDURE"},
        ),
    ]
```

Mocking guidance:

- Use fake input chunks with controlled `score` and metadata
- Use fake Cohere client returning deterministic rerank scores
- Track whether Cohere path was called when enabled/disabled
- Keep tests fully offline (no network calls)

Core assertions:

- metadata boosts change ranking in expected direction
- confidence mapping is deterministic
- tie ordering is stable
- fallback behavior works when Cohere is unavailable
- output remains `list[RetrievedChunk]` with valid fields

---

## Definition of Done for MVP-010

- [ ] `src/retrieval/reranker.py` implemented with `rerank_chunks()` and helper logic
- [ ] Metadata-first reranking active with deterministic scoring and ordering
- [ ] Confidence normalization maps to `HIGH/MEDIUM/LOW` consistently
- [ ] Optional Cohere second-stage path implemented with deterministic fallback
- [ ] Unit tests added and passing in `tests/test_retrieval.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-010 entry
- [ ] Work completed on `feature/mvp-010-metadata-reranker` and merged via PR

---

## Estimated Time: 45-75 minutes

| Task | Estimate |
|------|----------|
| Review MVP-009 output contract + rerank constraints | 10-15 min |
| Write failing reranker/confidence tests | 20-25 min |
| Implement metadata scoring + confidence mapping | 15-20 min |
| Add Cohere fallback path + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-010: What Comes Next

- **MVP-011:** COBOL-aware prompt template with citation instructions
- **MVP-012:** LLM generation module (GPT-4o + fallback)

MVP-010 should leave retrieval outputs consistently prioritized and confidence-labeled so generation receives cleaner, more reliable context without changing search contracts.

