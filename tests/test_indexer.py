"""Unit tests for Qdrant indexing module (MVP-008)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.config import EMBEDDING_DIMENSIONS
from src.ingestion import indexer
from src.ingestion.indexer import (
    IndexerConfigError,
    IndexingDimensionError,
    QdrantIndexingError,
    index_chunks,
)
from src.types.chunks import Chunk, EmbeddedChunk


@dataclass
class _FakeCollectionInfo:
    """Simple marker object used by fake collection lookup."""

    exists: bool = True


class _FakeQdrantClient:
    """Minimal Qdrant client fake with call tracking."""

    def __init__(
        self,
        *,
        collection_exists: bool = False,
        payload_index_error: dict[str, BaseException] | None = None,
        raise_on_upsert_call: dict[int, BaseException] | None = None,
    ) -> None:
        self._collection_exists = collection_exists
        self.payload_index_error = payload_index_error or {}
        self.raise_on_upsert_call = raise_on_upsert_call or {}

        self.collection_exists_calls: list[str] = []
        self.create_collection_calls: list[dict[str, object]] = []
        self.create_payload_index_calls: list[dict[str, object]] = []
        self.upsert_calls: list[dict[str, object]] = []

    def collection_exists(self, collection_name: str) -> bool:
        self.collection_exists_calls.append(collection_name)
        return self._collection_exists

    def get_collection(self, collection_name: str) -> _FakeCollectionInfo:
        return _FakeCollectionInfo(exists=collection_name == "legacylens")

    def create_collection(self, *, collection_name: str, vectors_config: object) -> None:
        self._collection_exists = True
        self.create_collection_calls.append(
            {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
            }
        )

    def create_payload_index(
        self,
        *,
        collection_name: str,
        field_name: str,
        field_schema: object,
    ) -> None:
        self.create_payload_index_calls.append(
            {
                "collection_name": collection_name,
                "field_name": field_name,
                "field_schema": field_schema,
            }
        )
        failure = self.payload_index_error.get(field_name)
        if failure is not None:
            raise failure

    def upsert(self, *, collection_name: str, points: list[object]) -> None:
        call_number = len(self.upsert_calls) + 1
        self.upsert_calls.append({"collection_name": collection_name, "points": points})
        failure = self.raise_on_upsert_call.get(call_number)
        if failure is not None:
            raise failure


def _build_embedded_chunks(count: int) -> list[EmbeddedChunk]:
    """Build deterministic EmbeddedChunk values for indexer tests."""
    chunks: list[EmbeddedChunk] = []

    for index in range(count):
        paragraph_name = f"MAIN-{index:03d}"
        chunk = Chunk(
            content=f"{paragraph_name}.\n    PERFORM NEXT-PARA.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=(index * 10) + 1,
            line_end=(index * 10) + 2,
            chunk_type="paragraph",
            language="cobol",
            codebase="gnucobol",
            name=paragraph_name,
            division="PROCEDURE",
            dependencies=["NEXT-PARA"],
            token_count=16,
            metadata={"paragraph_name": paragraph_name},
        )
        chunks.append(
            EmbeddedChunk(
                chunk=chunk,
                embedding=[0.01] * EMBEDDING_DIMENSIONS,
                chunk_id=f"gnucobol:data/raw/gnucobol/sample.cob:{chunk.line_start}",
            )
        )

    return chunks


def test_empty_input_returns_zero_without_client_build(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_client_build() -> object:
        raise AssertionError("Client should not be built for empty input.")

    monkeypatch.setattr(indexer, "_build_qdrant_client", _unexpected_client_build)

    assert index_chunks([]) == 0


def test_missing_qdrant_url_raises_actionable_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indexer, "QDRANT_URL", "")

    with pytest.raises(IndexerConfigError, match="QDRANT_URL is missing"):
        indexer._build_qdrant_client()


def test_creates_collection_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeQdrantClient(collection_exists=False)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    count = index_chunks(_build_embedded_chunks(1))

    assert count == 1
    assert len(fake_client.create_collection_calls) == 1
    vectors_config = fake_client.create_collection_calls[0]["vectors_config"]
    assert getattr(vectors_config, "size") == EMBEDDING_DIMENSIONS
    assert getattr(vectors_config, "distance") == indexer.Distance.COSINE


def test_does_not_recreate_collection_when_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    index_chunks(_build_embedded_chunks(2))

    assert len(fake_client.create_collection_calls) == 0


def test_creates_required_payload_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    index_chunks(_build_embedded_chunks(1))

    indexed_fields = [call["field_name"] for call in fake_client.create_payload_index_calls]
    assert indexed_fields == [
        "paragraph_name",
        "division",
        "file_path",
        "language",
        "codebase",
    ]


def test_payload_index_creation_is_idempotent_for_already_exists_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(
        collection_exists=True,
        payload_index_error={
            "paragraph_name": RuntimeError("payload index already exists"),
            "division": RuntimeError("already exists"),
            "file_path": RuntimeError("index exists"),
            "language": RuntimeError("already indexed"),
            "codebase": RuntimeError("already exists"),
        },
    )
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    count = index_chunks(_build_embedded_chunks(1))

    assert count == 1
    assert len(fake_client.create_payload_index_calls) == 5


def test_single_chunk_produces_single_upsert_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    index_chunks(_build_embedded_chunks(1))

    assert len(fake_client.upsert_calls) == 1
    assert len(fake_client.upsert_calls[0]["points"]) == 1


def test_batching_257_chunks_splits_into_128_128_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    indexed_count = index_chunks(_build_embedded_chunks(257))

    batch_sizes = [len(call["points"]) for call in fake_client.upsert_calls]
    assert indexed_count == 257
    assert batch_sizes == [128, 128, 1]


def test_point_mapping_uses_chunk_id_embedding_and_payload_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)
    embedded_chunk = _build_embedded_chunks(1)[0]

    index_chunks([embedded_chunk])

    points = fake_client.upsert_calls[0]["points"]
    first_point = points[0]

    assert getattr(first_point, "id") == embedded_chunk.chunk_id
    assert getattr(first_point, "vector") == embedded_chunk.embedding
    payload = getattr(first_point, "payload")
    assert payload["content"] == embedded_chunk.chunk.content
    assert payload["file_path"] == embedded_chunk.chunk.file_path
    assert payload["line_start"] == embedded_chunk.chunk.line_start
    assert payload["line_end"] == embedded_chunk.chunk.line_end
    assert payload["paragraph_name"] == embedded_chunk.chunk.name
    assert payload["division"] == embedded_chunk.chunk.division
    assert payload["chunk_type"] == embedded_chunk.chunk.chunk_type
    assert payload["language"] == embedded_chunk.chunk.language
    assert payload["codebase"] == embedded_chunk.chunk.codebase
    assert payload["dependencies"] == embedded_chunk.chunk.dependencies


def test_dimension_mismatch_raises_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)
    bad_chunk = _build_embedded_chunks(1)[0]
    bad_chunk.embedding = [0.5] * (EMBEDDING_DIMENSIONS - 1)

    with pytest.raises(IndexingDimensionError, match="expected 1536, got 1535"):
        index_chunks([bad_chunk])


def test_upsert_failure_is_surfaced_as_typed_qdrant_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(
        collection_exists=True,
        raise_on_upsert_call={1: RuntimeError("boom")},
    )
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    with pytest.raises(QdrantIndexingError, match="Failed to upsert batch"):
        index_chunks(_build_embedded_chunks(1))


def test_non_positive_batch_size_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeQdrantClient(collection_exists=True)
    monkeypatch.setattr(indexer, "_build_qdrant_client", lambda: fake_client)

    with pytest.raises(ValueError, match="batch_size must be greater than 0"):
        index_chunks(_build_embedded_chunks(1), batch_size=0)
