# G4-004 Primer: Ingest LAPACK Source

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-001 through MVP-016 complete. G4-001 (Fortran preprocessor), G4-002 (Fortran subroutine chunker), and G4-003 (ingestion pipeline + gfortran acquisition) complete. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-004 acquires the **LAPACK (Linear Algebra PACKage)** source code, runs it through the full ingestion pipeline using `ingest_codebase()` from G4-003, and verifies that the chunks are correctly indexed in Qdrant with `codebase="lapack"`.

LAPACK is the largest Fortran codebase in the LegacyLens target set — hundreds of subroutines for matrix factorizations, eigenvalue problems, and linear solvers.

### Why Does This Exist?

1. **Codebase parity:** The target is 5 codebases. GnuCOBOL is indexed; gfortran acquisition is complete (ingestion run pending Voyage upgrade). Adding LAPACK brings us to 3 of 5.
2. **Pipeline reuse validation:** `ingest_codebase()` from G4-003 should work with zero code changes — LAPACK is pure Fortran and uses the same preprocessor/chunker.
3. **Quality corpus:** LAPACK is professional scientific computing code — well-structured subroutines with clear naming conventions. This produces high-quality chunks for downstream feature testing.
4. **Feature testing:** Dense linear algebra routines are excellent test cases for code explanation, dependency mapping, and pattern detection features.

### Current State

| Component | Status |
|-----------|--------|
| `src/ingestion/ingest.py` | **Complete** (G4-003) — `ingest_codebase()` ready |
| `src/ingestion/fortran_parser.py` | **Complete** (G4-001) |
| `src/ingestion/fortran_chunker.py` | **Complete** (G4-002) |
| `src/ingestion/embedder.py` | **Complete** (MVP-007) |
| `src/ingestion/indexer.py` | **Complete** (MVP-008) |
| `data/raw/lapack/` | **Empty** — needs source acquisition |
| Qdrant collection `legacylens` | **Exists** — GnuCOBOL data already indexed |

---

## What Was Already Done

- G4-003 created the reusable `ingest_codebase()` function — this ticket uses it directly
- The Fortran preprocessor (G4-001) and chunker (G4-002) handle all Fortran source formats
- The config registry in `src/config.py` already has the `lapack` entry with extensions `.f`, `.f90`
- The `scripts/run_ingest_gfortran.py` script demonstrates how to call `ingest_codebase()` with rate limiting

---

## G4-004 Contract

### Phase 1: Source Acquisition

Download or clone the LAPACK source into `data/raw/lapack/`.

#### Suggested Sources

1. **Official LAPACK GitHub (recommended):** https://github.com/Reference-LAPACK/lapack
   - Clone with `--depth 1` to minimize download
   - The relevant Fortran source is in `SRC/`, `BLAS/SRC/`, `TESTING/`, and `INSTALL/`
   - Note: LAPACK bundles its own BLAS reference implementation — keep it for this ticket (G4-005 BLAS uses a separate dedicated source)

2. **Netlib archive (alternative):** https://www.netlib.org/lapack/
   - Official distribution as tarball
   - `lapack-3.12.0.tar.gz` or similar recent release

#### Corpus Requirements

| Metric | Minimum | Target |
|--------|---------|--------|
| Supported files (`.f`, `.f90`) | 50+ | 200+ |
| Total LOC | 10,000+ | 50,000+ |
| Mix of formats | Both fixed and free form | Both present |
| Readable text | All files readable | No binary files in corpus |

### Phase 2: Ingestion Pipeline

Use the existing `ingest_codebase()` function from `src/ingestion/ingest.py`:

```python
from src.ingestion.ingest import ingest_codebase

stats = ingest_codebase(
    data_dir="data/raw/lapack",
    codebase="lapack",
    language="fortran",
    # If Voyage rate limits still apply:
    rate_limit_delay=65.0,
    embed_sub_batch_size=10,
)
```

No new code should be needed for ingestion — `ingest_codebase()` handles everything.

### Phase 3: Verification

After ingestion, verify:

1. **Qdrant point count:** Query Qdrant for points with `codebase="lapack"` — should match chunk count
2. **Metadata correctness:** Sample a few points and verify `language="fortran"`, `codebase="lapack"`, `chunk_type` is valid
3. **Search sanity:** Run a few test queries filtered to `codebase="lapack"` to confirm retrieval works
4. **No regression:** Existing data (GnuCOBOL and any gfortran points) should still be queryable

---

## Deliverables Checklist

### A. Source Acquisition

- [ ] Download/clone LAPACK source into `data/raw/lapack/`
- [ ] Verify supported file count (50+ minimum)
- [ ] Verify LOC (10,000+ minimum)
- [ ] Verify git hygiene (raw data not tracked)

### B. Ingestion Execution

- [ ] Run `ingest_codebase()` for `data/raw/lapack/` with `codebase="lapack"`
- [ ] Record ingestion statistics in DEVLOG
- [ ] Create `scripts/run_ingest_lapack.py` runner script

### C. Verification

