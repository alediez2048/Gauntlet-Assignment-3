# G4-008 Primer: Ground Truth Evaluation Dataset + Evaluation Script

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 4, 2026
**Previous work:** All 5 codebases ingested. G4-007 (multi-codebase verification) should be complete or in progress. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-008 creates a ground truth evaluation dataset and implements the evaluation script (`evaluation/evaluate.py`). This combines the original G4-008 (dataset), G4-009 (script), and G4-022 (run) into a single ticket for efficiency.

The goal: prove LegacyLens retrieval quality with real numbers.

### Why Does This Exist?

1. **Quantitative proof:** "It works" is not enough. Retrieval precision@5 gives a concrete metric.
2. **Per-codebase visibility:** Identify if certain codebases retrieve poorly.
3. **Feature coverage:** Ensure all 8 features produce usable answers, not just `code_explanation`.
4. **Regression baseline:** Future changes can be evaluated against this dataset.

---

## What Was Already Done

- `evaluation/evaluate.py` exists but is **empty** (0 bytes)
- `evaluation/ground_truth.json` exists with an empty queries array: `{"queries": []}`
- The API is deployed and working at `https://gauntlet-assignment-3.onrender.com`
- All 5 codebases indexed in Qdrant
- The query endpoint returns `chunks` with `file_path`, `codebase`, `name`, `score`, `confidence`

---

## G4-008 Contract

### Phase 1: Ground Truth Dataset

Create `evaluation/ground_truth.json` with 25-30 query/answer pairs.

#### Dataset Requirements

| Dimension | Minimum |
|-----------|---------|
| Total queries | 25 |
| Codebases covered | All 5 (at least 3 queries each) |
| Features covered | At least 4 of 8 |
| Languages | Both COBOL and Fortran |

#### Schema

```json
{
  "queries": [
    {
      "id": "q001",
      "query": "How does DGETRF perform LU factorization?",
      "codebase": "lapack",
      "feature": "code_explanation",
      "expected_files": ["SRC/dgetrf.f"],
      "expected_names": ["DGETRF"],
      "notes": "Should retrieve the main DGETRF subroutine and explain pivoted LU decomposition"
    }
  ]
}
```

#### Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique query identifier (q001, q002, ...) |
| `query` | Yes | Natural language question |
| `codebase` | Yes | Target codebase filter |
| `feature` | Yes | Feature to use (one of the 8 configured features) |
| `expected_files` | Yes | List of file path substrings that should appear in top-5 chunks |
| `expected_names` | Yes | List of chunk name substrings that should appear in top-5 |
| `notes` | No | Human context about what a good answer looks like |

#### Query Distribution Guide

**COBOL codebases (gnucobol + opencobol-contrib): ~10 queries**

| Feature | Example Query | Codebase |
|---------|---------------|----------|
| code_explanation | "What does the PROCEDURE DIVISION do in the main program?" | gnucobol |
| dependency_mapping | "What paragraphs are called from the main program flow?" | gnucobol |
| translation_hints | "How would the file I/O operations look in Python?" | gnucobol |
| business_logic | "What business rules are implemented in the validation logic?" | opencobol-contrib |
| documentation_gen | "Generate documentation for the COBOL sample programs" | opencobol-contrib |

**Fortran codebases (lapack + blas + gfortran): ~15 queries**

| Feature | Example Query | Codebase |
|---------|---------------|----------|
| code_explanation | "How does DGETRF perform LU factorization?" | lapack |
| code_explanation | "What does DGEMM do for matrix multiplication?" | blas |
| code_explanation | "What does the SAXPY routine compute?" | blas |
| dependency_mapping | "What subroutines does DGESV call?" | lapack |
| dependency_mapping | "What BLAS routines are used internally?" | blas |
| pattern_detection | "What common patterns appear in LAPACK driver routines?" | lapack |
| impact_analysis | "What would break if DGEMM were modified?" | blas |
| bug_pattern_search | "Are there any potential issues in the error handling?" | lapack |
| translation_hints | "How would DAXPY look in Python with NumPy?" | blas |
| code_explanation | "How are Fortran array intrinsics tested?" | gfortran |

