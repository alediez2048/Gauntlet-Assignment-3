# MVP-006 Primer: Metadata Extraction

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-005 (COBOL paragraph chunker) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-006 implements **metadata extraction** for COBOL chunks so retrieval, filtering, and citation quality work correctly downstream.

In MVP-005, chunk boundaries are created. In MVP-006, each chunk must be enriched with complete, consistent metadata fields required by the pipeline:

- `file_path`
- `line_start`
- `line_end`
- `paragraph_name`
- `division`
- `chunk_type`
- `language`
- `codebase`
- `dependencies`

### Why It Matters

- **Retrieval quality:** Metadata fields are used for filtering and ranking (`codebase`, `language`, `division`, paragraph identity).
- **Answer quality:** The generator needs reliable line ranges and identifiers for source citations.
- **Feature correctness:** Dependency Mapping and Impact Analysis rely on extracted `PERFORM`, `CALL`, and `COPY` targets.
- **Qdrant indexing readiness:** Payload fields must be stable before embedding/indexing starts in MVP-007 and MVP-008.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005 chunking logic should exist (`src/ingestion/cobol_chunker.py`)
- Dataclasses already exist in `src/types/chunks.py`:
  - `ProcessedFile`
  - `Chunk`
- Chunk constants already exist in `src/config.py` (`CHUNK_MIN_TOKENS`, `CHUNK_MAX_TOKENS`)
- Rules define required metadata schema and multi-codebase constraints

---

## Metadata Schema (Critical Reference)

From project rules and PRD requirements, every chunk must expose these metadata values:

```python
{
    "file_path": str,
    "line_start": int,
    "line_end": int,
    "paragraph_name": str,
    "division": str,
    "chunk_type": str,
    "language": str,
    "codebase": str,
    "dependencies": list[str],
}
```

In this codebase:

- `Chunk.name` maps to paragraph identity
- `Chunk.metadata["paragraph_name"]` should be populated for payload parity
- `Chunk.dependencies` stores extracted targets

---

## What MVP-006 Must Accomplish

### Goal

Enrich COBOL chunks with complete, validated metadata and dependency extraction so output from ingestion is ready for embedding and retrieval.

### Deliverables Checklist

#### A. Metadata Extraction Logic (`src/ingestion/cobol_chunker.py`)

- [ ] Ensure every returned `Chunk` has:
  - `file_path`, `line_start`, `line_end`, `chunk_type`, `language`, `codebase`
  - `name` set to paragraph name (or deterministic merged name strategy)
  - `division` populated (typically `PROCEDURE` for paragraph chunks)
  - `dependencies` populated from parsed statements
  - `token_count` already set and preserved
- [ ] Populate `chunk.metadata` with schema-compatible keys:
  - `paragraph_name` (mirror of `Chunk.name`)
  - `division`, `file_path`, `line_start`, `line_end`, `chunk_type`, `language`, `codebase`
- [ ] Add dependency extraction for COBOL patterns:
  - `PERFORM paragraph-name`
  - `PERFORM paragraph-name THRU paragraph-name`
  - `CALL "program-name"`
  - `COPY copybook-name`
- [ ] Normalize dependencies:
  - trim punctuation
  - deduplicate while preserving encounter order
  - keep source case or normalize consistently (document the choice)
- [ ] Keep logic pure ingestion-only:
  - no network calls
  - no Qdrant calls
  - no embedding calls

#### B. Unit Tests (`tests/test_cobol_chunker.py`)

- [ ] TDD first: add tests before implementation updates
- [ ] Test required metadata field presence on each chunk
- [ ] Test paragraph name mapping:
  - `Chunk.name` is non-empty for normal paragraph chunks
  - `metadata["paragraph_name"]` equals `Chunk.name`
- [ ] Test line metadata:
  - `line_start >= 1`
  - `line_end >= line_start`
  - line ranges correspond to chunk content boundaries
- [ ] Test division extraction:
  - Paragraph chunks in `PROCEDURE DIVISION` report `division="PROCEDURE"`
  - Non-procedure fallback behavior is deterministic
- [ ] Test dependency extraction:
  - `PERFORM` target parsed
  - `PERFORM ... THRU ...` range captured
  - `CALL "FOO"` parsed as dependency
  - `COPY BOOK1` parsed as dependency
- [ ] Test normalization:
  - duplicate dependencies not repeated
  - trailing period/quotes cleaned as intended
- [ ] Test edge cases:
  - chunk with no dependencies returns empty list
  - empty/noisy statements do not crash parsing
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Metadata extraction integrates with MVP-005 chunk output without changing chunk boundary behavior
- [ ] Output remains `list[Chunk]` and stays compatible with MVP-007 embedding input
- [ ] Works with both `.cob/.cbl` program files and `.cpy` copybooks (fallback behavior documented)

#### D. Documentation

