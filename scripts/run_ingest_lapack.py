"""Run full LAPACK ingestion pipeline at full speed (no rate limiting)."""
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

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "lapack"


def main() -> None:
    print("Starting LAPACK ingestion (full speed)...")
    print(f"Data directory: {DATA_DIR}")
    stats = ingest_codebase(
        data_dir=DATA_DIR,
        codebase="lapack",
        language="fortran",
    )
    print("\n=== INGESTION RESULTS ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
