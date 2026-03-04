# G4-003 Primer: Ingest GNU Fortran (gfortran) Source

**For:** New Cursor Agent session  
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-001 through MVP-016 complete. G4-001 (Fortran preprocessor) and G4-002 (Fortran subroutine chunker) complete. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-003 acquires the **GNU Fortran (gfortran) source code**, runs it through the full ingestion pipeline (`preprocess_fortran()` → `chunk_fortran()` → `embed_chunks()` → `index_chunks()`), and verifies that the chunks are correctly indexed in Qdrant with `codebase="gfortran"`.

This is the first Fortran codebase to be ingested — it validates the entire Fortran pipeline end-to-end with real data.

### Why Does This Exist?

1. **Pipeline validation:** G4-001/002 were unit-tested with synthetic data. Ingesting real gfortran source validates the preprocessor and chunker against real-world Fortran code.
2. **Codebase parity:** GnuCOBOL is already indexed. Adding gfortran is the first step toward the 5-codebase target.
3. **Unblocks downstream:** G4-004 (LAPACK) and G4-005 (BLAS) follow the same pipeline. Any bugs caught here save time later.
4. **Feature testing:** Once indexed, gfortran data enables testing all 8 features against Fortran code.

### Current State

| Component | Status |
|-----------|--------|
| `src/ingestion/fortran_parser.py` | **Complete** (G4-001) |
| `src/ingestion/fortran_chunker.py` | **Complete** (G4-002) |
| `src/ingestion/embedder.py` | **Complete** (MVP-007) |
| `src/ingestion/indexer.py` | **Complete** (MVP-008) |
| `src/ingestion/detector.py` | **Complete** (MVP-003) |
| `data/raw/gfortran/` | **Empty** — needs source acquisition |
| Qdrant collection `legacylens` | **Exists** — GnuCOBOL data already indexed |

---

## What Was Already Done

- The GnuCOBOL codebase was acquired and indexed successfully in MVP-002 through MVP-008
- The Fortran preprocessor (G4-001) handles fixed-form and free-form Fortran source
- The Fortran chunker (G4-002) detects SUBROUTINE/FUNCTION/PROGRAM/MODULE/BLOCK DATA boundaries
- The embedder (MVP-007) batches chunks through Voyage Code 2
- The indexer (MVP-008) upserts to Qdrant with payload indexes on `paragraph_name`, `division`, `file_path`, `language`, `codebase`
- The config registry in `src/config.py` already has the `gfortran` entry with extensions `.f`, `.f90`, `.f77`, `.f95`

---

## G4-003 Contract

### Phase 1: Source Acquisition

Download or clone the GNU Fortran source into `data/raw/gfortran/`.

#### Suggested Sources

The GCC source tree contains gfortran under the `gcc/fortran/` directory. Options:

1. **GCC source archive (recommended):** Download a GCC release tarball and extract the Fortran-relevant subdirectories
   - `https://ftp.gnu.org/gnu/gcc/` — official GCC mirror
   - Example: `gcc-13.2.0.tar.gz` or similar recent release
   - Extract `gcc-X.Y.Z/gcc/fortran/` and `gcc-X.Y.Z/gcc/testsuite/gfortran.dg/` into `data/raw/gfortran/`

2. **GCC Git mirror (alternative):** Shallow clone the GCC repo and keep only Fortran directories
   - `https://github.com/gcc-mirror/gcc.git`
   - Use `--depth 1 --filter=blob:none --sparse` to minimize download size
   - Sparse checkout: `gcc/fortran/` and `gcc/testsuite/gfortran.dg/`

3. **GNU Fortran test suite only (fallback):** If the full GCC tree is too large, focus on the gfortran test suite which contains hundreds of small `.f`, `.f90`, `.f95` files
   - The test suite alone provides excellent coverage of Fortran language features
   - Located at `gcc/testsuite/gfortran.dg/` in the GCC source tree

#### Corpus Requirements

| Metric | Minimum | Target |
|--------|---------|--------|
| Supported files (`.f`, `.f90`, `.f77`, `.f95`) | 50+ | 200+ |
| Total LOC | 10,000+ | 50,000+ |
| Mix of formats | Both fixed and free form | Both present |
| Readable text | All files readable | No binary files in corpus |

### Phase 2: Ingestion Pipeline

Create an ingestion script (or CLI command extension) that:

1. **Discovers** all Fortran files under `data/raw/gfortran/` using `detector.py`
2. **Preprocesses** each file using `preprocess_fortran()` from `fortran_parser.py`
3. **Chunks** each `ProcessedFile` using `chunk_fortran()` from `fortran_chunker.py`
4. **Embeds** all chunks in batches using `embed_chunks()` from `embedder.py`
5. **Indexes** all `EmbeddedChunk` objects using `index_chunks()` from `indexer.py`
6. **Reports** ingestion statistics: files processed, chunks created, chunks indexed, errors skipped

