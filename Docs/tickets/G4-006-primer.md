# G4-006 Primer: Ingest OpenCOBOL Contrib Source

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-001 through MVP-016 complete. G4-001 (Fortran preprocessor), G4-002 (Fortran subroutine chunker), G4-003 (reusable ingestion pipeline), G4-004 (LAPACK ingestion), and G4-005 (BLAS ingestion) complete. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-006 acquires the **OpenCOBOL Contrib** source corpus, runs it through the existing ingestion pipeline (`ingest_codebase()`), and verifies indexed chunks in Qdrant with `codebase="opencobol-contrib"`.

OpenCOBOL Contrib is the second dedicated COBOL codebase in LegacyLens (after GnuCOBOL) and serves as the COBOL-side parity step toward all 5 codebases indexed.

### Why Does This Exist?

1. **5-codebase completion:** With G4-004 and G4-005 done, this ticket closes the final ingestion gap.
2. **COBOL diversity:** Adds real-world COBOL programs/utilities beyond compiler sources.
3. **Pipeline reuse proof (COBOL path):** Confirms `ingest_codebase()` works for another COBOL corpus without ingestion code changes.
4. **Feature quality:** Expands retrieval and business-logic/dependency testing against a second COBOL codebase.

### Current State

| Component | Status |
|-----------|--------|
| `src/ingestion/ingest.py` | **Complete** (G4-003) |
| `src/ingestion/cobol_parser.py` | **Complete** (MVP-004) |
| `src/ingestion/cobol_chunker.py` | **Complete** (MVP-005/MVP-006) |
| `src/ingestion/embedder.py` | **Complete** (MVP-007) |
| `src/ingestion/indexer.py` | **Complete** (MVP-008) |
| `data/raw/opencobol-contrib/` | **Empty** - needs source acquisition |
| Qdrant collection `legacylens` | **Exists** |

---

## What Was Already Done

- `ingest_codebase()` already exists in `src/ingestion/ingest.py`
- COBOL discovery/preprocessing/chunking modules are complete
- Config already includes `CODEBASES["opencobol-contrib"]` with language `cobol` and extensions `.cob`, `.cbl`, `.cpy`
- G4-004 and G4-005 proved reusable ingestion flow for additional codebases

---

## G4-006 Contract

### Phase 1: Source Acquisition

Download or clone OpenCOBOL Contrib source into `data/raw/opencobol-contrib/`.

#### Suggested Sources

1. **OpenCOBOL SourceForge (canonical):**  
   `https://sourceforge.net/projects/open-cobol/files/`
   - Download the contrib corpus release/tarball if available
   - Extract into `data/raw/opencobol-contrib/`

2. **GnuCOBOL contrib Git mirror (recommended fallback):**  
   `https://github.com/OCamlPro/gnucobol-contrib`
   - Shallow clone with `--depth 1`
   - Contains many `.cob`, `.cbl`, `.cpy` sources

**Source-of-truth decision for G4-006:** use a dedicated OpenCOBOL Contrib source under `data/raw/opencobol-contrib/`.  
Do **not** point this ticket at `data/raw/gnucobol/gnucobol-contrib/`; keep source provenance and ticket boundaries explicit.

#### Corpus Requirements

| Metric | Minimum | Target |
|--------|---------|--------|
| Supported files (`.cob`, `.cbl`, `.cpy`) | 30+ | 150+ |
| Total LOC | 15,000+ | 100,000+ |
| Readable text | All files readable | No binary files |

#### Pre-embed Encoding Sanity Check (Required)

Before running full embedding/indexing, run a lightweight dry scan (discover -> preprocess -> chunk) and confirm chunk contents are UTF-8 encodable.

If encoding anomalies appear (for example, unexpected decode behavior from `chardet`), apply a documented raw-data workaround for this ticket and record:
- affected files
- mitigation applied
- verification result

in `Docs/tickets/DEVLOG.md`.

### Phase 2: Ingestion Pipeline

Use the existing reusable function:

```python
from pathlib import Path
from src.ingestion.ingest import ingest_codebase

stats = ingest_codebase(
    data_dir=Path("data/raw/opencobol-contrib"),
    codebase="opencobol-contrib",
    language="cobol",
)
```

Default runner behavior should be full speed (no throttling params). Enable throttling only when account throughput or tier constraints require it.

If Voyage throughput is still constrained for your account, use:

```python
stats = ingest_codebase(
    data_dir=Path("data/raw/opencobol-contrib"),
    codebase="opencobol-contrib",
    language="cobol",
    rate_limit_delay=65.0,
    embed_sub_batch_size=10,
)
```

### Phase 3: Verification

After ingestion, verify:

1. **Qdrant point count:** `codebase="opencobol-contrib"` count matches chunks indexed
2. **Metadata correctness:** sampled points include:
   - `language="cobol"`
   - `codebase="opencobol-contrib"`
   - valid `chunk_type`
   - valid `paragraph_name` / `name`
3. **Search sanity:** basic OpenCOBOL Contrib queries return relevant chunks
4. **No regression:** existing indexed codebases are unaffected
   - verify `codebase="lapack"` remains queryable
   - verify `codebase="blas"` remains queryable
   - verify `codebase="gnucobol"` remains queryable

---

## Deliverables Checklist

