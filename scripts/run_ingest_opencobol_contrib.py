"""Run OpenCOBOL contrib ingestion pipeline.

Defaults to full speed; optional throttling flags are available for
accounts that need smaller paced embedding batches.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.ingest import ingest_codebase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "opencobol-contrib"


def parse_args() -> argparse.Namespace:
    """Parse optional throttling arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest OpenCOBOL Contrib source into Qdrant."
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.0,
        help="Seconds between embedding sub-batches (default: 0.0).",
    )
    parser.add_argument(
        "--embed-sub-batch-size",
        type=int,
        default=128,
        help="Chunks per embedding sub-batch when throttling is enabled.",
    )
    return parser.parse_args()


def main() -> None:
    """Run ingestion and print final stats."""
    args = parse_args()
    mode = "full speed" if args.rate_limit_delay <= 0 else "throttled"
    print(f"Starting OpenCOBOL Contrib ingestion ({mode})...")
    print(f"Data directory: {DATA_DIR}")
    if args.rate_limit_delay > 0:
        print(
            "Throttling params: "
            f"rate_limit_delay={args.rate_limit_delay}, "
            f"embed_sub_batch_size={args.embed_sub_batch_size}"
        )

    stats = ingest_codebase(
        data_dir=DATA_DIR,
        codebase="opencobol-contrib",
        language="cobol",
        rate_limit_delay=args.rate_limit_delay,
        embed_sub_batch_size=args.embed_sub_batch_size,
    )

    print("\n=== INGESTION RESULTS ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
