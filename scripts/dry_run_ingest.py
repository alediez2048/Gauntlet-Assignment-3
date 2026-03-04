"""Dry-run ingestion: discover, preprocess, chunk — without embedding or indexing.

Reports chunk count so we can estimate embedding cost before committing.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.detector import detect_language, is_supported_source_file
from src.ingestion.fortran_chunker import chunk_fortran
from src.ingestion.fortran_parser import preprocess_fortran

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "gfortran"
CODEBASE = "gfortran"
LANGUAGE = "fortran"


def main() -> None:
    files: list[Path] = []
    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file():
            continue
        if not is_supported_source_file(path):
            continue
        if detect_language(path) == LANGUAGE:
            files.append(path)

    print(f"Discovered {len(files)} {LANGUAGE} files")

    total_chunks = 0
    files_processed = 0
    errors = 0
    skipped_empty = 0

    for i, fp in enumerate(files):
        if i % 500 == 0 and i > 0:
            print(f"  ... processed {i}/{len(files)} files, {total_chunks} chunks so far")
        try:
            pf = preprocess_fortran(fp, codebase=CODEBASE)
            if not pf.code.strip():
                skipped_empty += 1
                continue
            chunks = chunk_fortran(pf, codebase=CODEBASE)
            total_chunks += len(chunks)
            files_processed += 1
        except Exception as exc:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {fp}: {exc}")

    print("\n=== DRY RUN RESULTS ===")
    print(f"Files discovered:  {len(files)}")
    print(f"Files processed:   {files_processed}")
    print(f"Files skipped:     {skipped_empty}")
    print(f"Errors:            {errors}")
    print(f"Total chunks:      {total_chunks}")
    print(f"\nEstimated embedding calls: {(total_chunks + 127) // 128}")
    print("(at 128 texts per Voyage API call)")


if __name__ == "__main__":
    main()