These are suggestions — use your judgment to create queries that test realistic usage patterns.

#### How to Build the Dataset

1. **Start with queries you already ran** during G4-003/004/005/006/007 verification — you know what those returned.
2. **Look at actual file names** in the corpus to know what's available:
   ```bash
   # LAPACK routine names
   ls data/raw/lapack/lapack-source/SRC/*.f | head -20
   # BLAS routine names
   ls data/raw/blas/netlib-blas/BLAS-3.12.0/*.f | head -20
   ```
3. **Run the query** through the API to see what chunks come back, then record the expected file paths and names.
4. **Don't fabricate expected results** — run each query, inspect the response, and record what the system actually returns when it's working well.

### Phase 2: Evaluation Script

Implement `evaluation/evaluate.py` that:

1. Loads `evaluation/ground_truth.json`
2. For each query, calls the API (or the retrieval pipeline directly)
3. Checks if `expected_files` and `expected_names` appear in the top-5 retrieved chunks
4. Computes **precision@5**: fraction of queries where at least one expected file/name appears in top-5
5. Prints a summary report

#### Script Interface

```bash
# Run evaluation against deployed API
python evaluation/evaluate.py

# Or with a custom API URL
python evaluation/evaluate.py --api-url https://gauntlet-assignment-3.onrender.com

# Or against local server
python evaluation/evaluate.py --api-url http://localhost:8000
```

#### Implementation Skeleton

```python
"""LegacyLens retrieval evaluation script."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

DEFAULT_API_URL = "https://gauntlet-assignment-3.onrender.com"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


def load_ground_truth(path: Path) -> list[dict]:
    """Load ground truth queries from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data["queries"]


def run_query(api_url: str, query: dict) -> dict:
    """Execute a single query against the API."""
    response = requests.post(
        f"{api_url}/api/query",
        json={
            "query": query["query"],
            "codebase": query["codebase"],
            "feature": query["feature"],
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def evaluate_query(query: dict, response: dict) -> dict:
    """Check if expected files/names appear in top-5 chunks."""
    chunks = response.get("chunks", [])[:5]

    chunk_files = [c.get("file_path", "") for c in chunks]
    chunk_names = [c.get("name", "") for c in chunks]

    file_hit = any(
        any(expected in cf for cf in chunk_files)
        for expected in query["expected_files"]
    )
    name_hit = any(
        any(expected.upper() in cn.upper() for cn in chunk_names)
        for expected in query["expected_names"]
    )

    return {
        "id": query["id"],
        "query": query["query"],
        "codebase": query["codebase"],
        "feature": query["feature"],
        "file_hit": file_hit,
        "name_hit": name_hit,
        "hit": file_hit or name_hit,
        "chunks_returned": len(chunks),
        "confidence": response.get("confidence", "UNKNOWN"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LegacyLens retrieval evaluation")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dataset", default=str(GROUND_TRUTH_PATH))
    args = parser.parse_args()

    queries = load_ground_truth(Path(args.dataset))
    if not queries:
        print("No queries in ground truth dataset.")
        sys.exit(1)

    results = []
    for query in queries:
        print(f"  [{query['id']}] {query['query'][:60]}...", end=" ")
        try:
            response = run_query(args.api_url, query)
            result = evaluate_query(query, response)
            results.append(result)
            status = "HIT" if result["hit"] else "MISS"
            print(f"{status} (confidence={result['confidence']})")
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"id": query["id"], "hit": False, "error": str(exc)})

    # Summary
    total = len(results)
    hits = sum(1 for r in results if r.get("hit", False))
    precision = hits / total if total > 0 else 0.0

    print(f"\n{'='*50}")
    print(f"Precision@5: {precision:.1%} ({hits}/{total})")

    # Per-codebase breakdown
    codebases = sorted(set(q["codebase"] for q in queries))
    for cb in codebases:
        cb_results = [r for r in results if r.get("codebase") == cb]
        cb_hits = sum(1 for r in cb_results if r.get("hit", False))
        cb_total = len(cb_results)
        pct = cb_hits / cb_total if cb_total > 0 else 0.0
        print(f"  {cb}: {pct:.0%} ({cb_hits}/{cb_total})")

    print(f"{'='*50}")


if __name__ == "__main__":
    main()
```

