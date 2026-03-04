#!/usr/bin/env python3
"""Run MVP-016 smoke test queries against the deployed API."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

API_URL = os.getenv("API_URL", "https://gauntlet-assignment-3.onrender.com")
QUERIES_PATH = Path(__file__).parent / "smoke_test_queries.json"
TIMEOUT = 90  # Cold start + LLM can be slow


def main() -> int:
    with open(QUERIES_PATH) as f:
        data = json.load(f)

    queries = data["queries"]
    codebase = data.get("codebase", "gnucobol")
    results: list[dict] = []

    for q in queries:
        payload = {
            "query": q["query"],
            "feature": q["feature"],
            "codebase": codebase,
        }
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                r = client.post(f"{API_URL}/api/query", json=payload)
            status = r.status_code
            body = r.json() if r.text else {}
            answer = body.get("answer", "")
            has_citations = ":" in answer and any(
                c.isdigit() for c in answer
            )  # heuristic: file:line
            passed = status == 200 and len(answer) > 0
            results.append(
                {
                    "id": q["id"],
                    "feature": q["feature"],
                    "query": q["query"],
                    "status": status,
                    "passed": passed,
                    "has_citations": has_citations,
                    "answer_preview": answer[:120] + "..." if len(answer) > 120 else answer,
                }
            )
            print(
                f"  {q['id']:2}. [{q['feature']}] status={status} "
                f"passed={passed} citations={has_citations}"
            )
        except httpx.TimeoutException:
            results.append(
                {
                    "id": q["id"],
                    "feature": q["feature"],
                    "query": q["query"],
                    "status": 0,
                    "passed": False,
                    "error": "timeout",
                }
            )
            print(f"  {q['id']:2}. [{q['feature']}] TIMEOUT")
        except Exception as e:
            results.append(
                {
                    "id": q["id"],
                    "feature": q["feature"],
                    "query": q["query"],
                    "status": 0,
                    "passed": False,
                    "error": str(e),
                }
            )
            print(f"  {q['id']:2}. [{q['feature']}] ERROR: {e}")

    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"\nPassed: {passed_count}/{len(queries)}")
    return 0 if passed_count >= 8 else 1


if __name__ == "__main__":
    sys.exit(main())
