"""Run full gfortran ingestion pipeline with rate limiting.

Uses a subset of the gfortran test suite to stay within Voyage free tier
rate limits while still meeting corpus requirements (200+ files, 10K+ LOC).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.ingest import ingest_codebase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "gfortran"


def main() -> None:
    print("Starting gfortran ingestion (rate-limited mode, 500 files)...")
    print(f"Data directory: {DATA_DIR}")
    stats = ingest_codebase(
        data_dir=DATA_DIR,
        codebase="gfortran",
        language="fortran",
        rate_limit_delay=65.0,
        embed_sub_batch_size=10,
        max_files=500,
    )
    print("\n=== INGESTION RESULTS ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
