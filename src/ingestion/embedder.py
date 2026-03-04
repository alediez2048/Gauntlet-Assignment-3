"""Batch embedding for ingestion chunks (MVP-007)."""

from __future__ import annotations

import importlib
import time
from collections.abc import Iterator, Sequence
from types import ModuleType
from typing import Protocol, TypeVar

from src.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    VOYAGE_API_KEY,
)
from src.types.chunks import Chunk, EmbeddedChunk


class EmbeddingConfigError(RuntimeError):
    """Raised when embedding configuration is missing or invalid."""


class EmbeddingDimensionError(ValueError):
    """Raised when returned vectors do not match configured dimensions."""


class EmbeddingRetryError(RuntimeError):
    """Raised when embedding retries are exhausted."""


class _VoyageClientProtocol(Protocol):
    """Protocol for the subset of voyageai.Client used by this module."""

    def embed(self, *, texts: list[str], model: str, input_type: str) -> object:
        """Return embedding response object containing `.embeddings`."""


T = TypeVar("T")


def _import_voyageai_module() -> ModuleType:
    """Import voyageai lazily to keep test environments lightweight."""
    try:
        return importlib.import_module("voyageai")
    except ModuleNotFoundError as exc:
        raise EmbeddingConfigError(
            "voyageai is not installed. Install dependencies before embedding."
        ) from exc


def _build_voyage_client() -> _VoyageClientProtocol:
    """Build a configured voyageai client using API key from config."""
    if not VOYAGE_API_KEY:
        raise EmbeddingConfigError(
            "VOYAGE_API_KEY is missing. Set it in your environment or .env file."
        )

    voyageai_module = _import_voyageai_module()
    return voyageai_module.Client(api_key=VOYAGE_API_KEY)


def _batched(items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield contiguous batches from items."""
    if size <= 0:
        raise ValueError("batch_size must be greater than 0")

    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def _extract_embeddings(response: object) -> list[list[float]]:
    """Extract embedding vectors from voyage response object."""
    embeddings_value: object | None

    if isinstance(response, dict):
        embeddings_value = response.get("embeddings")
    else:
        embeddings_value = getattr(response, "embeddings", None)

    if embeddings_value is None:
        raise EmbeddingRetryError("Embedding response did not include embeddings.")
    if not isinstance(embeddings_value, list):
        raise EmbeddingRetryError("Embedding response embeddings must be a list.")

    vectors: list[list[float]] = []
    for index, vector in enumerate(embeddings_value):
        if not isinstance(vector, list):
            raise EmbeddingRetryError(
                f"Embedding vector at index {index} is not a list."
            )
        vectors.append([float(value) for value in vector])

    return vectors


def _validate_dimensions(
    vectors: list[list[float]],
    expected_dimensions: int = EMBEDDING_DIMENSIONS,
) -> None:
    """Validate that every embedding vector matches configured dimensions."""
    for index, vector in enumerate(vectors):
        actual_dimensions = len(vector)
        if actual_dimensions != expected_dimensions:
            raise EmbeddingDimensionError(
                f"Embedding dimension mismatch at index {index}: "
                f"expected {expected_dimensions}, got {actual_dimensions}"
            )


def _build_chunk_id(chunk: Chunk) -> str:
    """Build deterministic chunk ID for downstream indexing."""
    return f"{chunk.codebase}:{chunk.file_path}:{chunk.line_start}"


def _get_timeout_exception_types() -> tuple[type[BaseException], ...]:
    """Collect timeout exception classes from stdlib and voyageai, if available."""
    timeout_types: list[type[BaseException]] = [TimeoutError]

    try:
        error_module = importlib.import_module("voyageai.error")
    except ModuleNotFoundError:
        return tuple(timeout_types)

    for attr_name in ("TimeoutError", "RequestTimeoutError", "APITimeoutError"):
        candidate = getattr(error_module, attr_name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            if candidate not in timeout_types:
                timeout_types.append(candidate)

    return tuple(timeout_types)


def _embed_batch_with_retry(
    client: _VoyageClientProtocol,
    texts: list[str],
    model: str,
    input_type: str = "document",
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.5,
) -> list[list[float]]:
    """Embed a single batch with timeout retries and exponential backoff."""
    if not texts:
        return []

    timeout_exceptions = _get_timeout_exception_types()
    backoff_seconds = initial_backoff_seconds

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.embed(texts=texts, model=model, input_type=input_type)
            vectors = _extract_embeddings(response)
            if len(vectors) != len(texts):
                raise EmbeddingRetryError(
                    "Embedding response count mismatch: "
                    f"expected {len(texts)}, got {len(vectors)}"
                )
            _validate_dimensions(vectors)
            return vectors
        except timeout_exceptions as exc:
            if attempt == max_attempts:
                raise EmbeddingRetryError(
                    f"Embedding batch failed after {max_attempts} attempts due to timeout."
                ) from exc
            time.sleep(backoff_seconds)
            backoff_seconds *= 2.0

    raise EmbeddingRetryError("Embedding batch failed unexpectedly.")


def _attach_vectors(chunks: list[Chunk], vectors: list[list[float]]) -> list[EmbeddedChunk]:
    """Attach vectors to chunks while preserving stable input order."""
    if len(chunks) != len(vectors):
        raise EmbeddingRetryError(
            "Chunk/vector length mismatch: "
            f"expected {len(chunks)} vectors, got {len(vectors)}"
        )

    return [
        EmbeddedChunk(
            chunk=chunk,
            embedding=vector,
            chunk_id=_build_chunk_id(chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]


def embed_chunks(
    chunks: list[Chunk],
    model: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> list[EmbeddedChunk]:
    """Embed chunks in deterministic batches and return EmbeddedChunk objects."""
    if not chunks:
        return []
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    client = _build_voyage_client()
    texts = [chunk.content for chunk in chunks]
    vectors: list[list[float]] = []

    for text_batch in _batched(texts, batch_size):
        batch_vectors = _embed_batch_with_retry(
            client=client,
            texts=text_batch,
            model=model,
            input_type="document",
        )
        vectors.extend(batch_vectors)

    return _attach_vectors(chunks=chunks, vectors=vectors)