- [ ] Add MVP-006 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document dependency parsing rules and normalization assumptions
- [ ] Record any new helper signatures introduced in `cobol_chunker.py`

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-006-metadata-extraction`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-006-metadata-extraction`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/cobol_chunker.py` | Add metadata enrichment + dependency extraction logic |
| `tests/test_cobol_chunker.py` | Add tests for metadata schema and dependency parsing |
| `Docs/tickets/DEVLOG.md` | Add MVP-006 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 complete)
- `src/ingestion/cobol_parser.py` (MVP-004 complete)
- `src/ingestion/fortran_parser.py` (G4-001)
- `src/ingestion/fortran_chunker.py` (G4-002)
- `src/config.py` unless blocked by missing constant
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/chunks.py` | `Chunk` contract fields and defaults |
| `src/ingestion/cobol_chunker.py` | Existing chunk construction flow from MVP-005 |
| `.claude/skills/legacylens-ingestion/references/cobol-format.md` | Dependency patterns (`PERFORM`, `CALL`, `COPY`) |
| `.cursor/rules/code-patterns.mdc` | Metadata schema constraints |
| `.cursor/rules/multi-codebase.mdc` | Required `language` and `codebase` behavior |

### Cursor Rules to Follow

- `.cursor/rules/code-patterns.mdc` - chunk metadata schema requirements
- `.cursor/rules/rag-pipeline.mdc` - chunking/retrieval architecture constraints
- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/multi-codebase.mdc` - consistent `codebase` and `language` metadata

---

## Suggested Implementation Pattern

### Main Public Contract (unchanged)

Keep `chunk_cobol(...) -> list[Chunk]` as the external contract.

Add helper functions for metadata enrichment, for example:

```python
def _extract_dependencies(chunk_text: str) -> list[str]:
    ...

def _build_chunk_metadata(chunk: Chunk) -> dict[str, str]:
    ...

def _enrich_chunk_metadata(chunk: Chunk) -> Chunk:
    ...
```

### Processing Flow

```python
def chunk_cobol(processed_file, codebase="gnucobol"):
    chunks = build_chunks_with_boundaries(processed_file, codebase)

    enriched = []
    for chunk in chunks:
        chunk.dependencies = _extract_dependencies(chunk.content)
        chunk.metadata = _build_chunk_metadata(chunk)
        enriched.append(chunk)

    return enriched
```

### Dependency Extraction Heuristics

Use simple regex-first parsing with deterministic output:

- `PERFORM\s+([A-Z0-9-]+)`
- `PERFORM\s+([A-Z0-9-]+)\s+THRU\s+([A-Z0-9-]+)`
- `CALL\s+["']?([A-Z0-9-_]+)["']?`
- `COPY\s+([A-Z0-9-_]+)`

Implementation notes:

- run case-insensitive matching
- preserve original lexical value or uppercase consistently
- avoid false positives in comments (MVP-004 already strips comments from code)

---

## Edge Cases to Handle

1. **Merged chunks (multiple paragraphs):** decide deterministic `paragraph_name` strategy and keep it stable
2. **No dependency statements:** return empty list, not `None`
3. **Duplicate references:** dedupe while preserving first-seen order
4. **Quoted/unquoted CALL target:** parse both forms
5. **PERFORM THRU range:** either keep as `A THRU B` single dependency or two entries; document in tests
6. **COPY with trailing period:** strip period cleanly
7. **Fallback chunks outside PROCEDURE DIVISION:** `division` should still be non-empty and deterministic

---

## Test Fixture Suggestions

```python
@pytest.fixture
def metadata_rich_processed_file() -> ProcessedFile:
    return ProcessedFile(
        code=(
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. TEST.\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-LOGIC.\n"
            "    PERFORM INIT-DATA.\n"
            "    CALL \"RATE-SVC\".\n"
            "    COPY CUSTCOPY.\n"
            "    STOP RUN.\n"
            "INIT-DATA.\n"
            "    MOVE 1 TO WS-COUNT.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/sample.cob",
        encoding="utf-8",
    )
```

Core assertions:

- each chunk has required fields populated
- `metadata["paragraph_name"] == chunk.name`
- dependencies include expected targets
- dependencies contain no duplicates
- line range and division values are valid

---

## Definition of Done for MVP-006

- [ ] Metadata extraction is implemented and integrated in `src/ingestion/cobol_chunker.py`
- [ ] Each chunk has required schema fields populated and consistent
- [ ] Dependency extraction works for `PERFORM`, `PERFORM THRU`, `CALL`, and `COPY`
- [ ] Metadata dictionary contains retrieval-ready payload keys (including `paragraph_name`)
- [ ] Unit tests added and passing in `tests/test_cobol_chunker.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-006 entry
- [ ] Work completed on `feature/mvp-006-metadata-extraction` and merged via PR

---

## Estimated Time: 45-75 minutes

| Task | Estimate |
|------|----------|
| Review MVP-005 chunk output shape | 10 min |
| Write failing metadata/dependency tests | 20 min |
| Implement metadata enrichment helpers | 20 min |
| Handle dependency edge cases + test fixes | 10-15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-006: What Comes Next

- **MVP-007:** Batch embedding module (Voyage Code 2, batch size 128, 1536 dims)
- **MVP-008:** Qdrant indexer with payload indexes on metadata fields

MVP-006 should leave chunk outputs metadata-complete and dependency-aware so embedding and retrieval stages can be implemented without changing ingestion contracts.