### A. Source Acquisition

- [ ] Download/clone OpenCOBOL Contrib source into `data/raw/opencobol-contrib/`
- [ ] Verify supported file count (30+)
- [ ] Verify LOC threshold
- [ ] Verify git hygiene (`data/raw` not tracked)

### B. Ingestion Execution

- [ ] Add `scripts/run_ingest_opencobol_contrib.py` runner script
- [ ] Run ingestion for `codebase="opencobol-contrib"`
- [ ] Capture stats: files, chunks, errors, indexed count

### C. Verification

- [ ] Qdrant point count matches expected
- [ ] Metadata spot-check passes
- [ ] At least 3 sanity queries return relevant OpenCOBOL Contrib chunks
- [ ] Existing codebases still queryable (at minimum `lapack`, `blas`, `gnucobol`)

### D. Repo Housekeeping

- [ ] Update `Docs/tickets/DEVLOG.md` with G4-006 entry
- [ ] Commit scope limited to G4-006 files only (expected: `scripts/run_ingest_opencobol_contrib.py` and `Docs/tickets/DEVLOG.md`)
- [ ] Push feature branch

---

## Branch & Merge Workflow

```bash
git switch main && git pull
git switch -c feature/g4-006-ingest-opencobol-contrib
# ... implement and run ...
git push -u origin feature/g4-006-ingest-opencobol-contrib
```

Use Conventional Commits: `feat:`, `test:`, `fix:`, `docs:`.

---

## Technical Specification

### Runner Script

Create `scripts/run_ingest_opencobol_contrib.py`:

```python
from pathlib import Path
from src.ingestion.ingest import ingest_codebase

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "opencobol-contrib"

stats = ingest_codebase(
    data_dir=DATA_DIR,
    codebase="opencobol-contrib",
    language="cobol",
)
print(stats)
```

### Qdrant Verification Example

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from src.config import QDRANT_URL, QDRANT_API_KEY

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

count = client.count(
    collection_name="legacylens",
    count_filter=Filter(
        must=[
            FieldCondition(
                key="codebase",
                match=MatchValue(value="opencobol-contrib"),
            )
        ]
    ),
)
print("opencobol-contrib points:", count.count)
```

---

## Important Context

### Files to Create

| File | Action |
|------|--------|
| `scripts/run_ingest_opencobol_contrib.py` | OpenCOBOL Contrib ingestion runner |

### Files to Modify

| File | Action |
|------|--------|
| `Docs/tickets/DEVLOG.md` | Add G4-006 entry |

### Files You Should NOT Modify

- `src/ingestion/cobol_parser.py`
- `src/ingestion/cobol_chunker.py`
- `src/ingestion/embedder.py`
- `src/ingestion/indexer.py`
- `src/ingestion/detector.py`
- `src/types/chunks.py`
- `src/config.py`
- Retrieval/generation/API/CLI/frontend modules

### Files to READ for Context

| File | Why |
|------|-----|
| `src/ingestion/ingest.py` | Reusable ingestion orchestration |
| `src/config.py` | `CODEBASES["opencobol-contrib"]` mapping |
| `scripts/run_ingest_blas.py` | Latest ingestion runner pattern |
| `src/ingestion/cobol_parser.py` | COBOL preprocessing behavior |
| `src/ingestion/cobol_chunker.py` | COBOL chunk metadata/dependency behavior |
| `Docs/tickets/DEVLOG.md` | Prior ingestion notes and known constraints |

---

## Environment Requirements

Set these in `.env`:

| Variable | Purpose |
|----------|---------|
| `VOYAGE_API_KEY` | Embedding API access |
| `QDRANT_URL` | Qdrant endpoint |
| `QDRANT_API_KEY` | Qdrant auth (if cloud) |

Quick check:

```bash
python -c "from src.config import VOYAGE_API_KEY, QDRANT_URL; print(bool(VOYAGE_API_KEY), bool(QDRANT_URL))"
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Mixed archive content includes non-COBOL files | Discovery filters via `detector.py` |
| Voyage throughput variability | Use optional rate-limited ingestion params |
| Encoding mis-detection in raw files | Run pre-embed UTF-8 sanity scan and document any file-level workaround |
| Duplicate sample names across COBOL corpora | Keep strict `codebase="opencobol-contrib"` metadata for isolation |
| Hidden regressions | Run full tests and verify existing codebase counts |

---

## Definition of Done for G4-006

- [ ] `data/raw/opencobol-contrib/` populated with source corpus
- [ ] File count and LOC thresholds verified
- [ ] Ingestion pipeline executed successfully
- [ ] Qdrant contains `codebase="opencobol-contrib"` points with correct metadata
- [ ] Existing codebase data unaffected
- [ ] DEVLOG updated with G4-006 entry
- [ ] Feature branch pushed

---

## Estimated Time

| Task | Estimate |
|------|----------|
| Source acquisition | 10-15 min |
| Ingestion execution | 10-30 min |
| Verification + DEVLOG | 15-20 min |
| **Total** | **~35-65 min** |

---

## After G4-006

With OpenCOBOL Contrib ingested:
- All 5 target codebases are indexed
- **G4-007** (multi-codebase query support) can be validated against full corpus coverage
- Feature quality checks become more representative across both COBOL and Fortran
