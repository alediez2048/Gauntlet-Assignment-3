"""Fortran subroutine/function chunking and metadata enrichment for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import re

import tiktoken

from src.config import CHUNK_MAX_TOKENS, CHUNK_MIN_TOKENS, TIKTOKEN_ENCODING
from src.types.chunks import Chunk, ProcessedFile

_UNIT_HEADER_PATTERN = re.compile(
    r"^\s*"
    r"(?:(?:RECURSIVE|PURE|ELEMENTAL|IMPURE)\s+)?"
    r"(?:(?:INTEGER|REAL|DOUBLE\s+PRECISION|COMPLEX|CHARACTER|LOGICAL)\s+)?"
    r"(SUBROUTINE|FUNCTION|PROGRAM|MODULE|BLOCK\s+DATA)"
    r"\s+([A-Z_]\w*)",
    re.IGNORECASE,
)

_END_PATTERN = re.compile(
    r"^\s*END\s*(?:(SUBROUTINE|FUNCTION|PROGRAM|MODULE|BLOCK\s+DATA)\s*\w*)?\s*$",
    re.IGNORECASE,
)

_CALL_PATTERN = re.compile(r"\bCALL\s+(\w+)", re.IGNORECASE)
_USE_PATTERN = re.compile(r"\bUSE\s+(\w+)", re.IGNORECASE)
_INCLUDE_PATTERN = re.compile(r"\bINCLUDE\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)

_TOKENIZER: tiktoken.Encoding | None = None


@dataclass(frozen=True)
class _UnitBlock:
    """Internal representation of a Fortran program unit range."""

    name: str
    unit_type: str
    chunk_type: str
    line_start: int
    line_end: int


def _get_tokenizer() -> tiktoken.Encoding:
    """Return a cached tokenizer for chunk size accounting."""
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = tiktoken.get_encoding(TIKTOKEN_ENCODING)
    return _TOKENIZER


def _count_tokens(text: str) -> int:
    """Count tokens using the configured tokenizer."""
    if not text.strip():
        return 0
    try:
        tokenizer = _get_tokenizer()
        return len(tokenizer.encode(text))
    except (KeyError, ValueError):
        return len(text.split())


def _parse_unit_header(line: str) -> tuple[str, str] | None:
    """Extract (unit_type, unit_name) from a header line, or None."""
    match = _UNIT_HEADER_PATTERN.match(line)
    if match is None:
        return None
    raw_type = match.group(1).upper()
    unit_type = re.sub(r"\s+", " ", raw_type)
    unit_name = match.group(2).upper()
    return unit_type, unit_name


def _is_end_statement(line: str) -> bool:
    """Check if a line is an END statement that closes a program unit."""
    return _END_PATTERN.match(line) is not None


def _detect_unit_boundaries(lines: list[str]) -> list[_UnitBlock]:
    """Scan lines for program unit headers and END statements."""
    blocks: list[_UnitBlock] = []
    current_name: str | None = None
    current_type: str | None = None
    current_start: int | None = None

    for idx, line in enumerate(lines, start=1):
        parsed = _parse_unit_header(line)
        if parsed is not None:
            if current_name is not None and current_start is not None and current_type is not None:
                blocks.append(_UnitBlock(
                    name=current_name,
                    unit_type=current_type,
                    chunk_type=_unit_type_to_chunk_type(current_type),
                    line_start=current_start,
                    line_end=idx - 1,
                ))
            current_type, current_name = parsed
            current_start = idx
            continue

        if _is_end_statement(line) and current_name is not None:
            blocks.append(_UnitBlock(
                name=current_name,
                unit_type=current_type,  # type: ignore[arg-type]
                chunk_type=_unit_type_to_chunk_type(current_type),  # type: ignore[arg-type]
                line_start=current_start,  # type: ignore[arg-type]
                line_end=idx,
            ))
            current_name = None
            current_type = None
            current_start = None

    if current_name is not None and current_start is not None and current_type is not None:
        blocks.append(_UnitBlock(
            name=current_name,
            unit_type=current_type,
            chunk_type=_unit_type_to_chunk_type(current_type),
            line_start=current_start,
            line_end=len(lines),
        ))

    return blocks


def _unit_type_to_chunk_type(unit_type: str) -> str:
    """Map a Fortran unit type to a chunk_type string."""
    mapping: dict[str, str] = {
        "SUBROUTINE": "subroutine",
        "FUNCTION": "function",
        "PROGRAM": "program",
        "MODULE": "module",
        "BLOCK DATA": "block_data",
    }
    return mapping.get(unit_type, "file_block")


def _build_chunk_from_block(
    block: _UnitBlock,
    lines: list[str],
    file_path: str,
    codebase: str,
) -> Chunk:
    """Construct a Chunk from a unit block."""
    content = "\n".join(lines[block.line_start - 1: block.line_end])
    token_count = _count_tokens(content)
    return Chunk(
        content=content,
        file_path=file_path,
        line_start=block.line_start,
        line_end=block.line_end,
        chunk_type=block.chunk_type,
        language="fortran",
        codebase=codebase,
        name=block.name,
        division=block.unit_type,
        token_count=token_count,
    )


def _merge_chunk_names(left: str, right: str) -> str:
    """Merge unit names deterministically while preserving first-seen order."""
    merged: list[str] = []
    for value in left.split("+") + right.split("+"):
        name = value.strip()
        if name and name not in merged:
            merged.append(name)
    return "+".join(merged) if merged else "MERGED"


def _merge_chunk_pair(left: Chunk, right: Chunk) -> Chunk:
    """Merge two adjacent chunks."""
    merged_content = f"{left.content}\n{right.content}".strip()
    merged_name = _merge_chunk_names(left.name, right.name)
    merged_division = left.division if left.division == right.division else "MIXED"
    return Chunk(
        content=merged_content,
        file_path=left.file_path,
        line_start=min(left.line_start, right.line_start),
        line_end=max(left.line_end, right.line_end),
        chunk_type=left.chunk_type,
        language=left.language,
        codebase=left.codebase,
        name=merged_name,
        division=merged_division,
        token_count=_count_tokens(merged_content),
    )


def _merge_small_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Merge adjacent small chunks until minimum token threshold is met."""
    if not chunks:
        return []

    merged: list[Chunk] = []
    current = chunks[0]
    for candidate in chunks[1:]:
        if current.token_count < CHUNK_MIN_TOKENS:
            current = _merge_chunk_pair(current, candidate)
            continue
        merged.append(current)
        current = candidate
    merged.append(current)

    if len(merged) > 1 and merged[-1].token_count < CHUNK_MIN_TOKENS:
        tail = merged.pop()
        merged[-1] = _merge_chunk_pair(merged[-1], tail)

    return merged