#### Output Format

```
  [q001] How does DGETRF perform LU factorization?...     HIT (confidence=HIGH)
  [q002] What does DGEMM do for matrix multiplication?... HIT (confidence=HIGH)
  [q003] What paragraphs are called from the main pro...  MISS (confidence=MEDIUM)
  ...

==================================================
Precision@5: 84.0% (21/25)
  blas: 100% (5/5)
  gnucobol: 60% (3/5)
  gfortran: 80% (4/5)
  lapack: 100% (5/5)
  opencobol-contrib: 80% (4/5)
==================================================
```

### Phase 3: Run Evaluation

1. Run the evaluation script against the deployed API
2. Record the precision@5 score
3. If precision is below 70%, investigate the MISS queries and document findings
4. Record results in DEVLOG

---

## Deliverables Checklist

- [ ] `evaluation/ground_truth.json` populated with 25+ queries
- [ ] All 5 codebases represented (at least 3 queries each)
- [ ] At least 4 features represented
- [ ] `evaluation/evaluate.py` implemented with precision@5
- [ ] Evaluation run completed against deployed API
- [ ] Results recorded in DEVLOG (overall score + per-codebase)

### Files to Create/Modify

| File | Action |
|------|--------|
| `evaluation/ground_truth.json` | Populate with 25+ query/answer pairs |
| `evaluation/evaluate.py` | Implement evaluation script |
| `Docs/tickets/DEVLOG.md` | Add G4-008 entry with evaluation results |

### Files You Should NOT Modify

- Any source code in `src/` — this ticket evaluates the system, it doesn't change it
- Ingestion scripts or data files
- Config files

---

## Important Context

### API Contract

The `/api/query` endpoint accepts:

```json
{
  "query": "string (required)",
  "feature": "string (default: code_explanation)",
  "codebase": "string or null (default: null = search all)",
  "top_k": 10,
  "language": "cobol",
  "model": null
}
```

And returns:

```json
{
  "answer": "string",
  "chunks": [
    {
      "content": "string",
      "file_path": "string",
      "line_start": 0,
      "line_end": 0,
      "name": "string",
      "language": "string",
      "codebase": "string",
      "score": 0.0,
      "confidence": "HIGH|MEDIUM|LOW",
      "metadata": {}
    }
  ],
  "query": "string",
  "feature": "string",
  "confidence": "HIGH|MEDIUM|LOW",
  "codebase_filter": "string or null",
  "latency_ms": 0.0,
  "model": "string"
}
```

### Known Limitation

The `language` field in `QueryRequest` only accepts `"cobol"` (validated in `schemas.py`). Fortran codebase queries still work — they retrieve Fortran chunks correctly — but the prompt template uses COBOL-specific language guidance. This may slightly affect answer quality for Fortran queries. Document if observed but do not attempt to fix in this ticket.

### API URL

**Deployed:** `https://gauntlet-assignment-3.onrender.com`

Note: Render free tier has cold starts (~30s). The first query may be slow. Subsequent queries are fast.

---

## Definition of Done

- [ ] Ground truth dataset has 25+ queries across all 5 codebases and 4+ features
- [ ] Evaluation script runs end-to-end and produces precision@5 with per-codebase breakdown
- [ ] Evaluation results documented in DEVLOG
- [ ] No regressions in existing test suite
