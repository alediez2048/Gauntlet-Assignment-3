"""Reusable ingestion pipeline for legacy codebases (G4-003).

Orchestrates the full pipeline: discover → preprocess → chunk → embed → index.
Supports both COBOL and Fortran codebases via language-aware dispatch.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from src.ingestion.cobol_chunker import chunk_cobol
from src.ingestion.cobol_parser import preprocess_cobol
from src.ingestion.detector import detect_language, is_supported_source_file
from src.ingestion.embedder import embed_chunks
from src.ingestion.fortran_chunker import chunk_fortran
from src.ingestion.fortran_parser import preprocess_fortran
from src.ingestion.indexer import index_chunks
from src.types.chunks import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)


def discover_files(data_dir: Path, language: str) -> list[Path]:
    """Find all supported source files for a given language.

    Args:
        data_dir: Root directory to scan recursively.
        language: Target language to filter by (``"cobol"`` or ``"fortran"``).

    Returns:
        Sorted list of file paths matching the requested language.
    """
    files: list[Path] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        if not is_supported_source_file(path):
            continue
        detected = detect_language(path)
        if detected == language:
            files.append(path)
    return files


def _embed_with_rate_limit(
    chunks: list[Chunk],
    sub_batch_size: int = 20,
    delay_seconds: float = 25.0,
    max_retries: int = 5,
) -> list[EmbeddedChunk]:
    """Embed chunks in sub-batches with delays for rate-limited APIs.

    Calls embed_chunks on smaller groups with pauses to stay within
    API rate limits (e.g. Voyage free tier: 3 RPM, 10K TPM).
    Retries with exponential backoff on rate limit errors.
    """
    if not chunks:
        return []

    all_embedded: list[EmbeddedChunk] = []
    total_batches = (len(chunks) + sub_batch_size - 1) // sub_batch_size

    for i in range(0, len(chunks), sub_batch_size):
        batch_num = i // sub_batch_size + 1
        sub_batch = chunks[i : i + sub_batch_size]
        logger.info(
            "Embedding sub-batch %d/%d (%d chunks)",
            batch_num,
            total_batches,
            len(sub_batch),
        )

        backoff = delay_seconds
        for attempt in range(1, max_retries + 1):
            try:
                embedded = embed_chunks(sub_batch)
                all_embedded.extend(embedded)
                break
            except Exception as exc:
                exc_str = str(exc).lower()
                is_rate_limit = (
                    "rate" in exc_str
                    or "ratelimit" in exc_str
                    or "429" in exc_str
                    or "too many" in exc_str
                )
                if is_rate_limit and attempt < max_retries:
                    logger.warning(
                        "Rate limited on sub-batch %d (attempt %d/%d), "
                        "waiting %.0fs before retry",
                        batch_num,
                        attempt,
                        max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 120.0)
                else:
                    raise

        if i + sub_batch_size < len(chunks):
            logger.info("Rate limit pause: %.0fs", delay_seconds)
            time.sleep(delay_seconds)

    return all_embedded


def _preprocess_and_chunk(
    file_path: Path,
    codebase: str,
    language: str,
) -> list[Chunk]:
    """Run preprocessing and chunking for a single file.

    Dispatches to the correct language pipeline based on the ``language``
    parameter.

    Returns:
        List of chunks produced from the file, possibly empty.

    Raises:
        Any exception from the preprocessor or chunker is propagated to
        the caller for error handling.
    """
    if language == "cobol":
        processed = preprocess_cobol(file_path, codebase=codebase)
        if not processed.code.strip():
            return []
        return chunk_cobol(processed, codebase=codebase)
    elif language == "fortran":
        processed = preprocess_fortran(file_path, codebase=codebase)
        if not processed.code.strip():
            return []
        return chunk_fortran(processed, codebase=codebase)
    else:
        logger.warning("Unsupported language '%s' for %s", language, file_path)
        return []


def ingest_codebase(
    data_dir: str | Path,
    codebase: str,
    language: str,
    rate_limit_delay: float = 0.0,
    embed_sub_batch_size: int = 128,
    max_files: int = 0,
) -> dict[str, int]:
    """Run the full ingestion pipeline for a codebase directory.

    Discovers source files, preprocesses each one, chunks, embeds in
    batch, and indexes into Qdrant. Files that fail preprocessing are
    skipped with a logged warning rather than aborting the pipeline.

    Args:
        data_dir: Path to the directory containing raw source files.
        codebase: Codebase identifier (e.g. ``"gfortran"``, ``"gnucobol"``).
        language: Language identifier (``"cobol"`` or ``"fortran"``).
        rate_limit_delay: Seconds to pause between embedding sub-batches.
            Set > 0 to stay within API rate limits.
        embed_sub_batch_size: Number of chunks per embedding sub-batch
            when rate limiting is active.
        max_files: Maximum number of files to process. 0 means no limit.

    Returns:
        Dict with keys: ``files_found``, ``files_processed``,
        ``chunks_created``, ``chunks_embedded``, ``chunks_indexed``,
        ``errors``, ``skipped_empty``.
    """
    data_path = Path(data_dir)
    stats: dict[str, int] = {
        "files_found": 0,
        "files_processed": 0,
        "chunks_created": 0,
        "chunks_embedded": 0,
        "chunks_indexed": 0,
        "errors": 0,
        "skipped_empty": 0,
    }

    source_files = discover_files(data_path, language)
    stats["files_found"] = len(source_files)

    if max_files > 0 and len(source_files) > max_files:
        logger.info(
            "Limiting to %d of %d discovered files",
            max_files,
            len(source_files),
        )
        source_files = source_files[:max_files]

    if not source_files:
        logger.info(
            "No %s files found in %s — nothing to ingest", language, data_path
        )
        return stats

    logger.info(
        "Discovered %d %s files in %s for codebase '%s'",
        len(source_files),
        language,
        data_path,
        codebase,
    )

    all_chunks: list[Chunk] = []

    for file_path in source_files:
        try:
            chunks = _preprocess_and_chunk(file_path, codebase, language)
            if not chunks:
                stats["skipped_empty"] += 1
                continue
            all_chunks.extend(chunks)
            stats["files_processed"] += 1
        except Exception as exc:
            logger.warning("Failed to process %s: %s", file_path, exc)
            stats["errors"] += 1

    stats["chunks_created"] = len(all_chunks)

    if not all_chunks:
        logger.info("No chunks produced — skipping embedding and indexing")
        return stats

    logger.info(
        "Embedding %d chunks from %d files",
        len(all_chunks),
        stats["files_processed"],
    )

    if rate_limit_delay > 0:
        embedded = _embed_with_rate_limit(
            all_chunks,
            sub_batch_size=embed_sub_batch_size,
            delay_seconds=rate_limit_delay,
        )
    else:
        embedded = embed_chunks(all_chunks)
    stats["chunks_embedded"] = len(embedded)

    logger.info("Indexing %d embedded chunks into Qdrant", len(embedded))

    indexed_count = index_chunks(embedded)
    stats["chunks_indexed"] = indexed_count

    logger.info(
        "Ingestion complete for '%s': %d files → %d chunks → %d indexed",
        codebase,
        stats["files_processed"],
        stats["chunks_created"],
        stats["chunks_indexed"],
    )

    return stats
