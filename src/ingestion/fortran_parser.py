"""Fortran preprocessor — transforms raw Fortran source into clean ProcessedFile.

Handles two source formats:

Fixed-form (Fortran 77 and earlier):
- Col 1:     Comment indicator (C, c, * → comment line)
- Cols 1-5:  Label/statement number field (stripped)
- Col 6:     Continuation column (non-blank, non-zero → continuation)
- Cols 7-72: Statement field (actual code — preserved)
- Cols 73+:  Identification field (stripped)

Free-form (Fortran 90+):
- No column restrictions; lines up to 132 characters
- ! anywhere on line starts an inline comment
- & at end of line means continuation on next line
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import chardet

from src.types.chunks import ProcessedFile

logger = logging.getLogger(__name__)

_ENCODING_CONFIDENCE_THRESHOLD = 0.7

_FIXED_COMMENT_INDICATORS = frozenset({"C", "c", "*"})

_FIXED_EXTENSIONS = frozenset({".f", ".f77"})
_FREE_EXTENSIONS = frozenset({".f90", ".f95"})

_PROGRAM_UNIT_PATTERN = re.compile(
    r"\b(PROGRAM|SUBROUTINE|FUNCTION|MODULE|BLOCK\s+DATA)\b",
    re.IGNORECASE,
)


def _detect_encoding(raw_bytes: bytes, file_path: str) -> str | None:
    """Detect file encoding via chardet, returning None if confidence is too low."""
    if not raw_bytes:
        return "utf-8"

    # Fast path: pure ASCII bytes are always valid UTF-8 source text.
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
            "chardet could not determine encoding for %s — skipping",
            file_path,
        )
        return None

    normalized = encoding.lower().replace("-", "").replace("_", "")
    if normalized == "utf7":
        logger.info(
            "Overriding chardet utf-7 detection to utf-8 for %s",
            file_path,
        )
        return "utf-8"

    if confidence < _ENCODING_CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low confidence encoding for %s: %s (%.2f) — skipping",
            file_path,
            encoding,
            confidence,
        )
        return None

    return encoding


def _detect_source_format(file_path: Path, lines: list[str]) -> str:
    """Determine fixed vs free form using extension default + heuristic override.

    Extension takes priority. Heuristic signals are logged as warnings if they
    conflict with the extension default, but do not override.
    """
    ext = file_path.suffix.lower()

    if ext in _FIXED_EXTENSIONS:
        extension_format = "fixed"
    elif ext in _FREE_EXTENSIONS:
        extension_format = "free"
    else:
        extension_format = "free"

    fixed_signals = 0
    free_signals = 0

    non_blank_lines = [ln for ln in lines if ln.strip()][:20]

    for line in non_blank_lines:
        if len(line) >= 1 and line[0] in _FIXED_COMMENT_INDICATORS:
            fixed_signals += 1

        if len(line) >= 6 and line[5] not in (" ", "0", "") and line[0] == " ":
            fixed_signals += 1

        stripped = line.rstrip()
        if "!" in stripped:
            code_before = stripped.split("!")[0]
            if code_before.strip():
                free_signals += 1

        if stripped.endswith("&"):
            free_signals += 1

        code_content = stripped
        if len(code_content) > 72:
            free_signals += 1

    if extension_format == "fixed" and free_signals > fixed_signals > 0:
        logger.warning(
            "Heuristic signals suggest free-form for %s but extension says fixed — trusting extension",
            file_path,
        )
    elif extension_format == "free" and fixed_signals > free_signals > 0:
        logger.warning(
            "Heuristic signals suggest fixed-form for %s but extension says free — trusting extension",
            file_path,
        )

    return extension_format


def _process_fixed_line(
    line: str,
    code_lines: list[str],
    comments: list[str],
) -> None:
    """Process a single fixed-form Fortran line."""
    if not line:
        code_lines.append("")
        return

    if len(line) < 1:
        code_lines.append(line)
        return

    if line[0] in _FIXED_COMMENT_INDICATORS:
        comment_text = line[1:].strip() if len(line) > 1 else ""
        if comment_text:
            comments.append(comment_text)
        return

    if len(line) < 7:
        code_lines.append(line.strip())
        return

    if line[5] not in (" ", "0", ""):
        continuation_text = line[6:72].rstrip()
        if code_lines:
            code_lines[-1] = code_lines[-1].rstrip() + continuation_text
        else:
            code_lines.append(continuation_text)
        return

    code_area = line[6:72].rstrip()
    code_lines.append(code_area)


def _process_free_line(
    line: str,
    code_lines: list[str],
    comments: list[str],
    in_continuation: list[bool],
) -> None:
    """Process a single free-form Fortran line."""
    stripped = line.rstrip()

    if "!" in stripped:
        excl_idx = stripped.index("!")
        code_part = stripped[:excl_idx].rstrip()
        comment_text = stripped[excl_idx + 1:].strip()

        if comment_text:
            comments.append(comment_text)

        if not code_part.strip():
            return

        stripped = code_part

    is_continuation = in_continuation[0]
    in_continuation[0] = False

    if stripped.endswith("&"):
        stripped = stripped[:-1].rstrip()
        in_continuation[0] = True

    if stripped.startswith("&"):
        stripped = stripped[1:].lstrip()

    if is_continuation and code_lines:
        code_lines[-1] = code_lines[-1].rstrip() + " " + stripped
    else:
        code_lines.append(stripped)


def _find_program_units(code: str) -> list[str]:
    """Scan cleaned code for Fortran program unit keywords."""
    found: list[str] = []
    seen: set[str] = set()

    for match in _PROGRAM_UNIT_PATTERN.finditer(code):
        keyword = match.group(1).upper()
        normalized = re.sub(r"\s+", " ", keyword)
        if normalized not in seen:
            seen.add(normalized)
            found.append(normalized)

    return found


def preprocess_fortran(
    file_path: str | Path,
    codebase: str = "gfortran",
) -> ProcessedFile:
    """Transform a raw Fortran source file into a clean ProcessedFile.

    Reads the file as raw bytes, detects encoding via chardet, determines
    fixed vs free form, strips formatting artifacts, separates comments
    from code, and handles continuation lines.

    Args:
        file_path: Path to the raw Fortran source file.
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
            language="fortran",
            file_path=path_str,
            encoding="utf-8",
        )

    if not raw_bytes:
        return ProcessedFile(
            code="",
            comments=[],
            language="fortran",
            file_path=path_str,
            encoding="utf-8",
        )

    encoding = _detect_encoding(raw_bytes, path_str)
    if encoding is None:
        return ProcessedFile(
            code="",
            comments=[],
            language="fortran",
            file_path=path_str,
            encoding="utf-8",
        )

    text = raw_bytes.decode(encoding, errors="replace")
    lines = text.splitlines()

    source_format = _detect_source_format(path, lines)

    code_lines: list[str] = []
    comments: list[str] = []

    if source_format == "fixed":
        for line in lines:
            _process_fixed_line(line, code_lines, comments)
    else:
        in_continuation: list[bool] = [False]
        for line in lines:
            _process_free_line(line, code_lines, comments, in_continuation)

    code = "\n".join(code_lines)

    units = _find_program_units(code)
    metadata: dict[str, str] = {
        "codebase": codebase,
        "source_format": source_format,
    }
    if units:
        metadata["units_found"] = ",".join(units)

    return ProcessedFile(
        code=code,
        comments=comments,
        language="fortran",
        file_path=path_str,
        encoding=encoding,
        metadata=metadata,
    )
