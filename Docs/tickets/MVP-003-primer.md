# MVP-003 Primer: Language Detector Module

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** Phase 0 complete; MVP-002 data acquisition should be in progress/completed. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-003 implements the **language detection and dispatch layer** for ingestion.  
It maps file extensions to language and pipeline handlers so later tickets can route files correctly:

- COBOL (`.cob`, `.cbl`, `.cpy`) -> COBOL preprocessor/chunker
- Fortran (`.f`, `.f90`, `.f77`, `.f95`) -> Fortran preprocessor/chunker

This ticket does **not** parse code yet. It only decides how files should be routed.

### Why It Matters

- **Foundation dependency:** MVP-004 and later ingestion modules rely on detector output.
- **Multi-language correctness:** Wrong routing breaks preprocessors/chunkers downstream.
- **TDD unblock:** Defines stable contracts for parser/chunker unit tests.

---

## What Was Already Done

- `src/config.py` defines codebase registry with language + extensions + preprocessor + chunker
- `src/ingestion/detector.py` exists as placeholder (empty)
- `tests/test_detector.py` exists as placeholder (empty)
- Rules already specify extension mapping and unknown-file behavior:
  - `.cob/.cbl/.cpy` -> COBOL
  - `.f/.f90/.f77/.f95` -> Fortran
  - unknown extension -> skip with warning

---

## What MVP-003 Must Accomplish

### Goal

Replace the detector placeholder with a tested module that identifies language and returns dispatch metadata based on file extension.

### Deliverables Checklist

#### A. Detector Module (`src/ingestion/detector.py`)

- [ ] Implement extension-based language detection using `src.config.CODEBASES` (single source of truth)
- [ ] Support case-insensitive extensions
- [ ] Unknown extension behavior:
  - return `None`/unsupported result
  - log warning (do not crash ingestion)
- [ ] Provide helper(s) for downstream dispatch, e.g.:
  - `detect_language(path) -> "cobol" | "fortran" | None`
  - `get_processing_route(path) -> {language, preprocessor, chunker, codebase} | None`
  - `is_supported_source_file(path) -> bool`

#### B. Unit Tests (`tests/test_detector.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test COBOL mappings:
  - `.cob`, `.cbl`, `.cpy`
- [ ] Test Fortran mappings:
  - `.f`, `.f90`, `.f77`, `.f95`
- [ ] Test unknown extension skip behavior
- [ ] Test case-insensitivity (e.g., `FILE.CBL`, `routine.F90`)
- [ ] Minimum: 3+ focused tests (prefer 6-10 granular assertions)

#### C. Integration Expectations

- [ ] Public function signatures are stable and easy for later ingestion tickets to call
- [ ] No network calls, no Qdrant calls, no embedding calls in this ticket

#### D. Documentation

- [ ] Add MVP-003 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Record which signatures were introduced for parser/chunker modules

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before any code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-003-language-detector`
- Never commit directly to `main` for ticket work.
- Commit in small, meaningful increments using Conventional Commits:
  - `feat:`, `fix:`, `test:`, `docs:`, `refactor:`
- Push branch and open PR when ticket Definition of Done is met:
  - `git push -u origin feature/mvp-003-language-detector`
- Merge to `main` only after checks/review pass.
- After merge:
  - `git switch main && git pull`
  - delete branch locally/remotely if desired.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/ingestion/detector.py` | Replace placeholder with language/route detection logic |
| `tests/test_detector.py` | Add unit tests for mapping and unknown behavior |
| `Docs/tickets/DEVLOG.md` | Add MVP-003 completion entry (after done) |

### Files You Should NOT Modify

- `src/ingestion/cobol_parser.py` (MVP-004)
- `src/ingestion/cobol_chunker.py` (MVP-005)
- `src/ingestion/fortran_parser.py` (G4-001)
- `src/ingestion/fortran_chunker.py` (G4-002)
- Deployment config files (`Dockerfile`, `render.yaml`) unless blocking bug

### Cursor Rules to Follow

- `.cursor/rules/multi-codebase.mdc` — extension mapping and unknown-file handling
- `.cursor/rules/rag-pipeline.mdc` — custom pipeline constraints
- `.cursor/rules/tdd.mdc` — test-first workflow
- `.cursor/rules/code-patterns.mdc` — module ownership + typing conventions

---

## Suggested Implementation Pattern

Use `CODEBASES` in `src/config.py` to build an extension map once, rather than hardcoding duplicate dicts in detector.

Example route shape:

```python
{
    "language": "cobol",
    "codebase": "gnucobol",
    "preprocessor": "cobol",
    "chunker": "cobol_paragraph",
    "extension": ".cbl",
}
```

This keeps the detector synchronized with config and avoids drift.

---

## Definition of Done for MVP-003

- [ ] `src/ingestion/detector.py` implemented with extension-based routing
- [ ] Unknown extensions handled safely (skip + warning, no crash)
- [ ] Unit tests added and passing in `tests/test_detector.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-003 entry
- [ ] Work completed on `feature/mvp-003-language-detector` and merged via PR

---

## Estimated Time: 30–45 minutes

| Task | Estimate |
|------|----------|
| Test scaffolding and failing tests | 10 min |
| Detector implementation | 15 min |
| Test fixes/refactor | 10 min |
| DEVLOG update | 5–10 min |

---

## After MVP-003: What Comes Next

- **MVP-004:** COBOL preprocessor (column stripping, encoding, comments)
- **MVP-005:** COBOL paragraph chunker

MVP-003 should leave clean, stable routing contracts that MVP-004/005 can consume directly.