#### Ingestion Script Location

Create the script at `src/ingestion/ingest.py` (if not already present) or add a `ingest_codebase()` function that can be reused by G4-004, G4-005, and G4-006.

```python
def ingest_codebase(
    data_dir: str | Path,
    codebase: str,
    language: str,
) -> dict[str, int]:
    """Run the full ingestion pipeline for a codebase directory.
    
    Returns:
        Dict with keys: files_found, files_processed, chunks_created, 
        chunks_embedded, chunks_indexed, errors
    """
```

#### Pipeline Flow

```
data/raw/gfortran/
    ├── *.f, *.f90, *.f77, *.f95
    │
    ▼
detector.is_supported_source_file() → filter supported files
    │
    ▼
fortran_parser.preprocess_fortran() → ProcessedFile per file
    │
    ▼
fortran_chunker.chunk_fortran(pf, codebase="gfortran") → list[Chunk]
    │
    ▼
embedder.embed_chunks(all_chunks) → list[EmbeddedChunk]
    │
    ▼
indexer.index_chunks(embedded_chunks) → count indexed
    │
    ▼
Qdrant collection "legacylens" with codebase="gfortran" points
```

### Phase 3: Verification

After ingestion, verify:

1. **Qdrant point count:** Query Qdrant for points with `codebase="gfortran"` — should match chunk count
2. **Metadata correctness:** Sample a few points and verify `language="fortran"`, `codebase="gfortran"`, `chunk_type` is valid, `paragraph_name` populated
3. **Search sanity:** Run a few test queries filtered to `codebase="gfortran"` to confirm retrieval works
4. **No regression:** Existing GnuCOBOL data should still be queryable

---

## Deliverables Checklist

### A. Source Acquisition

- [ ] Download/clone gfortran source into `data/raw/gfortran/`
- [ ] Verify supported file count (50+ minimum)
- [ ] Verify LOC (10,000+ minimum)
- [ ] Verify git hygiene (raw data not tracked)

### B. Ingestion Pipeline

- [ ] Create or extend ingestion script (`src/ingestion/ingest.py`)
- [ ] `ingest_codebase()` function with reusable interface
- [ ] Pipeline: discover → preprocess → chunk → embed → index
- [ ] Error handling: skip unprocessable files with logged warnings
- [ ] Statistics reporting: files/chunks/errors counts

### C. Ingestion Execution

- [ ] Run full ingestion for `data/raw/gfortran/` with `codebase="gfortran"`
- [ ] Record ingestion statistics in DEVLOG

### D. Verification

- [ ] Qdrant point count matches expected chunk count
- [ ] Sample metadata spot-check passes
- [ ] Test query against gfortran data returns relevant results
- [ ] GnuCOBOL data not affected (existing points still queryable)

### E. Tests

- [ ] Add integration test for `ingest_codebase()` function (mock embedder/indexer)
- [ ] Test file discovery filters correctly by extension
- [ ] Test pipeline handles empty directories gracefully
- [ ] Test pipeline handles preprocessing errors gracefully (skip + continue)

### F. Repo Housekeeping

- [ ] Update `Docs/tickets/DEVLOG.md` with G4-003 entry
- [ ] Feature branch pushed

---

## Branch & Merge Workflow

```bash
git switch main && git pull
git switch -c feature/g4-003-ingest-gfortran
# ... implement ...
git push -u origin feature/g4-003-ingest-gfortran
```

Use Conventional Commits: `feat:`, `test:`, `fix:`.

---

## Technical Specification

### File Discovery

```python
from pathlib import Path
from src.ingestion.detector import is_supported_source_file, detect_language

def discover_files(data_dir: Path, language: str) -> list[Path]:
    """Find all supported source files for a given language."""
    files: list[Path] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        if not is_supported_source_file(path):
            continue
        detected = detect_language(path)
        if detected == language:
            files.append(path)
    return files
```

### Error Handling Strategy

The ingestion pipeline must be resilient to individual file failures:

```python
for file_path in fortran_files:
    try:
        processed = preprocess_fortran(file_path, codebase=codebase)
        if not processed.code.strip():
            stats["skipped_empty"] += 1
            continue
        chunks = chunk_fortran(processed, codebase=codebase)
        all_chunks.extend(chunks)
        stats["files_processed"] += 1
    except Exception as exc:
        logger.warning("Failed to process %s: %s", file_path, exc)
        stats["errors"] += 1
```

### Embedding Batch Strategy

Chunks should be collected first, then embedded in one `embed_chunks()` call (which internally batches at 128 texts/call). This minimizes API overhead:

```python
all_chunks: list[Chunk] = []
# ... collect from all files ...

if all_chunks:
    embedded = embed_chunks(all_chunks)
    indexed_count = index_chunks(embedded)
```

