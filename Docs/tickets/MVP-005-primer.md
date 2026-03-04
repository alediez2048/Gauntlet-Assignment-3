# MVP-005 Primer: COBOL Paragraph Chunker

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-004 (COBOL preprocessor) complete and merged. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-005 implements the **COBOL paragraph chunker** - the module that takes a preprocessed COBOL file (`ProcessedFile`) and produces chunk objects (`Chunk`) on paragraph boundaries.

This chunker must:

1. Detect COBOL paragraph boundaries in `PROCEDURE DIVISION`
2. Build chunks that respect paragraph structure
3. Enforce adaptive chunk sizes (64-768 tokens)
4. Merge small chunks and split oversized chunks safely
5. Return `Chunk` dataclasses ready for embedding in MVP-007

### Why It Matters

- **Retrieval precision depends on boundaries:** Paragraph-level chunks align with COBOL control flow and business logic.
- **Embedding quality:** Chunks that mix unrelated paragraphs reduce semantic relevance in search results.
- **RAG context quality:** Chunk size directly affects recall and answer grounding.
- **Foundation for metadata and retrieval:** MVP-006 and MVP-009 assume stable chunk boundaries and token counts.

---

## What Was Already Done

- `src/ingestion/cobol_parser.py` is implemented and tested (MVP-004)
- `tests/test_cobol_parser.py` has 25 passing tests
- `src/ingestion/cobol_chunker.py` exists as empty placeholder
- `tests/test_cobol_chunker.py` exists as empty placeholder
- `src/types/chunks.py` defines both required dataclasses:
  - `ProcessedFile` (input)
  - `Chunk` (output)
- `src/config.py` already defines chunking constraints:
  - `CHUNK_MIN_TOKENS = 64`
  - `CHUNK_MAX_TOKENS = 768`
  - `TIKTOKEN_ENCODING = "cl100k_base"`
- COBOL paragraph rules are documented in `.claude/skills/legacylens-ingestion/references/cobol-format.md`

---

## COBOL Paragraph Boundary Rules (Critical Reference)

COBOL paragraphs are named blocks inside `PROCEDURE DIVISION`:

```cobol
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           PERFORM INIT-DATA.
           PERFORM PROCESS-RECORDS.
           STOP RUN.
       INIT-DATA.
           MOVE ZEROS TO WS-COUNTER.
       PROCESS-RECORDS.
           READ INPUT-FILE.
```

Detection rules for MVP-005:

- A paragraph name appears in Area A and ends with a period
- `PROCEDURE DIVISION.` is **not** a paragraph
- A paragraph ends at the next paragraph header or file end
- Keep paragraph content together whenever possible
- Split only when a single paragraph exceeds max tokens

---

## What MVP-005 Must Accomplish

### Goal

Replace the empty `src/ingestion/cobol_chunker.py` placeholder with a tested chunker that converts `ProcessedFile` into `list[Chunk]` using paragraph-aware adaptive chunking.

### Deliverables Checklist

#### A. Chunker Module (`src/ingestion/cobol_chunker.py`)

- [ ] Main function:
  - `chunk_cobol(processed_file: ProcessedFile, codebase: str = "gnucobol") -> list[Chunk]`
- [ ] Token counting via `tiktoken` using `cl100k_base` (from config)
- [ ] Paragraph detection:
  - Identify paragraph headers in `PROCEDURE DIVISION`
  - Exclude `PROCEDURE DIVISION.` from paragraph headers
  - Track paragraph start/end line numbers
- [ ] Adaptive size enforcement:
  - If chunk < 64 tokens, merge with adjacent chunk(s)
  - If chunk > 768 tokens, split on sentence/statement boundaries (prefer periods)
  - Avoid splitting mid-statement when possible
- [ ] Chunk output:
  - `content` from detected paragraph block(s)
  - `file_path` from `processed_file.file_path`
  - `line_start`, `line_end` from detected boundaries
  - `chunk_type` = `"paragraph"`
  - `language` = `"cobol"`
  - `codebase` from function arg
  - `name` = paragraph name (or merged paragraph names strategy)
  - `division` = `"PROCEDURE"` when in executable section
  - `token_count` from tokenizer
