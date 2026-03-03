"""Response data types for LegacyLens."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    """Confidence level for retrieval results."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class RetrievedChunk:
    """A chunk returned from search with relevance scoring."""

    content: str
    file_path: str
    line_start: int
    line_end: int
    name: str
    language: str
    codebase: str
    score: float = 0.0
    confidence: Confidence = Confidence.MEDIUM
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class QueryResponse:
    """Full response to a user query."""

    answer: str
    chunks: list[RetrievedChunk]
    query: str
    feature: str
    confidence: Confidence
    codebase_filter: str | None = None
    latency_ms: float = 0.0
    model: str = ""