- [ ] Qdrant point count matches expected chunk count
- [ ] Sample metadata spot-check passes
- [ ] Test query against LAPACK data returns relevant results
- [ ] Existing codebase data not affected

### D. Repo Housekeeping

- [ ] Update `Docs/tickets/DEVLOG.md` with G4-004 entry
- [ ] Feature branch pushed

---

## Branch & Merge Workflow

```bash
git switch main && git pull
git switch -c feature/g4-004-ingest-lapack
# ... execute ...
git push -u origin feature/g4-004-ingest-lapack
```

Use Conventional Commits: `feat:`, `test:`, `fix:`.

---

## Technical Specification

### Ingestion Script

Create `scripts/run_ingest_lapack.py`:

```python
from src.ingestion.ingest import ingest_codebase
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "lapack"

stats = ingest_codebase(
    data_dir=DATA_DIR,
    codebase="lapack",
    language="fortran",
)
print(stats)
```

### Qdrant Verification Queries

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Count lapack points
result = client.count(
    collection_name="legacylens",
    count_filter=Filter(
        must=[FieldCondition(key="codebase", match=MatchValue(value="lapack"))]
    ),
)
print(f"lapack points: {result.count}")

# Verify gnucobol still present
result = client.count(
    collection_name="legacylens",
    count_filter=Filter(
        must=[FieldCondition(key="codebase", match=MatchValue(value="gnucobol"))]
    ),
)
print(f"gnucobol points: {result.count}")
```

---

## Important Context

### Files to Create

| File | Action |
|------|--------|
| `scripts/run_ingest_lapack.py` | Ingestion runner script |

### Files to Modify

| File | Action |
|------|--------|
| `Docs/tickets/DEVLOG.md` | Add G4-004 entry |

### Files You Should NOT Modify

- `src/ingestion/ingest.py` (G4-003 is complete — reuse as-is)
- `src/ingestion/fortran_parser.py` (G4-001 is complete)
- `src/ingestion/fortran_chunker.py` (G4-002 is complete)
- `src/ingestion/embedder.py` (MVP-007 is complete)
- `src/ingestion/indexer.py` (MVP-008 is complete)
- `src/ingestion/detector.py` (MVP-003 is complete)
- `src/types/chunks.py` (stable)
- `src/config.py` (already has lapack entry)
- Any retrieval, generation, API, CLI, or frontend code

### Files to READ for Context

| File | Why |
|------|-----|
| `src/ingestion/ingest.py` | `ingest_codebase()` API — your only entry point |
| `src/config.py` | `CODEBASES["lapack"]` registry entry |
| `scripts/run_ingest_gfortran.py` | Example of how to call `ingest_codebase()` with rate limiting |
| `Docs/tickets/DEVLOG.md` | G4-003 entry shows corpus acquisition patterns and Voyage rate limit details |

---

## Environment Requirements

The following environment variables must be set in `.env` before running ingestion:

| Variable | Purpose |
|----------|---------|
| `VOYAGE_API_KEY` | Voyage Code 2 embedding API |
| `QDRANT_URL` | Qdrant Cloud or local instance URL |
| `QDRANT_API_KEY` | Qdrant API key (if using Qdrant Cloud) |

**Important:** If the Voyage free tier rate limits (3 RPM, 10K TPM) have not been upgraded by adding a payment method, use rate-limited parameters:

```python
stats = ingest_codebase(
    ...,
    rate_limit_delay=65.0,
    embed_sub_batch_size=10,
)
```

If the rate limits have been upgraded, omit these parameters to run at full speed.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LAPACK repo includes CMake/build artifacts | Filter strictly by `.f`, `.f90` using `detector.py` — only Fortran files are ingested |
| Some LAPACK files are very large (5,000+ lines) | Chunker handles oversized splits (>768 tokens) on line boundaries |
| Voyage rate limits still active | Use rate-limited parameters per G4-003 pattern |
| LAPACK bundles BLAS reference impl | Keep it — BLAS files under lapack/ get `codebase="lapack"`. G4-005 uses a separate BLAS source |

---

## Definition of Done for G4-004

- [ ] `data/raw/lapack/` populated with real LAPACK source files
- [ ] Supported file count verified (50+ minimum)
- [ ] Full ingestion pipeline executed: preprocess → chunk → embed → index
- [ ] Qdrant contains lapack points with correct metadata
- [ ] Existing codebase data unaffected
- [ ] No regressions in existing test suite
- [ ] DEVLOG updated with G4-004 entry
- [ ] Feature branch pushed

---

## Estimated Time

| Task | Estimate |
|------|----------|
| Source acquisition (clone) | 5–10 min |
| Ingestion run (depends on rate limits) | 5–60 min |
| Verification + DEVLOG | 10–15 min |
| **Total** | **~20–85 min** |

---

## After G4-004

With LAPACK ingested:
- **G4-005** (Ingest BLAS) follows the exact same pattern — clone + `ingest_codebase()`
- **G4-006** (Ingest OpenCOBOL Contrib) uses the same function but with COBOL pipeline
- **G4-007** (Multi-codebase query support) becomes testable with 3+ indexed codebases
