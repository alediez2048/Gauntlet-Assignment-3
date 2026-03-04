"""COBOL paragraph chunking and metadata enrichment for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import re

import tiktoken

from src.config import CHUNK_MAX_TOKENS, CHUNK_MIN_TOKENS, TIKTOKEN_ENCODING
from src.types.chunks import Chunk, ProcessedFile

_DIVISION_HEADERS = frozenset(
    {
        "IDENTIFICATION DIVISION",
        "ENVIRONMENT DIVISION",
        "DATA DIVISION",
        "PROCEDURE DIVISION",
    }
)

_PARAGRAPH_NAME_PATTERN = re.compile(r"^[A-Z0-9-]+$")
_PERFORM_THRU_PATTERN = re.compile(
    r"\bPERFORM\b\s+([A-Z0-9-]+)\s+\bTHRU\b\s+([A-Z0-9-]+)",
    re.IGNORECASE,
)
_PERFORM_PATTERN = re.compile(
    r"\bPERFORM\b\s+([A-Z0-9-]+)\b(?!\s+\bTHRU\b)",
    re.IGNORECASE,
)
_CALL_PATTERN = re.compile(r"\bCALL\b\s+[\"']?([A-Z0-9-_]+)[\"']?", re.IGNORECASE)
_COPY_PATTERN = re.compile(r"\bCOPY\b\s+([A-Z0-9-_]+)", re.IGNORECASE)

_TOKENIZER: tiktoken.Encoding | None = None


@dataclass(frozen=True)
class _ParagraphBlock:
    """Internal representation of paragraph/fallback ranges before sizing rules."""

    name: str
    line_start: int
    line_end: int
    division: str


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


def _extract_division_name(line: str) -> str | None:
    """Extract division name from lines like 'PROCEDURE DIVISION.'."""
    stripped = line.strip().upper()
    if not stripped.endswith("DIVISION."):
        return None
    candidate = stripped[:-1]
    if candidate in _DIVISION_HEADERS:
        return candidate.split()[0]
    return None


def _find_procedure_division_start(lines: list[str]) -> int | None:
    """Return 1-indexed line number for PROCEDURE DIVISION, if present."""
    for idx, line in enumerate(lines, start=1):
        division = _extract_division_name(line)
        if division == "PROCEDURE":
            return idx
    return None


def _is_paragraph_header(line: str) -> bool:
    """Heuristic paragraph detection for cleaned COBOL code lines."""
    if not line:
        return False
    if line[0].isspace():
        return False

    stripped = line.strip()
    if not stripped.endswith("."):
        return False

    bare = stripped[:-1].strip().upper()
    if not bare:
        return False
    if bare in _DIVISION_HEADERS:
        return False
    if bare.endswith(" SECTION"):
        return False
    if " " in bare:
        return False
    return _PARAGRAPH_NAME_PATTERN.fullmatch(bare) is not None


def _extract_paragraph_name(header_line: str) -> str:
    """Extract canonical paragraph name from a header line."""
    return header_line.strip()[:-1].strip().upper()


def _detect_paragraph_blocks(lines: list[str]) -> list[_ParagraphBlock]:
    """Detect paragraph boundaries in PROCEDURE DIVISION with safe fallback."""
    if not lines:
        return []

    procedure_start = _find_procedure_division_start(lines)
    if procedure_start is None:
        return [
            _ParagraphBlock(
                name="FILE-BLOCK",
                line_start=1,
                line_end=len(lines),
                division="UNKNOWN",
            )
        ]

    blocks: list[_ParagraphBlock] = []
    current_name: str | None = None
    current_start: int | None = None

    for line_number in range(procedure_start + 1, len(lines) + 1):
        line = lines[line_number - 1]
        if _is_paragraph_header(line):
            if current_name is not None and current_start is not None:
                blocks.append(
                    _ParagraphBlock(
                        name=current_name,
                        line_start=current_start,
                        line_end=line_number - 1,
                        division="PROCEDURE",
                    )
                )
            current_name = _extract_paragraph_name(line)
            current_start = line_number

    if current_name is not None and current_start is not None:
        blocks.append(
            _ParagraphBlock(
                name=current_name,
                line_start=current_start,
                line_end=len(lines),
                division="PROCEDURE",
            )
        )

    if blocks:
        return blocks

    return [
        _ParagraphBlock(
            name="PROCEDURE-BLOCK",
            line_start=procedure_start,
            line_end=len(lines),
            division="PROCEDURE",
        )
    ]


def _build_chunk_from_block(
    block: _ParagraphBlock,
    lines: list[str],
    file_path: str,
    codebase: str,
) -> Chunk:
    """Construct a chunk for a paragraph/fallback block."""
    content = "\n".join(lines[block.line_start - 1 : block.line_end])
    token_count = _count_tokens(content)
    return Chunk(
        content=content,
        file_path=file_path,
        line_start=block.line_start,
        line_end=block.line_end,
        chunk_type="paragraph",
        language="cobol",
        codebase=codebase,
        name=block.name,
        division=block.division,
        token_count=token_count,
    )


def _merge_chunk_names(left: str, right: str) -> str:
    """Merge paragraph names deterministically while preserving first-seen order."""
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
    merged_division = left.division if left.division == right.division else "UNKNOWN"
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
    """Normalize dependency token format for stable payload behavior."""
    compact = " ".join(raw_value.split())
    stripped = compact.strip().strip(".,;:").strip("\"'")
    return stripped.upper()


def _append_dependency(
    dependencies: list[str],
    seen: set[str],
    raw_value: str,
) -> None:
    """Append normalized dependency while preserving first-seen ordering."""
    normalized = _normalize_dependency(raw_value)
    if not normalized:
        return
    if normalized in seen:
        return
    seen.add(normalized)
    dependencies.append(normalized)


def _extract_dependencies(chunk_text: str) -> list[str]:
    """Extract PERFORM/CALL/COPY dependencies from chunk text."""
    dependencies: list[str] = []
    seen: set[str] = set()

    for match in _PERFORM_THRU_PATTERN.finditer(chunk_text):
        start = match.group(1)
        end = match.group(2)
        _append_dependency(dependencies, seen, f"{start} THRU {end}")

    perform_stripped = _PERFORM_THRU_PATTERN.sub(" ", chunk_text)
    for match in _PERFORM_PATTERN.finditer(perform_stripped):
        _append_dependency(dependencies, seen, match.group(1))

    for match in _CALL_PATTERN.finditer(chunk_text):
        _append_dependency(dependencies, seen, match.group(1))

    for match in _COPY_PATTERN.finditer(chunk_text):
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


def chunk_cobol(
    processed_file: ProcessedFile,
    codebase: str = "gnucobol",
) -> list[Chunk]:
    """Chunk preprocessed COBOL source on paragraph boundaries.

    The output is paragraph-oriented, then normalized to satisfy adaptive
    token size constraints, and finally enriched with dependency and
    metadata fields needed by retrieval and citation layers.
    """
    if not processed_file.code.strip():
        return []

    lines = processed_file.code.splitlines()
    blocks = _detect_paragraph_blocks(lines)

    initial_chunks = [
        _build_chunk_from_block(
            block=block,
            lines=lines,
            file_path=processed_file.file_path,
            codebase=codebase,
        )
        for block in blocks
    ]

    merged_chunks = _merge_small_chunks(initial_chunks)
    sized_chunks = _split_oversized_chunks(merged_chunks)

    return [_enrich_chunk(chunk) for chunk in sized_chunks]