### Qdrant Verification Queries

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Count gfortran points
result = client.count(
    collection_name="legacylens",
    count_filter=Filter(
        must=[FieldCondition(key="codebase", match=MatchValue(value="gfortran"))]
    ),
)
print(f"gfortran points: {result.count}")

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
| `src/ingestion/ingest.py` | Reusable ingestion pipeline function |
| `tests/test_ingest.py` | Integration tests for ingestion pipeline |

### Files to Modify

| File | Action |
|------|--------|
| `Docs/tickets/DEVLOG.md` | Add G4-003 entry |

### Files You Should NOT Modify

- `src/ingestion/fortran_parser.py` (G4-001 is complete)
- `src/ingestion/fortran_chunker.py` (G4-002 is complete)
- `src/ingestion/cobol_parser.py` (complete)
- `src/ingestion/cobol_chunker.py` (complete)
- `src/ingestion/embedder.py` (MVP-007 is complete)
- `src/ingestion/indexer.py` (MVP-008 is complete)
- `src/ingestion/detector.py` (MVP-003 is complete)
- `src/types/chunks.py` (stable)
- `src/config.py` (already has gfortran entry)
- Any retrieval, generation, API, CLI, or frontend code

### Files to READ for Context

| File | Why |
|------|-----|
| `src/ingestion/fortran_parser.py` | Upstream preprocessor — produces `ProcessedFile` |
| `src/ingestion/fortran_chunker.py` | Upstream chunker — produces `list[Chunk]` |
| `src/ingestion/embedder.py` | `embed_chunks()` API contract |
| `src/ingestion/indexer.py` | `index_chunks()` API contract |
| `src/ingestion/detector.py` | `is_supported_source_file()`, `detect_language()` |
| `src/config.py` | `CODEBASES["gfortran"]` registry entry, API keys, Qdrant config |
| `Docs/tickets/DEVLOG.md` | Prior ticket context, especially MVP-002 (GnuCOBOL acquisition pattern) |

---

## Environment Requirements

The following environment variables must be set in `.env` before running ingestion:

| Variable | Purpose |
|----------|---------|
| `VOYAGE_API_KEY` | Voyage Code 2 embedding API |
| `QDRANT_URL` | Qdrant Cloud or local instance URL |
| `QDRANT_API_KEY` | Qdrant API key (if using Qdrant Cloud) |

Verify these are set before starting:

```bash
python -c "from src.config import VOYAGE_API_KEY, QDRANT_URL; print('Voyage:', bool(VOYAGE_API_KEY)); print('Qdrant:', bool(QDRANT_URL))"
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| GCC archive is very large (>1 GB compressed) | Only extract `gcc/fortran/` and `gcc/testsuite/gfortran.dg/` — skip the rest |
| Some test files have non-standard extensions | Filter strictly by `.f`, `.f90`, `.f77`, `.f95` using `detector.py` |
| Embedding costs for large corpus | Monitor chunk count before embedding. If >5,000 chunks, consider batching with pause |
| Qdrant Cloud free tier limits | Check point count before and after ingestion |
| Preprocessor/chunker bugs on real data | Log and skip files that cause errors. Fix later if needed. |
| Test suite files may contain invalid Fortran (intentional compile errors) | The preprocessor handles these gracefully (they produce valid `ProcessedFile` with code, just potentially odd) |

---

## Definition of Done for G4-003

- [ ] `data/raw/gfortran/` populated with real GNU Fortran source files
- [ ] Supported file count verified (50+ minimum)
- [ ] `src/ingestion/ingest.py` implements reusable `ingest_codebase()` function
- [ ] Full ingestion pipeline executed: preprocess → chunk → embed → index
- [ ] Qdrant contains gfortran points with correct metadata
- [ ] Existing GnuCOBOL data unaffected
- [ ] Integration tests for ingestion pipeline added
- [ ] No regressions in existing test suite
- [ ] DEVLOG updated with G4-003 entry
- [ ] Feature branch pushed

---

## Estimated Time

| Task | Estimate |
|------|----------|
| Source acquisition (download + extract) | 15–30 min |
| Ingestion script implementation | 30–45 min |
| Tests (TDD) | 20–30 min |
| Run full ingestion | 10–20 min (depends on corpus size + embedding API) |
| Verification + DEVLOG | 15–20 min |
| **Total** | **~1.5–2.5 hours** |

---

## After G4-003

With gfortran ingested:
- **G4-004** (Ingest LAPACK) uses the exact same `ingest_codebase()` function
- **G4-005** (Ingest BLAS) uses the exact same function
- **G4-006** (Ingest OpenCOBOL Contrib) uses the same function but with COBOL pipeline
- All 4 remaining codebases become trivial once the reusable ingestion function exists
