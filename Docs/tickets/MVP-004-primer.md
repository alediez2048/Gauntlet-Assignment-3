# MVP-004 Primer: COBOL Preprocessor

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-003 (language detector) complete and merged. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-004 implements the **COBOL preprocessor** — the module that takes raw COBOL source files and transforms them into a clean `ProcessedFile` dataclass ready for the chunker (MVP-005).

COBOL source has a rigid column-based format inherited from 80-column punch cards. This preprocessor must:

1. Detect file encoding via `chardet`
2. Strip sequence numbers (cols 1–6) and identification area (cols 73–80)
3. Identify and separate comments (col 7 indicator)
4. Handle continuation lines (col 7 = `-`)
5. Preserve the actual code (cols 8–72)
6. Return a `ProcessedFile` dataclass

### Why It Matters

- **Chunking depends on this:** MVP-005 (paragraph chunker) needs clean code with column artifacts removed
- **Embedding quality:** Raw COBOL with sequence numbers and trailing IDs adds noise to embeddings
- **Comment separation:** Comments become metadata — they should not pollute code chunks but must be preserved for documentation features
- **Encoding safety:** Legacy COBOL files may use EBCDIC, ISO-8859, or other encodings — chardet detection prevents mojibake

---

## What Was Already Done

- `src/ingestion/cobol_parser.py` exists as empty placeholder
- `tests/test_cobol_parser.py` exists as empty placeholder
- `src/types/chunks.py` defines `ProcessedFile` dataclass (the output type):

```python
@dataclass
class ProcessedFile:
    code: str                                    # cleaned source text
    comments: list[str]                          # extracted comment lines
    language: str                                # "cobol"
    file_path: str                               # relative path
    encoding: str = "utf-8"                      # detected encoding
    metadata: dict[str, str] = field(default_factory=dict)
```

- `src/ingestion/detector.py` provides `detect_language()` and `get_processing_route()` — the upstream dispatch layer
- COBOL format reference available at `.claude/skills/legacylens-ingestion/references/cobol-format.md`
- GnuCOBOL corpus on disk: 799 files at `data/raw/gnucobol/` (334 `.cob`, 246 `.cbl`, 219 `.cpy`)
- `chardet>=5.2.0` already in `requirements.txt`

---

## COBOL Column Layout (Critical Reference)

```
Cols 1-6:   Sequence number area     → STRIP (not code)
Col  7:     Indicator area           → INSPECT for line type
              ' ' = normal code line
              '*' = comment line     → extract to comments list
              '/' = comment + page break → extract to comments list
              '-' = continuation     → append to previous line
              'D' = debug line       → treat as comment
Cols 8-11:  Area A                   → division/section/paragraph headers
Cols 12-72: Area B                   → statements and clauses
Cols 73-80: Identification area      → STRIP (not code)
```

### Real Example from Corpus

Raw COBOL (`data/raw/gnucobol/gnucobol-3.2/extras/CBL_OC_DUMP.cob`):
```
      *>----------------------------------------------------------------
      *> Authors:   Brian Tiffin, Asger Kjelstrup, Simon Sobisch,
       IDENTIFICATION   DIVISION.
       PROGRAM-ID.      CBL_OC_DUMP.
       WORKING-STORAGE  SECTION.
       01  addr                  usage pointer.
```

After preprocessing:
- Comments extracted: `["Authors:   Brian Tiffin, Asger Kjelstrup, Simon Sobisch,", ...]`
- Code: `"IDENTIFICATION   DIVISION.\nPROGRAM-ID.      CBL_OC_DUMP.\nWORKING-STORAGE  SECTION.\n01  addr                  usage pointer."`
- Cols 1–6 and 73–80 stripped, col 7 indicators processed

---

## What MVP-004 Must Accomplish

### Goal

Replace the empty `src/ingestion/cobol_parser.py` placeholder with a tested preprocessor that transforms raw COBOL source into a `ProcessedFile`.

### Deliverables Checklist

#### A. Preprocessor Module (`src/ingestion/cobol_parser.py`)

- [ ] Main function: `preprocess_cobol(file_path: str | Path, codebase: str = "gnucobol") -> ProcessedFile`
- [ ] Encoding detection via `chardet`:
  - Read file as raw bytes
  - Detect encoding with `chardet.detect()`
  - Skip file (return empty `ProcessedFile` or raise) if confidence < 0.7
  - Decode bytes using detected encoding
- [ ] Column stripping:
  - Strip cols 1–6 (sequence numbers) from every line
  - Strip cols 73–80 (identification area) from every line
  - Handle short lines (< 7 chars, < 73 chars) gracefully