- [ ] Include safe fallback behavior:
  - If no `PROCEDURE DIVISION`, return structural fallback chunk(s) without crashing
  - Empty input returns empty list

#### B. Unit Tests (`tests/test_cobol_chunker.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test paragraph detection:
  - Finds `MAIN-LOGIC.` / `INIT-DATA.` / etc
  - Does not treat `PROCEDURE DIVISION.` as a paragraph
- [ ] Test chunk boundaries:
  - No split across normal paragraph boundaries
  - `line_start` and `line_end` are consistent and ordered
- [ ] Test adaptive sizing:
  - Two tiny adjacent paragraphs merge (combined >= 64 tokens or minimal chunk set)
  - Oversized paragraph splits into multiple chunks <= 768 tokens
- [ ] Test token accounting:
  - Each chunk has non-zero `token_count`
  - `token_count` reflects content size progression
- [ ] Test metadata and contract:
  - `chunk_type`, `language`, `codebase`, `name`, `file_path` populated
  - Return type is `list[Chunk]`
- [ ] Edge cases:
  - Empty `ProcessedFile`
  - File with no paragraph headers
  - Single paragraph only
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] `chunk_cobol` consumes the real output of `preprocess_cobol`
- [ ] No network calls, no Qdrant calls, no embedding calls
- [ ] Signature is stable for MVP-006 metadata and MVP-007 embedding pipeline
- [ ] Works with code from both `.cob/.cbl` programs and `.cpy` copybooks (fallback behavior acceptable)

#### D. Documentation

- [ ] Add MVP-005 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Record public function signature and chunking strategy assumptions

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-005-cobol-paragraph-chunker`
- Never commit directly to `main` for ticket work.
- Commit in small, meaningful increments with Conventional Commits:
  - `feat:`, `fix:`, `test:`, `docs:`, `refactor:`
- Push branch and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-005-cobol-paragraph-chunker`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/cobol_chunker.py` | Replace placeholder with paragraph chunking logic |
| `tests/test_cobol_chunker.py` | Add unit tests for paragraph detection + adaptive sizing |
| `Docs/tickets/DEVLOG.md` | Add MVP-005 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 complete)
- `src/ingestion/cobol_parser.py` (MVP-004 complete)
- `src/ingestion/fortran_parser.py` (G4-001)
- `src/ingestion/fortran_chunker.py` (G4-002)
- `src/config.py` (already contains chunk size constants)
- Deployment config (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `.claude/skills/legacylens-ingestion/references/cobol-format.md` | Paragraph boundary rules |
| `src/types/chunks.py` | `ProcessedFile` input + `Chunk` output contracts |
| `src/config.py` | `CHUNK_MIN_TOKENS`, `CHUNK_MAX_TOKENS`, tokenizer name |
| `src/ingestion/cobol_parser.py` | Shape and normalization of upstream code text |
| `tests/test_cobol_parser.py` | Patterns for ingestion-layer test style |

### Cursor Rules to Follow

- `.cursor/rules/rag-pipeline.mdc` - adaptive 64-768 token chunking on structural boundaries
- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/multi-codebase.mdc` - metadata must include language + codebase

---

## Suggested Implementation Pattern

### Main Function Signature

```python
def chunk_cobol(
    processed_file: ProcessedFile,
    codebase: str = "gnucobol",
) -> list[Chunk]:
```

### Processing Pipeline

```python
def chunk_cobol(processed_file, codebase="gnucobol"):
    # 1. Fast exits
    if not processed_file.code.strip():
        return []

    # 2. Split into lines and detect paragraph blocks in PROCEDURE DIVISION
    paragraphs = detect_paragraph_blocks(processed_file.code)

    # 3. Convert each paragraph block to preliminary chunks
    raw_chunks = [build_chunk_from_paragraph(p, processed_file, codebase) for p in paragraphs]

    # 4. Enforce adaptive token sizes
    merged = merge_small_chunks(raw_chunks, min_tokens=64)
    final_chunks = split_oversized_chunks(merged, max_tokens=768)

    # 5. Recompute token counts and return
    return normalize_chunks(final_chunks)
```

