"""Qdrant indexing for embedded chunks (MVP-008)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from typing import TypeVar

_LEGACYLENS_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from src.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from src.types.chunks import EmbeddedChunk

REQUIRED_PAYLOAD_INDEX_FIELDS: tuple[str, ...] = (
    "paragraph_name",
    "division",
    "file_path",
    "language",
    "codebase",
)

T = TypeVar("T")


class IndexerConfigError(RuntimeError):
    """Raised when Qdrant indexing configuration is missing or invalid."""


class IndexingDimensionError(ValueError):
    """Raised when embedding dimensions do not match configured size."""


class QdrantIndexingError(RuntimeError):
    """Raised when Qdrant collection/index/upsert operations fail."""


def _build_qdrant_client() -> QdrantClient:
    """Build a Qdrant client using configured URL and API key."""
    if not QDRANT_URL:
        raise IndexerConfigError(
            "QDRANT_URL is missing. Set it in your environment or .env file."
        )
    try:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    except (TypeError, ValueError) as exc:
        raise IndexerConfigError(
            "Failed to create Qdrant client. Verify QDRANT_URL and QDRANT_API_KEY."
        ) from exc


def _is_already_exists_error(error: Exception) -> bool:
    """Return True when Qdrant reports an already-existing resource."""
    message = str(error).lower()
    return (
        "already exists" in message
        or "already indexed" in message
        or ("index" in message and "exists" in message)
    )


def _collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """Return whether the target collection already exists in Qdrant."""
    try:
        return bool(client.collection_exists(collection_name=collection_name))
    except Exception as exc:
        raise QdrantIndexingError(
            f"Failed to check collection existence for '{collection_name}'."
        ) from exc


def _ensure_collection(client: QdrantClient, collection_name: str) -> None:
    """Create collection with correct vector settings if it does not exist."""
    if _collection_exists(client, collection_name):
        return

    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )
    except Exception as exc:
        if _is_already_exists_error(exc):
            return
        raise QdrantIndexingError(
            f"Failed to create collection '{collection_name}'."
        ) from exc


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """Ensure required retrieval payload indexes exist (idempotent)."""
    for field_name in REQUIRED_PAYLOAD_INDEX_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            if _is_already_exists_error(exc):
                continue
            raise QdrantIndexingError(
                f"Failed to create payload index '{field_name}' in '{collection_name}'."
            ) from exc


def _validate_embedding(
    embedding: list[float],
    expected_dimensions: int = EMBEDDING_DIMENSIONS,
) -> None:
    """Validate embedding dimensionality before Qdrant upsert."""
    actual_dimensions = len(embedding)
    if actual_dimensions != expected_dimensions:
        raise IndexingDimensionError(
            f"Embedding dimension mismatch: expected {expected_dimensions}, "
            f"got {actual_dimensions}"
        )


def _to_int(value: object, fallback: int) -> int:
    """Convert metadata value to int when possible, else return fallback."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return fallback
    return fallback


def _build_payload(embedded_chunk: EmbeddedChunk) -> dict[str, str | int | list[str]]:
    """Build retrieval-ready payload from chunk fields + metadata fallbacks."""
    chunk = embedded_chunk.chunk
    metadata = chunk.metadata

    file_path = str(metadata.get("file_path", chunk.file_path) or chunk.file_path)
    line_start = _to_int(metadata.get("line_start"), chunk.line_start)
    line_end = _to_int(metadata.get("line_end"), chunk.line_end)
    paragraph_name = str(metadata.get("paragraph_name", chunk.name) or chunk.name)
    division = str(metadata.get("division", chunk.division) or chunk.division)
    chunk_type = str(metadata.get("chunk_type", chunk.chunk_type) or chunk.chunk_type)
    language = str(metadata.get("language", chunk.language) or chunk.language)
    codebase = str(metadata.get("codebase", chunk.codebase) or chunk.codebase)

    return {
        "content": chunk.content,
        "file_path": file_path,
        "line_start": line_start,
        "line_end": line_end,
        "name": chunk.name,
        "paragraph_name": paragraph_name,
        "division": division,
        "chunk_type": chunk_type,
        "language": language,
        "codebase": codebase,
        "dependencies": list(chunk.dependencies),
    }


def _chunk_id_to_uuid(chunk_id: str) -> str:
    """Convert a string chunk ID to a deterministic UUID for Qdrant."""
    return str(uuid.uuid5(_LEGACYLENS_UUID_NAMESPACE, chunk_id))


def _build_point(embedded_chunk: EmbeddedChunk) -> PointStruct:
    """Convert an EmbeddedChunk into deterministic Qdrant PointStruct."""
    _validate_embedding(embedded_chunk.embedding)
    payload = _build_payload(embedded_chunk)
    return PointStruct(
        id=_chunk_id_to_uuid(embedded_chunk.chunk_id),
        vector=embedded_chunk.embedding,
        payload={**payload, "chunk_id": embedded_chunk.chunk_id},
    )


def _batched(items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield contiguous deterministic batches from input items."""
    if size <= 0:
        raise ValueError("batch_size must be greater than 0")

    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def _upsert_batch(
    client: QdrantClient,
    collection_name: str,
    points: list[PointStruct],
) -> None:
    """Upsert one batch of Qdrant points."""
    if not points:
        return
    try:
        client.upsert(collection_name=collection_name, points=points)
    except Exception as exc:
        raise QdrantIndexingError(
            f"Failed to upsert batch of {len(points)} points into '{collection_name}'."
        ) from exc


def index_chunks(
    embedded_chunks: list[EmbeddedChunk],
    collection_name: str = QDRANT_COLLECTION_NAME,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> int:
    """Index EmbeddedChunk vectors + payloads into Qdrant in deterministic batches."""
    if not embedded_chunks:
        return 0
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    client = _build_qdrant_client()
    _ensure_collection(client, collection_name)
    _ensure_payload_indexes(client, collection_name)

    points = [_build_point(chunk) for chunk in embedded_chunks]
    for batch in _batched(points, batch_size):
        _upsert_batch(client, collection_name, batch)

    return len(points)
