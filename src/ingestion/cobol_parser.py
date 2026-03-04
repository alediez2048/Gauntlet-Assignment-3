"""COBOL preprocessor — transforms raw COBOL source into clean ProcessedFile.

Handles the fixed-format column layout inherited from 80-column punch cards:
- Cols 1-6:  sequence numbers (stripped)
- Col 7:    indicator (* / D - for comments/continuations)
- Cols 8-72: code area (preserved)
- Cols 73-80: identification area (stripped)

Also handles modern GnuCOBOL *> free-format inline comments.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chardet

from src.types.chunks import ProcessedFile

logger = logging.getLogger(__name__)

_ENCODING_CONFIDENCE_THRESHOLD = 0.7

_COMMENT_INDICATORS = frozenset({"*", "/", "D", "d"})

_DIVISION_KEYWORDS = (
    "IDENTIFICATION DIVISION",
    "ENVIRONMENT DIVISION",
    "DATA DIVISION",
    "PROCEDURE DIVISION",
)


def _is_probably_binary(raw_bytes: bytes) -> bool:
    """Return True when bytes look like binary data instead of source text."""
    if not raw_bytes:
        return False
    if b"\x00" in raw_bytes:
        return True

    text_like_count = 0
    for value in raw_bytes:
        if value in (9, 10, 13) or 32 <= value <= 126:
            text_like_count += 1

    return (text_like_count / len(raw_bytes)) < 0.75


def _detect_encoding(raw_bytes: bytes, file_path: str) -> str | None:
    """Detect file encoding via chardet, returning None if confidence is too low."""
    if not raw_bytes:
        return "utf-8"

    if _is_probably_binary(raw_bytes):
        logger.warning("Binary-like file content for %s — skipping", file_path)
        return None

    try:
        raw_bytes.decode("ascii")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    detection = chardet.detect(raw_bytes)
    confidence: float = detection.get("confidence", 0.0) or 0.0
    encoding: str | None = detection.get("encoding")

    if encoding is None:
        logger.warning(
            "Encoding not detected for %s (confidence %.2f) — skipping",
            file_path,
            confidence,
        )
        return None

    if confidence < _ENCODING_CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low confidence encoding for %s: %s (%.2f) — skipping",
            file_path,
            encoding,
            confidence,
        )
        return None

    return encoding or "utf-8"


def _find_divisions(code: str) -> list[str]:
    """Scan cleaned code for COBOL division headers."""
    found: list[str] = []
    upper = code.upper()
    for kw in _DIVISION_KEYWORDS:
        if kw in upper:
            found.append(kw.split()[0])
    return found


def _process_line(
    line: str,
    code_lines: list[str],
    comments: list[str],
) -> None:
    """Process a single raw COBOL line, mutating code_lines and comments in place."""
    if len(line) < 7:
        code_lines.append(line)
        return

    indicator = line[6]

    code_area = line[7:72]

    if indicator in _COMMENT_INDICATORS:
        comment_text = code_area.strip()
        if comment_text:
            comments.append(comment_text)
        return

    if indicator == "-":
        if code_lines:
            continuation_text = line[11:72].lstrip()
            code_lines[-1] = code_lines[-1].rstrip() + continuation_text
        return

    if "*>" in code_area:
        code_part, _, comment_part = code_area.partition("*>")
        code_lines.append(code_part.rstrip())
        comment_text = comment_part.strip()
        if comment_text:
            comments.append(comment_text)
        return

    code_lines.append(code_area)


def preprocess_cobol(
    file_path: str | Path,
    codebase: str = "gnucobol",
) -> ProcessedFile:
    """Transform a raw COBOL source file into a clean ProcessedFile.

    Reads the file as raw bytes, detects encoding via chardet, strips
    column-based formatting artifacts, separates comments from code,
    and handles continuation lines.

    Args:
        file_path: Path to the raw COBOL source file.
        codebase: Name of the codebase this file belongs to.

    Returns:
        A ProcessedFile with cleaned code, extracted comments, and metadata.
    """
    path = Path(file_path)
    path_str = str(file_path)

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        logger.error("Cannot read file: %s", path_str)
        return ProcessedFile(
            code="",
            comments=[],
            language="cobol",
            file_path=path_str,
            encoding="utf-8",
        )

    if not raw_bytes:
        return ProcessedFile(
            code="",
            comments=[],
            language="cobol",
            file_path=path_str,
            encoding="utf-8",
        )

    encoding = _detect_encoding(raw_bytes, path_str)
    if encoding is None:
        return ProcessedFile(
            code="",
            comments=[],
            language="cobol",
            file_path=path_str,
            encoding="utf-8",
        )

    text = raw_bytes.decode(encoding, errors="replace")

    code_lines: list[str] = []
    comments: list[str] = []

    for line in text.splitlines():
        _process_line(line, code_lines, comments)

    code = "\n".join(code_lines)

    divisions = _find_divisions(code)
    metadata: dict[str, str] = {"codebase": codebase}
    if divisions:
        metadata["divisions_found"] = ",".join(divisions)

    return ProcessedFile(
        code=code,
        comments=comments,
        language="cobol",
        file_path=path_str,
        encoding=encoding,
        metadata=metadata,
    )