Suggested helper responsibilities:

- `_detect_paragraph_headers(lines: list[str]) -> list[ParagraphBoundary]`
- `_build_initial_chunks(...) -> list[Chunk]`
- `_merge_small_chunks(...) -> list[Chunk]`
- `_split_large_chunk(...) -> list[Chunk]`
- `_count_tokens(text: str) -> int`

### Paragraph Name Heuristic (Practical)

A simple and robust heuristic for headers in cleaned code:

- Candidate line is left-aligned (not heavily indented)
- Ends with `.` (period)
- Is not a known division/section header:
  - `IDENTIFICATION DIVISION.`
  - `ENVIRONMENT DIVISION.`
  - `DATA DIVISION.`
  - `PROCEDURE DIVISION.`
  - `... SECTION.`
- Mostly identifier-like tokens (letters, digits, hyphen)

Use tests to lock this behavior before refining regex complexity.

---

## Edge Cases to Handle

1. **No PROCEDURE DIVISION:** Return fallback chunk(s), do not crash
2. **Single huge paragraph:** Split by sentence boundaries into <= 768 tokens
3. **Many tiny paragraphs:** Merge adjacent ones to meet minimum size
4. **Paragraph-like false positives:** Avoid labeling division/section lines as paragraphs
5. **Blank-line heavy files:** Preserve logical boundaries without empty chunks
6. **Copybooks (`.cpy`) without paragraphs:** Graceful fallback chunking

---

## Test Fixture Suggestions

```python
@pytest.fixture
def simple_processed_file() -> ProcessedFile:
    return ProcessedFile(
        code=(
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. TEST.\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-LOGIC.\n"
            "    PERFORM INIT-DATA.\n"
            "    STOP RUN.\n"
            "INIT-DATA.\n"
            "    MOVE 1 TO WS-COUNT.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/sample.cob",
        encoding="utf-8",
    )

@pytest.fixture
def tiny_paragraphs_processed_file() -> ProcessedFile:
    # Build multiple very small paragraphs to trigger merge logic
    ...

@pytest.fixture
def oversized_paragraph_processed_file() -> ProcessedFile:
    # Build one very large paragraph to trigger split logic
    ...
```

Core assertions to include:

- paragraph names detected correctly
- chunk boundaries do not cut normal paragraph blocks
- all chunks satisfy size policy after merge/split
- metadata fields are populated and consistent

---

## Definition of Done for MVP-005

- [ ] `src/ingestion/cobol_chunker.py` implements `chunk_cobol()` and helper logic
- [ ] Paragraph detection works for typical COBOL `PROCEDURE DIVISION` code
- [ ] Adaptive size rules enforced (merge <64, split >768)
- [ ] Chunk output uses `Chunk` dataclass with valid required fields
- [ ] Unit tests added and passing in `tests/test_cobol_chunker.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-005 entry
- [ ] Work completed on `feature/mvp-005-cobol-paragraph-chunker` and merged via PR

---

## Estimated Time: 60-90 minutes

| Task | Estimate |
|------|----------|
| Read references + inspect parser output samples | 10 min |
| Test scaffolding and failing tests | 20 min |
| Initial paragraph chunker implementation | 25 min |
| Merge/split edge case handling | 15 min |
| DEVLOG update | 5-10 min |

---

## After MVP-005: What Comes Next

- **MVP-006:** Metadata extraction improvements (division/dependencies normalization and enrichment)
- **MVP-007:** Batch embedding module (Voyage Code 2, 128 texts/call)

MVP-005 should produce reliable paragraph-aligned chunks and token counts that downstream retrieval quality depends on.