- [ ] Comment extraction via col 7 indicator:
  - `*` → full-line comment (extract text from cols 8–72)
  - `/` → page-break comment (same as `*` for our purposes)
  - `D` → debug line (treat as comment)
  - `-` → continuation line (append cols 12–72 to previous code line)
  - ` ` or any other → normal code line (cols 8–72)
- [ ] Handle `*>` inline/free-format comment style (common in modern GnuCOBOL):
  - Everything after `*>` on a line is a comment
- [ ] Return `ProcessedFile` with:
  - `code`: cleaned source text (cols 8–72, comments removed, continuations joined)
  - `comments`: list of extracted comment strings
  - `language`: `"cobol"`
  - `file_path`: the input path as string
  - `encoding`: detected encoding name
  - `metadata`: optional dict (e.g., `{"divisions_found": "IDENTIFICATION,DATA,PROCEDURE"}`)

#### B. Unit Tests (`tests/test_cobol_parser.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test column stripping:
  - Sequence numbers (cols 1–6) removed
  - Identification area (cols 73–80) removed
  - Actual code (cols 8–72) preserved
- [ ] Test comment detection:
  - `*` in col 7 → extracted as comment
  - `/` in col 7 → extracted as comment
  - `D` in col 7 → extracted as comment
- [ ] Test continuation handling:
  - `-` in col 7 → content appended to previous line
- [ ] Test encoding detection:
  - UTF-8 file detected and decoded
  - Low-confidence encoding → skip/error behavior
- [ ] Test short lines (< 7 chars) don't crash
- [ ] Test empty file doesn't crash
- [ ] Test `*>` free-format comment extraction
- [ ] Test against real corpus file (optional but valuable)
- [ ] Minimum: 8+ focused tests

#### C. Integration Expectations

- [ ] `preprocess_cobol` returns a `ProcessedFile` (from `src.types.chunks`)
- [ ] No network calls, no Qdrant calls, no embedding calls
- [ ] Function signature is stable for MVP-005 chunker consumption
- [ ] Works with both string and Path inputs

#### D. Documentation

- [ ] Add MVP-004 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Record the public function signature for downstream consumers

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before any code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-004-cobol-preprocessor`
- Never commit directly to `main` for ticket work.
- Commit in small, meaningful increments using Conventional Commits:
  - `feat:`, `fix:`, `test:`, `docs:`, `refactor:`
- Push branch and open PR when ticket Definition of Done is met:
  - `git push -u origin feature/mvp-004-cobol-preprocessor`
- Merge to `main` only after checks/review pass.
- After merge:
  - `git switch main && git pull`
  - delete branch locally/remotely if desired.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/cobol_parser.py` | Replace placeholder with COBOL preprocessing logic |
| `tests/test_cobol_parser.py` | Add unit tests for column stripping, comments, encoding, continuations |
| `Docs/tickets/DEVLOG.md` | Add MVP-004 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/detector.py` (MVP-003 — complete)
- `src/ingestion/cobol_chunker.py` (MVP-005 — next ticket)
- `src/ingestion/fortran_parser.py` (G4-001)
- `src/ingestion/fortran_chunker.py` (G4-002)
- `src/types/chunks.py` (already defines `ProcessedFile` correctly)
- `src/config.py` (already has all needed constants)
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `.claude/skills/legacylens-ingestion/references/cobol-format.md` | Full COBOL column layout reference |
| `src/types/chunks.py` | `ProcessedFile` dataclass definition |
| `src/ingestion/detector.py` | Upstream dispatch API (for understanding the pipeline flow) |
| `src/config.py` | Constants and codebase registry |
| `data/raw/gnucobol/gnucobol-3.2/extras/CBL_OC_DUMP.cob` | Real COBOL file for testing reference |

### Cursor Rules to Follow

- `.cursor/rules/multi-codebase.mdc` — COBOL preprocessing: column stripping (1-6, 73-80), encoding detection (chardet), comment separation (col 7)
- `.cursor/rules/rag-pipeline.mdc` — custom pipeline constraints
- `.cursor/rules/tdd.mdc` — test-first workflow
- `.cursor/rules/code-patterns.mdc` — module ownership + typing conventions

---

## Suggested Implementation Pattern

### Main Function Signature

```python
def preprocess_cobol(
    file_path: str | Path,
    codebase: str = "gnucobol",
) -> ProcessedFile:
```

### Processing Pipeline

```python
def preprocess_cobol(file_path, codebase="gnucobol"):
    # 1. Read raw bytes
    raw_bytes = Path(file_path).read_bytes()

    # 2. Detect encoding
    detection = chardet.detect(raw_bytes)
    if detection["confidence"] < 0.7:
        logger.warning("Low confidence encoding for %s: %s", file_path, detection)
        # Return empty ProcessedFile or raise

    encoding = detection["encoding"] or "utf-8"
    text = raw_bytes.decode(encoding, errors="replace")

    # 3. Process each line
    code_lines: list[str] = []
    comments: list[str] = []

    for line in text.splitlines():
        # Handle short lines
        if len(line) < 7:
            code_lines.append(line)
            continue

        # Strip cols 1-6 (sequence) and 73-80 (identification)
        indicator = line[6] if len(line) > 6 else " "
        code_area = line[7:72]  # cols 8-72 (0-indexed: 7-71)

        if indicator in ("*", "/", "D", "d"):
            comments.append(code_area.strip())
        elif indicator == "-":
            # Continuation: append to previous line
            if code_lines:
                code_lines[-1] = code_lines[-1] + code_area.lstrip()
        else:
            # Check for *> inline comment
            if "*>" in code_area:
                code_part, _, comment_part = code_area.partition("*>")
                code_lines.append(code_part.rstrip())
                comments.append(comment_part.strip())
            else:
                code_lines.append(code_area)

    # 4. Build ProcessedFile
    return ProcessedFile(
        code="\n".join(code_lines),
        comments=comments,
        language="cobol",
        file_path=str(file_path),
        encoding=encoding,
    )
