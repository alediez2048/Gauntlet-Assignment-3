# MVP-002 Primer: Download GnuCOBOL Source

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** Phase 0 complete (`6da74d4`, `2e04456`, `8e4e8ac`) — scaffolding + docs + live Render health baseline. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-002 obtains the **real legacy source code** for GnuCOBOL and places it under:

`data/raw/gnucobol/`

This ticket does not implement parsers/chunkers yet. It prepares the raw corpus that MVP-003 and MVP-004 depend on.

### Why It Matters

- **Hard dependency:** MVP-004 (COBOL preprocessor) depends on actual COBOL files.
- **TDD unblock:** You cannot write meaningful parser/chunker tests without real source samples.
- **MVP gate:** The assignment requires ingesting at least one legacy codebase.

---

## What Was Already Done (Phase 0)

- Full project structure created under `src/`, `tests/`, `evaluation/`, and `Docs/`
- Config and language registry in `src/config.py` (COBOL extensions: `.cob`, `.cbl`, `.cpy`)
- Environment keys configured in `.env`
- Render deployment baseline is live:
  - `GET /api/health` -> `200`
  - `GET /api/codebases` -> `200`
- Documentation consolidated into `Docs/` categories
- Claude skills versioned into `.claude/skills/`

---

## What MVP-002 Must Accomplish

### Goal

Download or clone GnuCOBOL source so that `data/raw/gnucobol/` contains a usable COBOL corpus for ingestion and preprocessing.

### Deliverables Checklist

#### A. Acquire source into canonical path

- [ ] Create/verify path: `data/raw/gnucobol/`
- [ ] Download/clone GnuCOBOL source into that directory (or extract archive there)
- [ ] Keep source tree intact (do not flatten file structure)

#### B. Verify corpus quality for upcoming ingestion

- [ ] Confirm there are COBOL files with supported extensions:
  - `.cob`
  - `.cbl`
  - `.cpy`
- [ ] Confirm dataset is large enough for MVP expectations (50+ files, 10k+ LOC practical minimum)
- [ ] Confirm files are readable text and not only binaries/docs

#### C. Ensure git hygiene

- [ ] Verify `data/raw/` remains ignored by git (`.gitignore` already includes `data/raw/`)
- [ ] Do **not** commit raw source files

#### D. Document completion

- [ ] Add a new DEVLOG entry for MVP-002 in `Docs/tickets/DEVLOG.md`
- [ ] Include source method used (archive vs clone), counts, issues, and verification output

---

## Suggested Implementation Approach

Use either source archive download or repository clone from a trusted GnuCOBOL source location.

Reference from PRD:
- `https://sourceforge.net/projects/gnucobol/`
- `https://sourceforge.net/projects/gnucobol/files/` (noted in PRD appendix)

After download/extract, validate file inventory before moving on.

---

## Validation Commands (Expected in Ticket Work)

```bash
# 1) Verify target directory exists
ls -la data/raw/gnucobol

# 2) Count COBOL files by extension
rg --files data/raw/gnucobol | rg "\.(cob|cbl|cpy)$" | wc -l

# 3) Sample a few file paths
rg --files data/raw/gnucobol | rg "\.(cob|cbl|cpy)$" | head -20

# 4) Quick LOC estimate for COBOL files (rough)
python3 - <<'PY'
from pathlib import Path
root = Path("data/raw/gnucobol")
exts = {".cob", ".cbl", ".cpy"}
files = [p for p in root.rglob("*") if p.suffix.lower() in exts and p.is_file()]
loc = 0
for p in files:
    try:
        loc += sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        pass
print("files:", len(files))
print("loc:", loc)
PY

# 5) Confirm git ignore behavior
git status --short
```

Expected:
- COBOL file count > 0 (ideally 50+)
- LOC > 10,000 preferred for MVP realism
- `git status` should not list raw dataset files

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `data/raw/gnucobol/` | Add downloaded source corpus |
| `Docs/tickets/DEVLOG.md` | Add MVP-002 completion entry |

### Files You Should NOT Modify

- Do not modify parser/chunker implementation files yet (`src/ingestion/*`) in this ticket
- Do not modify deployment configuration unless needed for a blocker

### Rules/Constraints to Respect

- Use existing codebase registry assumptions in `src/config.py` (`gnucobol` + `.cob/.cbl/.cpy`)
- Keep raw data out of git history
- Keep this ticket scoped to data acquisition + validation

---

## Definition of Done for MVP-002

- [ ] `data/raw/gnucobol/` populated with real GnuCOBOL source files
- [ ] Supported COBOL extension files are present (`.cob/.cbl/.cpy`)
- [ ] Basic counts/validation executed and recorded
- [ ] Raw dataset not tracked by git
- [ ] DEVLOG updated with MVP-002 details

---

## Estimated Time: 30–60 minutes

| Task | Estimate |
|------|----------|
| Acquire source (download/clone/extract) | 20 min |
| Validate file inventory and LOC | 15 min |
| DEVLOG update | 10–20 min |

---

## After MVP-002: What Comes Next

- **MVP-003:** Language detector module (`src/ingestion/detector.py`)
- **MVP-004:** COBOL preprocessor (column stripping, encoding detection, comment separation)

MVP-003 and MVP-004 should start immediately after this ticket verifies that raw source is present and usable.

