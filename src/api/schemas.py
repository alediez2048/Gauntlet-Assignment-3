"""Pydantic schemas for LegacyLens API query routes."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.config import FEATURES
from src.types.responses import Confidence, QueryResponse, RetrievedChunk

# Keep API language validation aligned with prompt builder support.
SUPPORTED_LANGUAGES: set[str] = {"cobol"}


class QueryRequest(BaseModel):
    """Request body for query and streaming endpoints."""

    query: str
    feature: str = "code_explanation"
    codebase: str | None = None
    top_k: int = 10
    language: str = "cobol"
    model: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Ensure the query contains at least one non-whitespace character."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("feature")
    @classmethod
    def validate_feature(cls, value: str) -> str:
        """Validate feature names against configured supported features."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("feature must not be blank")
        if normalized not in FEATURES:
            raise ValueError(f"unsupported feature: {normalized}")
        return normalized

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        """Validate positive retrieval limit."""
        if value <= 0:
            raise ValueError("top_k must be greater than 0")
        return value

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Validate language enum for prompt generation."""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {normalized}")
        return normalized

    @field_validator("codebase", "model")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Convert blank optional text inputs to None."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class RetrievedChunkSchema(BaseModel):
    """API serialization contract for one retrieved/reranked chunk."""

    content: str
    file_path: str
    line_start: int
    line_end: int
    name: str
    language: str
    codebase: str
    score: float = 0.0
    confidence: Confidence = Confidence.MEDIUM
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_retrieved_chunk(cls, chunk: RetrievedChunk) -> "RetrievedChunkSchema":
        """Build response schema from internal RetrievedChunk dataclass."""
        return cls(
            content=chunk.content,
            file_path=chunk.file_path,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            name=chunk.name,
            language=chunk.language,
            codebase=chunk.codebase,
            score=chunk.score,
            confidence=chunk.confidence,
            metadata=chunk.metadata,
        )


class QueryResponseSchema(BaseModel):
    """API serialization contract mirroring QueryResponse fields."""

    answer: str
    chunks: list[RetrievedChunkSchema]
    query: str
    feature: str
    confidence: Confidence
    codebase_filter: str | None = None
    latency_ms: float = 0.0
    model: str = ""

    @classmethod
    def from_query_response(
        cls,
        response: QueryResponse,
        *,
        request_codebase: str | None = None,
    ) -> "QueryResponseSchema":
        """Build API response preserving QueryResponse contract fields."""
        codebase_filter = response.codebase_filter
        if codebase_filter is None and request_codebase is not None:
            codebase_filter = request_codebase

        return cls(
            answer=response.answer,
            chunks=[
                RetrievedChunkSchema.from_retrieved_chunk(chunk)
                for chunk in response.chunks
            ],
            query=response.query,
            feature=response.feature,
            confidence=response.confidence,
            codebase_filter=codebase_filter,
            latency_ms=response.latency_ms,
            model=response.model,
        )
