# G4-001 Primer: Fortran Preprocessor

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-001 through MVP-016 complete. COBOL pipeline operational end-to-end. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-001 implements the **Fortran preprocessor** in `src/ingestion/fortran_parser.py`. This is the Fortran equivalent of the COBOL preprocessor (`cobol_parser.py`, MVP-004) — it transforms raw Fortran source files into clean `ProcessedFile` objects that the Fortran chunker (G4-002) will consume.

### Why Does This Exist?

Fortran has two completely different source formats that must be handled:

1. **Fixed-form** (Fortran 77 and earlier) — column-based layout similar to COBOL, inherited from punch cards
2. **Free-form** (Fortran 90+) — modern format with no column restrictions

The preprocessor must detect which format each file uses, then apply the correct stripping/comment/continuation rules. Without this, the chunker would receive raw formatting artifacts that pollute embeddings and degrade retrieval quality.

### Current State

| Component | Status |
|-----------|--------|
| `src/ingestion/fortran_parser.py` | **Empty placeholder** — needs full implementation |
| `tests/test_fortran_parser.py` | **Empty or not yet written** — needs TDD tests |
| `src/ingestion/cobol_parser.py` | **Complete** — reference implementation to mirror |
| `src/types/chunks.py` | **Complete** — `ProcessedFile` dataclass is stable |

---

## What Was Already Done

- The COBOL preprocessor (`cobol_parser.py`) is fully implemented and tested — it serves as the architectural template
- Language detection (`detector.py`) already routes `.f`, `.f90`, `.f77`, `.f95` to `language="fortran"`, `preprocessor="fortran"`
- The `ProcessedFile` dataclass in `src/types/chunks.py` is stable and language-agnostic
- chardet is already a dependency for encoding detection

---

## G4-001 Contract

### Public API

One public function mirroring the COBOL preprocessor signature:

```python
def preprocess_fortran(
    file_path: str | Path,
    codebase: str = "gfortran",
) -> ProcessedFile:
```

### Fortran Fixed-Form Layout (`.f`, `.f77`)

```
Col  1:     Comment indicator (C, c, * → entire line is a comment)
Cols 1-5:   Label/statement number field (strip)
Col  6:     Continuation column (non-blank, non-zero = continuation of previous line)
Cols 7-72:  Statement field (actual code — preserve)
Cols 73+:   Identification field (strip, like COBOL)
```

### Fortran Free-Form Layout (`.f90`, `.f95`)

```
No column restrictions. Lines up to 132 characters.
!  anywhere on line = inline comment (rest of line is comment)
&  at end of line = continuation on next line
Full line is code (minus comments)
```

### Format Detection Strategy

**Primary:** Extension-based default

| Extension | Default Format |
|-----------|---------------|
| `.f` | fixed |
| `.f77` | fixed |
| `.f90` | free |
| `.f95` | free |

**Secondary:** Heuristic override — scan the first 20 non-blank lines for signals:

| Signal | Suggests |
|--------|----------|
| `C`, `c`, or `*` in column 1 as comment indicator | fixed |
| Non-blank character in column 6 (continuation) | fixed |
| `!` used as inline comment | free |
| `&` at end of line (continuation) | free |
| Lines exceeding 72 characters of actual content | free |

If heuristic signals conflict with the extension default, log a warning and trust the extension. This keeps behavior deterministic while allowing future override if needed.

### Processing Pipeline

1. **Read raw bytes** from file
2. **Detect encoding** via `chardet.detect()` — skip file if confidence < 0.7 (same as COBOL)
3. **Decode text** using detected encoding
4. **Detect format** (fixed vs free) using extension + heuristic
5. **Process each line** according to format:
   - **Fixed:** strip cols 1-5 and 73+, handle col 1 comment indicators, handle col 6 continuations, extract cols 7-72
   - **Free:** extract `!` inline comments, handle `&` continuations, full line is code
6. **Build `ProcessedFile`** with code, comments, language, encoding, metadata

### Metadata

The returned `ProcessedFile.metadata` dict should include:

```python
{
    "codebase": codebase,       # e.g., "gfortran"
    "source_format": "fixed" | "free",
    "units_found": "SUBROUTINE,FUNCTION,...",  # scan for program unit keywords
}
```

### Helper Functions (private)

Following the `cobol_parser.py` pattern:

