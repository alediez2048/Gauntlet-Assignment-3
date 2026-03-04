"""Compute average token count per chunk to size batches optimally."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.detector import detect_language, is_supported_source_file
from src.ingestion.fortran_chunker import chunk_fortran
from src.ingestion.fortran_parser import preprocess_fortran

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "gfortran"

logging.disable(logging.CRITICAL)

total_tokens = 0
total_chunks = 0
file_count = 0

for fp in sorted(DATA_DIR.rglob("*")):
    if not fp.is_file() or not is_supported_source_file(fp):
        continue
    if detect_language(fp) != "fortran":
        continue
    file_count += 1
    if file_count > 200:
        break
    try:
        pf = preprocess_fortran(fp, codebase="gfortran")
        if not pf.code.strip():
            continue
        chunks = chunk_fortran(pf, codebase="gfortran")
        for c in chunks:
            total_tokens += c.token_count
            total_chunks += 1
    except Exception:
        pass

avg = total_tokens / total_chunks if total_chunks else 0
print(f"Sampled {total_chunks} chunks from first 500 files")
print(f"Total tokens: {total_tokens}")
print(f"Average tokens/chunk: {avg:.1f}")
print(f"\n10K TPM budget fits: {int(10_000 / avg)} chunks per minute" if avg > 0 else "")
print(f"3 RPM budget fits: 3 batches of {int(10_000 / avg / 3)} per minute" if avg > 0 else "")
