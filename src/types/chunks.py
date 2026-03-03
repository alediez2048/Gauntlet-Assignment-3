"""Chunk data types for LegacyLens."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessedFile:
    """Result of preprocessing a legacy source file."""

    code: str
    comments: list[str]
    language: str
    file_path: str
    encoding: str = "utf-8"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    """A single code chunk with metadata, ready for embedding."""

    content: str
    file_path: str
    line_start: int
    line_end: int
    chunk_type: str
    language: str
    codebase: str
    name: str = ""
    division: str = ""
    dependencies: list[str] = field(default_factory=list)
    token_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class EmbeddedChunk:
    """A chunk with its embedding vector attached."""

    chunk: Chunk
    embedding: list[float] = field(default_factory=list)
    chunk_id: str = ""