def _split_long_line(line: str, max_tokens: int) -> list[str]:
    """Split a single oversized line on words as a last resort."""
    words = line.split()
    if not words:
        return [line]

    parts: list[str] = []
    current_words: list[str] = []
    for word in words:
        candidate_words = current_words + [word]
        candidate_text = " ".join(candidate_words)
        if current_words and _count_tokens(candidate_text) > max_tokens:
            parts.append(" ".join(current_words))
            current_words = [word]
            continue
        current_words = candidate_words
    if current_words:
        parts.append(" ".join(current_words))
    return parts


def _split_chunk_by_size(chunk: Chunk, max_tokens: int) -> list[Chunk]:
    """Split oversized chunk on line boundaries; fallback to word boundaries."""
    if chunk.token_count <= max_tokens:
        return [chunk]

    lines = chunk.content.splitlines()
    if not lines:
        return [chunk]

    split_chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_start_line = chunk.line_start

    for offset, line in enumerate(lines):
        absolute_line = chunk.line_start + offset
        candidate_lines = current_lines + [line]
        candidate_text = "\n".join(candidate_lines)

        if current_lines and _count_tokens(candidate_text) > max_tokens:
            split_content = "\n".join(current_lines)
            split_chunks.append(
                Chunk(
                    content=split_content,
                    file_path=chunk.file_path,
                    line_start=current_start_line,
                    line_end=absolute_line - 1,
                    chunk_type=chunk.chunk_type,
                    language=chunk.language,
                    codebase=chunk.codebase,
                    name=chunk.name,
                    division=chunk.division,
                    token_count=_count_tokens(split_content),
                )
            )
            current_lines = [line]
            current_start_line = absolute_line
            continue

        if not current_lines and _count_tokens(line) > max_tokens:
            line_parts = _split_long_line(line, max_tokens=max_tokens)
            start_suffix = len(split_chunks) + 1
            for index, part in enumerate(line_parts):
                split_chunks.append(
                    Chunk(
                        content=part,
                        file_path=chunk.file_path,
                        line_start=absolute_line,
                        line_end=absolute_line,
                        chunk_type=chunk.chunk_type,
                        language=chunk.language,
                        codebase=chunk.codebase,
                        name=f"{chunk.name}#{start_suffix + index}",
                        division=chunk.division,
                        token_count=_count_tokens(part),
                    )
                )
            current_lines = []
            current_start_line = absolute_line + 1
            continue

        current_lines = candidate_lines

    if current_lines:
        split_content = "\n".join(current_lines)
        split_chunks.append(
            Chunk(
                content=split_content,
                file_path=chunk.file_path,
                line_start=current_start_line,
                line_end=chunk.line_end,
                chunk_type=chunk.chunk_type,
                language=chunk.language,
                codebase=chunk.codebase,
                name=chunk.name,
                division=chunk.division,
                token_count=_count_tokens(split_content),
            )
        )

    for index, split_chunk in enumerate(split_chunks, start=1):
        if len(split_chunks) == 1:
            continue
        if "#" in split_chunk.name:
            continue
        split_chunk.name = f"{split_chunk.name}#{index}"

    return split_chunks