| Helper | Purpose |
|--------|---------|
| `_detect_encoding(raw_bytes, file_path)` | chardet with 0.7 confidence threshold (can reuse COBOL's pattern) |
| `_detect_source_format(file_path, lines)` | Extension default + heuristic override |
| `_process_fixed_line(line, code_lines, comments)` | Fixed-form column stripping + comment/continuation |
| `_process_free_line(line, code_lines, comments)` | Free-form `!` comment and `&` continuation handling |
| `_find_program_units(code)` | Scan for SUBROUTINE, FUNCTION, PROGRAM, MODULE keywords |

---

## Deliverables Checklist

### A. Tests First (TDD)

- [ ] Create `tests/test_fortran_parser.py` with tests covering:

**Fixed-form tests:**
- [ ] Col 1 `C`/`c`/`*` comment indicators extract comments
- [ ] Cols 1-5 label field stripped from output
- [ ] Cols 73+ identification field stripped
- [ ] Cols 7-72 code area preserved
- [ ] Col 6 continuation joins lines correctly
- [ ] Col 6 continuation does not produce separate line

**Free-form tests:**
- [ ] `!` full-line comment extracted
- [ ] `!` inline comment extracted, code before it preserved
- [ ] `&` continuation joins lines correctly
- [ ] Lines longer than 72 chars preserved (no truncation)

**Format detection tests:**
- [ ] `.f` file detected as fixed-form
- [ ] `.f90` file detected as free-form
- [ ] `.f77` file detected as fixed-form
- [ ] `.f95` file detected as free-form

**Encoding tests:**
- [ ] Valid encoding detected and file processed
- [ ] Low-confidence encoding returns empty ProcessedFile

**Edge cases:**
- [ ] Empty file returns valid ProcessedFile with empty code
- [ ] Short lines (< 7 chars) don't crash in fixed-form mode
- [ ] File with mixed indicators handled gracefully

**Return contract tests:**
- [ ] Returns `ProcessedFile` dataclass
- [ ] `language` is `"fortran"`
- [ ] `file_path` is set correctly
- [ ] `encoding` is a non-empty string
- [ ] Accepts both `str` and `Path` inputs
- [ ] `metadata["codebase"]` is set
- [ ] `metadata["source_format"]` is `"fixed"` or `"free"`

### B. Implementation

- [ ] Implement `preprocess_fortran()` in `src/ingestion/fortran_parser.py`
- [ ] All helper functions with type hints and return types
- [ ] All tests pass
- [ ] No regressions in existing test suite (182 collected, 180 passed, 2 pre-existing failures)

### C. Repo Housekeeping

- [ ] Update `Docs/tickets/DEVLOG.md` with G4-001 entry
- [ ] Feature branch pushed

---

## Branch & Merge Workflow

```bash
git switch main && git pull
git switch -c feature/g4-001-fortran-preprocessor
# ... implement ...
git push -u origin feature/g4-001-fortran-preprocessor
```

Use Conventional Commits: `test:`, `feat:`, `fix:`.

---

## Technical Specification

### Fortran Comment Patterns

**Fixed-form (col 1 indicators):**
```fortran
C     This is a comment (C in column 1)
c     Also a comment (lowercase c)
*     Also a comment (asterisk in column 1)
      X = 1  (normal code — col 1 is blank)
```

**Free-form (`!` comments):**
```fortran
! This is a full-line comment
x = 1.0  ! This is an inline comment
```

### Fortran Continuation Patterns

**Fixed-form (col 6):**
```fortran
      CALL VERY_LONG_SUBROUTINE_NAME(
     &     ARG1, ARG2, ARG3,
     &     ARG4, ARG5)
```
Any non-blank, non-zero character in col 6 means "continuation of previous line". The `&` is conventional but not required — any character works.

**Free-form (`&`):**
```fortran
x = a + b + c + &
    d + e + f
```
`&` at the end of a line means "continued on next line". If the next line also starts with `&`, the `&` is stripped from both ends.

### Program Unit Keywords (for metadata)

Scan the cleaned code for these (case-insensitive):

```
PROGRAM, SUBROUTINE, FUNCTION, MODULE, BLOCK DATA
```

Store found keywords in `metadata["units_found"]` as comma-separated list, similar to COBOL's `divisions_found`.

---

## Important Context

### Files to Create

| File | Action |
|------|--------|
| `tests/test_fortran_parser.py` | Write TDD tests first |

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/fortran_parser.py` | Implement `preprocess_fortran()` |
| `Docs/tickets/DEVLOG.md` | Add G4-001 entry |

### Files You Should NOT Modify

- `src/ingestion/cobol_parser.py` (reference only — do not change)
- `src/types/chunks.py` (ProcessedFile is stable)
- `src/ingestion/detector.py` (already routes Fortran extensions correctly)
- Any API, CLI, retrieval, or generation code
- Any existing test files

### Files to READ for Context

| File | Why |
|------|-----|
| `src/ingestion/cobol_parser.py` | Architectural template — mirror this structure |
| `tests/test_cobol_parser.py` | Test pattern template — mirror this structure |
| `src/types/chunks.py` | `ProcessedFile` dataclass contract |
| `src/config.py` | `CODEBASES` dict — Fortran codebase entries |
| `.claude/skills/legacylens-ingestion/references/fortran-format.md` | Fortran fixed/free form reference |

---

## Definition of Done for G4-001

- [ ] `src/ingestion/fortran_parser.py` implements `preprocess_fortran()` with fixed + free form support
- [ ] Format detection works by extension with heuristic fallback
- [ ] Fixed-form: col 1 comments, cols 1-5 stripped, cols 73+ stripped, col 6 continuations
- [ ] Free-form: `!` comments (inline + full-line), `&` continuations
- [ ] Encoding detection via chardet with confidence threshold
- [ ] Returns `ProcessedFile` with `language="fortran"` and `metadata` including `source_format`
- [ ] Unit tests written first (TDD) and all passing
- [ ] No regressions in existing test suite
- [ ] DEVLOG updated with G4-001 entry
- [ ] Feature branch pushed

---

## After G4-001

With the Fortran preprocessor done:
- **G4-002** (Fortran subroutine chunker) can begin — it consumes `ProcessedFile` from this module
- **G4-003/004/005** (Fortran codebase ingestion) become possible once G4-002 is also done
- **G4-006** (OpenCOBOL Contrib) can start immediately since it uses the existing COBOL pipeline
