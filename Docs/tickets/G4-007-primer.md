# G4-007 Primer: Multi-Codebase Query Verification

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 4, 2026
**Previous work:** Phase 1 (Fortran pipeline) and Phase 2 (all 5 codebases ingested) complete. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-007 verifies that the existing query pipeline works correctly across all 5 indexed codebases. This is a **verification-only ticket** — no new code is expected unless bugs are found.

The system already supports multi-codebase queries: the `codebase` filter param flows through `QueryRequest` → `hybrid_search()` → `rerank_chunks()` → `generate_answer()`. This ticket proves it works with real data.

### Why Does This Exist?

1. **Confidence gate:** Before evaluation (G4-008/009), confirm the pipeline returns relevant results for every codebase.
2. **Filter validation:** Verify the `codebase` param correctly isolates results — a LAPACK query with `codebase="lapack"` should not return BLAS or GnuCOBOL chunks.
3. **Cross-language check:** Both COBOL codebases (gnucobol, opencobol-contrib) and all 3 Fortran codebases (gfortran, lapack, blas) should work through the same API.
4. **Answer quality baseline:** Spot-check that GPT-4o generates grounded answers with proper citations for each codebase.

### Current State

| Component | Status |
|-----------|--------|
| Qdrant `legacylens` collection | **Indexed** — gnucobol, gfortran, lapack, blas, opencobol-contrib |
| `/api/query` endpoint | **Deployed** at `https://gauntlet-assignment-3.onrender.com` |
| `codebase` filter in search | **Implemented** in `hybrid_search()` |
| Feature param routing | **Implemented** — 8 features via `prompts.py` |

---

## What Was Already Done

- All 5 codebases ingested and indexed in Qdrant
- The API already accepts `codebase` as an optional filter in `QueryRequest`
- `hybrid_search()` passes `codebase` to Qdrant's filter
- `prompts.py` builds feature-specific system prompts
- Individual codebase sanity queries were run during each G4-003/004/005/006 ingestion verification

---

## G4-007 Contract

### Phase 1: Qdrant Count Verification

Confirm all 5 codebases have non-zero point counts:

```python
from src.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
for cb in ["gnucobol", "gfortran", "lapack", "blas", "opencobol-contrib"]:
    r = client.count(
        collection_name=QDRANT_COLLECTION_NAME,
        count_filter=Filter(must=[FieldCondition(key="codebase", match=MatchValue(value=cb))]),
    )
    print(f"{cb}: {r.count}")
```

Expected: at least 4 non-zero (gnucobol, lapack, blas, opencobol-contrib). **gfortran may be 0** if ingestion is still running (throttled runs can take a long time) — if so, skip gfortran in Phase 2 and note it in the DEVLOG entry.

### Phase 2: Per-Codebase Query Verification

Run one query per codebase through the deployed API. Each query should return relevant chunks from the correct codebase only.

| Codebase | Language | Query | Expected Top Result | Skip if |
|----------|----------|-------|---------------------|---------|
| gnucobol | cobol | "How does the PERFORM statement work?" | GnuCOBOL PROCEDURE DIVISION chunks | — |
| opencobol-contrib | cobol | "What COBOL sample programs are available?" | OpenCOBOL contrib sample files | — |
| lapack | fortran | "How does DGETRF perform LU factorization?" | `SRC/dgetrf.f` or variants | — |
| blas | fortran | "What does DGEMM do?" | `dgemm.f` chunks | — |
| gfortran | fortran | "How are Fortran array operations tested?" | gfortran test suite files | count = 0 |

Use curl or the API client:

```bash
API_URL="https://gauntlet-assignment-3.onrender.com"

# Example: LAPACK filtered query
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "How does DGETRF perform LU factorization?", "codebase": "lapack"}' \
  | python3 -m json.tool | head -30
```

#### Verification Criteria

For each query, confirm:
- [ ] Response includes `chunks` with `codebase` matching the filter
- [ ] No chunks from other codebases leak through
- [ ] `answer` field references the correct codebase context
- [ ] `confidence` is HIGH or MEDIUM (LOW acceptable for gnucobol due to only 3 points)
- [ ] Citations include `file_path` and `line_start`/`line_end`

### Phase 3: Unfiltered Cross-Codebase Query

Run one query without a `codebase` filter to verify the system searches across all codebases:

```bash
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "How is matrix multiplication implemented?"}' \
  | python3 -m json.tool | head -40
```

Expected: chunks from multiple codebases (likely LAPACK, BLAS, and possibly gfortran) appear in results.

### Phase 4: Multi-Feature Spot Check

Pick 2-3 features and verify they produce different answer styles for the same query. Use BLAS (Fortran) and/or opencobol-contrib (COBOL):

```bash
# BLAS — Code explanation (default)
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What does DAXPY do?", "codebase": "blas", "feature": "code_explanation"}'

# BLAS — Dependency mapping
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What does DAXPY do?", "codebase": "blas", "feature": "dependency_mapping"}'

# BLAS — Translation hints
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What does DAXPY do?", "codebase": "blas", "feature": "translation_hints"}'

# COBOL (opencobol-contrib) — optional
curl -s "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "How does COBOL handle file I-O?", "codebase": "opencobol-contrib", "feature": "code_explanation"}'
```

---

## Deliverables Checklist

- [ ] Qdrant counts verified (at least 4 non-zero; gfortran may be 0 if ingestion still running)
- [ ] Per-codebase filtered queries executed for each codebase with non-zero count (skip gfortran if 0)
- [ ] 1 unfiltered cross-codebase query executed
- [ ] 2-3 feature variations tested on same query (BLAS and/or opencobol-contrib)
- [ ] No codebase filter leaks observed
- [ ] Results recorded in DEVLOG (same format as G4-006: counts, sample queries, findings)
- [ ] Any bugs found are documented with fix recommendations

### Files to Modify

| File | Action |
|------|--------|
| `Docs/tickets/DEVLOG.md` | Add G4-007 entry with counts, sample queries, and findings (same format as G4-006) |

### Files You Should NOT Modify

- Any source code in `src/` (unless a bug is found)
- Ingestion scripts
- Test files
- Config files

---

## Known Considerations

1. **Fortran queries use `language: "cobol"` in the API** — the `language` validator in `schemas.py` only accepts `"cobol"`. This means Fortran codebase queries still go through COBOL prompt templates. This is a known limitation, not a blocker — the answers are still grounded in retrieved Fortran chunks. If this affects answer quality, document it as a finding.

2. **gnucobol has very few points (3)** — queries may return limited context and answers may be thin or low-confidence. This is expected given the small corpus size.

3. **gfortran ingestion is often still running** — throttled ingestion (e.g. `run_ingest_gfortran_throttled.py`) can take a long time. If the gfortran count is 0, skip gfortran queries in Phase 2 and note "gfortran ingestion pending" in the DEVLOG entry. Re-run G4-007 verification for gfortran once ingestion completes.

---

## Definition of Done

- [ ] All codebases with non-zero count return relevant results when filtered (gfortran may be skipped if ingestion pending)
- [ ] No cross-codebase contamination in filtered queries
- [ ] Unfiltered query returns multi-codebase results
- [ ] Multiple features produce differentiated answers
- [ ] DEVLOG updated with G4-007 verification evidence (counts, sample queries, findings)