def _split_oversized_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Split oversized chunks and preserve existing compliant chunks."""
    final_chunks: list[Chunk] = []
    for chunk in chunks:
        final_chunks.extend(_split_chunk_by_size(chunk, max_tokens=CHUNK_MAX_TOKENS))
    return final_chunks


def _normalize_dependency(raw_value: str) -> str:
    """Normalize dependency token format."""
    compact = " ".join(raw_value.split())
    stripped = compact.strip().strip(".,;:").strip("\"'")
    return stripped.upper()


def _append_dependency(
    dependencies: list[str],
    seen: set[str],
    raw_value: str,
    preserve_case: bool = False,
) -> None:
    """Append normalized dependency while preserving first-seen ordering."""
    if preserve_case:
        compact = " ".join(raw_value.split())
        normalized = compact.strip().strip(".,;:").strip("\"'")
    else:
        normalized = _normalize_dependency(raw_value)
    if not normalized:
        return
    lookup_key = normalized.upper()
    if lookup_key in seen:
        return
    seen.add(lookup_key)
    dependencies.append(normalized)


def _extract_dependencies(chunk_text: str) -> list[str]:
    """Extract CALL/USE/INCLUDE dependencies from chunk text."""
    dependencies: list[str] = []
    seen: set[str] = set()

    for match in _USE_PATTERN.finditer(chunk_text):
        _append_dependency(dependencies, seen, match.group(1))

    for match in _INCLUDE_PATTERN.finditer(chunk_text):
        _append_dependency(dependencies, seen, match.group(1), preserve_case=True)

    for match in _CALL_PATTERN.finditer(chunk_text):
        _append_dependency(dependencies, seen, match.group(1))

    return dependencies


def _build_chunk_metadata(chunk: Chunk) -> dict[str, str | int]:
    """Build metadata payload required by retrieval/indexing contracts."""
    return {
        "paragraph_name": chunk.name,
        "division": chunk.division,
        "file_path": chunk.file_path,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "chunk_type": chunk.chunk_type,
        "language": chunk.language,
        "codebase": chunk.codebase,
    }


def _enrich_chunk(chunk: Chunk) -> Chunk:
    """Enrich chunk with dependency list and metadata payload."""
    chunk.dependencies = _extract_dependencies(chunk.content)
    chunk.metadata = _build_chunk_metadata(chunk)
    return chunk


def chunk_fortran(
    processed_file: ProcessedFile,
    codebase: str = "gfortran",
) -> list[Chunk]:
    """Chunk preprocessed Fortran source on program unit boundaries.

    Detects SUBROUTINE, FUNCTION, PROGRAM, MODULE, and BLOCK DATA
    boundaries, then normalizes to satisfy adaptive token size constraints,
    and finally enriches with dependency and metadata fields needed by
    retrieval and citation layers.
    """
    if not processed_file.code.strip():
        return []

    lines = processed_file.code.splitlines()
    blocks = _detect_unit_boundaries(lines)

    if not blocks:
        fallback_content = processed_file.code
        fallback_chunk = Chunk(
            content=fallback_content,
            file_path=processed_file.file_path,
            line_start=1,
            line_end=len(lines),
            chunk_type="file_block",
            language="fortran",
            codebase=codebase,
            name="FILE-BLOCK",
            division="UNKNOWN",
            token_count=_count_tokens(fallback_content),
        )
        sized = _split_oversized_chunks([fallback_chunk])
        return [_enrich_chunk(chunk) for chunk in sized]

    initial_chunks: list[Chunk] = []

    first_block = blocks[0]
    if first_block.line_start > 1:
        gap_content = "\n".join(lines[: first_block.line_start - 1])
        if gap_content.strip():
            initial_chunks.append(Chunk(
                content=gap_content,
                file_path=processed_file.file_path,
                line_start=1,
                line_end=first_block.line_start - 1,
                chunk_type="file_block",
                language="fortran",
                codebase=codebase,
                name="FILE-BLOCK",
                division="UNKNOWN",
                token_count=_count_tokens(gap_content),
            ))

    for i, block in enumerate(blocks):
        initial_chunks.append(
            _build_chunk_from_block(
                block=block,
                lines=lines,
                file_path=processed_file.file_path,
                codebase=codebase,
            )
        )

        if i + 1 < len(blocks):
            gap_start = block.line_end + 1
            gap_end = blocks[i + 1].line_start - 1
            if gap_start <= gap_end:
                gap_content = "\n".join(lines[gap_start - 1: gap_end])
                if gap_content.strip():
                    initial_chunks.append(Chunk(
                        content=gap_content,
                        file_path=processed_file.file_path,
                        line_start=gap_start,
                        line_end=gap_end,
                        chunk_type="file_block",
                        language="fortran",
                        codebase=codebase,
                        name="FILE-BLOCK",
                        division="UNKNOWN",
                        token_count=_count_tokens(gap_content),
                    ))

    last_block = blocks[-1]
    if last_block.line_end < len(lines):
        tail_content = "\n".join(lines[last_block.line_end:])
        if tail_content.strip():
            initial_chunks.append(Chunk(
                content=tail_content,
                file_path=processed_file.file_path,
                line_start=last_block.line_end + 1,
                line_end=len(lines),
                chunk_type="file_block",
                language="fortran",
                codebase=codebase,
                name="FILE-BLOCK",
                division="UNKNOWN",
                token_count=_count_tokens(tail_content),
            ))

    merged_chunks = _merge_small_chunks(initial_chunks)
    sized_chunks = _split_oversized_chunks(merged_chunks)

    return [_enrich_chunk(chunk) for chunk in sized_chunks]
