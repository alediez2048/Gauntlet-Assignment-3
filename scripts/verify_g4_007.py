#!/usr/bin/env python3
"""G4-007: Multi-Codebase Query Verification — runs all phases and prints results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = "https://gauntlet-assignment-3.onrender.com"
TIMEOUT = 120.0  # Render cold start can take 60+ seconds


def phase1_counts() -> dict[str, int]:
    """Phase 1: Qdrant count verification."""
    from src.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_URL
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    counts: dict[str, int] = {}
    for cb in ["gnucobol", "gfortran", "lapack", "blas", "opencobol-contrib"]:
        r = client.count(
            collection_name=QDRANT_COLLECTION_NAME,
            count_filter=Filter(must=[FieldCondition(key="codebase", match=MatchValue(value=cb))]),
        )
        counts[cb] = r.count
    return counts


def phase2_4_queries(counts: dict[str, int]) -> dict:
    """Phase 2-4: Per-codebase, unfiltered, and multi-feature queries via API."""
    from src.api.client import ApiClientTransportError, post_query, QueryRequestPayload

    results: dict = {"phase2": {}, "phase3": {}, "phase4": {}}

    # Phase 2: Per-codebase filtered queries (skip gfortran if 0)
    phase2_specs = [
        ("gnucobol", "How does the PERFORM statement work?"),
        ("opencobol-contrib", "What COBOL sample programs are available?"),
        ("lapack", "How does DGETRF perform LU factorization?"),
        ("blas", "What does DGEMM do?"),
    ]
    for codebase, query in phase2_specs:
        if counts.get(codebase, 0) == 0:
            results["phase2"][codebase] = {"skipped": True, "reason": "count=0"}
            continue
        try:
            payload = QueryRequestPayload(query=query, codebase=codebase)
            resp = post_query(payload, base_url=API_URL, timeout_seconds=TIMEOUT)
            chunks_codebases = [c.codebase for c in resp.chunks if c.codebase]
            all_match = all(cb == codebase for cb in chunks_codebases)
            results["phase2"][codebase] = {
                "ok": True,
                "chunks_count": len(resp.chunks),
                "all_from_filtered_codebase": all_match,
                "confidence": resp.confidence.value,
                "answer_preview": resp.answer[:200] + "..." if len(resp.answer) > 200 else resp.answer,
            }
        except ApiClientTransportError as e:
            results["phase2"][codebase] = {"ok": False, "error": str(e)}
        except Exception as e:
            results["phase2"][codebase] = {"ok": False, "error": str(e)}

    # Phase 3: Unfiltered cross-codebase query
    try:
        payload = QueryRequestPayload(query="How is matrix multiplication implemented?")
        resp = post_query(payload, base_url=API_URL, timeout_seconds=TIMEOUT)
        codebases_in_results = list({c.codebase for c in resp.chunks if c.codebase})
        results["phase3"] = {
            "ok": True,
            "chunks_count": len(resp.chunks),
            "codebases_in_results": codebases_in_results,
            "multi_codebase": len(codebases_in_results) > 1,
        }
    except ApiClientTransportError as e:
        results["phase3"] = {"ok": False, "error": str(e)}
    except Exception as e:
        results["phase3"] = {"ok": False, "error": str(e)}

    # Phase 4: Multi-feature spot check (BLAS)
    phase4_queries = [
        ("code_explanation", "What does DAXPY do?"),
        ("dependency_mapping", "What does DAXPY do?"),
        ("translation_hints", "What does DAXPY do?"),
    ]
    for feature, query in phase4_queries:
        try:
            payload = QueryRequestPayload(
                query=query, codebase="blas", feature=feature
            )
            resp = post_query(payload, base_url=API_URL, timeout_seconds=TIMEOUT)
            results["phase4"][feature] = {
                "ok": True,
                "answer_preview": resp.answer[:150] + "..." if len(resp.answer) > 150 else resp.answer,
            }
        except ApiClientTransportError as e:
            results["phase4"][feature] = {"ok": False, "error": str(e)}
        except Exception as e:
            results["phase4"][feature] = {"ok": False, "error": str(e)}

    return results


def main() -> None:
    print("=== G4-007 Phase 1: Qdrant Counts ===")
    counts = phase1_counts()
    for cb, n in counts.items():
        print(f"  {cb}: {n}")
    print()

    print("=== G4-007 Phase 2-4: API Queries (deployed) ===")
    api_results = phase2_4_queries(counts)
    print(json.dumps(api_results, indent=2, default=str))
    print()

    # Summary for DEVLOG
    print("=== Summary ===")
    non_zero = sum(1 for n in counts.values() if n > 0)
    print(f"  Codebases with non-zero count: {non_zero}/5")
    p2_ok = sum(1 for v in api_results["phase2"].values() if isinstance(v, dict) and v.get("ok"))
    print(f"  Phase 2 passed: {p2_ok} codebases")
    print(f"  Phase 3 passed: {api_results['phase3'].get('ok', False)}")
    p4_ok = sum(1 for v in api_results["phase4"].values() if isinstance(v, dict) and v.get("ok"))
    print(f"  Phase 4 passed: {p4_ok}/3 features")


if __name__ == "__main__":
    main()
