"""LegacyLens retrieval evaluation script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_API_URL = "https://gauntlet-assignment-3.onrender.com"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


def load_ground_truth(path: Path) -> list[dict]:
    """Load ground truth queries from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data["queries"]


def run_query(api_url: str, query: dict) -> dict:
    """Execute a single query against the API."""
    with httpx.Client(timeout=90) as client:
        response = client.post(
            f"{api_url.rstrip('/')}/api/query",
            json={
                "query": query["query"],
                "codebase": query["codebase"],
                "feature": query["feature"],
            },
        )
    response.raise_for_status()
    return response.json()


def evaluate_query(query: dict, response: dict) -> dict:
    """Check if expected files/names appear in top-5 chunks."""
    chunks = response.get("chunks", [])[:5]

    chunk_files = [c.get("file_path", "") for c in chunks]
    chunk_names = [c.get("name", "") for c in chunks]

    file_hit = (
        any(
            any(expected in cf for cf in chunk_files)
            for expected in query["expected_files"]
        )
        if query.get("expected_files")
        else False
    )
    name_hit = (
        any(
            any(expected.upper() in cn.upper() for cn in chunk_names)
            for expected in query["expected_names"]
        )
        if query.get("expected_names")
        else False
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
        "confidence": str(response.get("confidence", "UNKNOWN")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LegacyLens retrieval evaluation"
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dataset", default=str(GROUND_TRUTH_PATH))
    args = parser.parse_args()

    queries = load_ground_truth(Path(args.dataset))
    if not queries:
        print("No queries in ground truth dataset.")
        sys.exit(1)

    results = []
    for query in queries:
        q_preview = query["query"][:60] + ("..." if len(query["query"]) > 60 else "")
        print(f"  [{query['id']}] {q_preview}...", end=" ", flush=True)
        try:
            response = run_query(args.api_url, query)
            result = evaluate_query(query, response)
            results.append(result)
            status = "HIT" if result["hit"] else "MISS"
            print(f"{status} (confidence={result['confidence']})")
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append(
                {
                    "id": query["id"],
                    "codebase": query.get("codebase"),
                    "hit": False,
                    "error": str(exc),
                }
            )

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