```

This is a suggested starting point — adjust based on test results and edge cases.

### Edge Cases to Handle

1. **Short lines (< 7 chars):** Some files have blank or truncated lines
2. **Free-format COBOL:** Modern GnuCOBOL uses `*>` for inline comments without the col 7 convention
3. **Empty files:** Should return a valid `ProcessedFile` with empty code/comments
4. **Binary/unreadable files:** chardet confidence < 0.7 should skip gracefully
5. **Lines exactly 72 chars:** No identification area to strip
6. **Tab characters:** Some editors produce tabs instead of spaces in columns

---

## Test Fixture Suggestions

```python
@pytest.fixture
def classic_cobol_lines() -> str:
    """Fixed-format COBOL with sequence numbers and indicators."""
    return (
        "000100 IDENTIFICATION DIVISION.                                        PROG01\n"
        "000200 PROGRAM-ID. TEST-PROG.                                         PROG01\n"
        "000300*THIS IS A COMMENT LINE                                         PROG01\n"
        "000400 PROCEDURE DIVISION.                                            PROG01\n"
        "000500 MAIN-LOGIC.                                                    PROG01\n"
        "000600     DISPLAY \"HELLO\".                                           PROG01\n"
        "000700     STOP RUN.                                                  PROG01\n"
    )

@pytest.fixture
def continuation_lines() -> str:
    """COBOL with continuation line (col 7 = '-')."""
    return (
        "000100     MOVE \"THIS IS A VERY LONG LI                              PROG01\n"
        "000200-    \"TERAL VALUE\" TO WS-FIELD.                                PROG01\n"
    )

@pytest.fixture
def comment_variants() -> str:
    """All comment indicator types."""
    return (
        "000100*FULL LINE COMMENT                                              PROG01\n"
        "000200/PAGE BREAK COMMENT                                             PROG01\n"
        "000300DDEBUG LINE                                                     PROG01\n"
        "000400 NORMAL CODE LINE.                                              PROG01\n"
    )
```

---

## Definition of Done for MVP-004

- [ ] `src/ingestion/cobol_parser.py` implements `preprocess_cobol()` function
- [ ] Encoding detection via chardet with confidence threshold (< 0.7 skips)
- [ ] Column stripping: cols 1–6 and cols 73–80 removed
- [ ] Comment extraction: `*`, `/`, `D` indicators in col 7 → comments list
- [ ] Continuation handling: `-` in col 7 → appended to previous line
- [ ] Short/empty lines handled without crashes
- [ ] Returns `ProcessedFile` dataclass from `src.types.chunks`
- [ ] Unit tests added and passing in `tests/test_cobol_parser.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-004 entry
- [ ] Work completed on `feature/mvp-004-cobol-preprocessor` and merged via PR

---

## Estimated Time: 45–60 minutes

| Task | Estimate |
|------|----------|
| Read COBOL format reference + corpus samples | 5 min |
| Test scaffolding and failing tests | 15 min |
| Preprocessor implementation | 20 min |
| Edge case handling + test fixes | 10 min |
| DEVLOG update | 5–10 min |

---

## After MVP-004: What Comes Next

- **MVP-005:** COBOL paragraph chunker — takes the `ProcessedFile` from this module and produces `Chunk` objects on paragraph boundaries (adaptive 64–768 tokens)
- **MVP-006:** Metadata extraction — populates division, dependencies, chunk_type fields

MVP-004 should produce clean `ProcessedFile` output that MVP-005 can consume directly for paragraph boundary detection and chunking.
