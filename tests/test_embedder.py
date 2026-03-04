"""Unit tests for batch embedding module (MVP-007)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.config import EMBEDDING_DIMENSIONS
from src.ingestion import embedder
from src.ingestion.embedder import (
    EmbeddingDimensionError,
    EmbeddingRetryError,
    _build_chunk_id,
    embed_chunks,
)
from src.types.chunks import Chunk, EmbeddedChunk


def _build_chunks(count: int) -> list[Chunk]:
    """Build deterministic chunks for embedding tests."""
    chunks: list[Chunk] = []
    for index in range(count):
        paragraph_name = f"PARA-{index:03d}"
        chunks.append(
            Chunk(
                content=f"{paragraph_name}.\n    DISPLAY \"{index}\".",
                file_path="data/raw/gnucobol/sample.cob",
                line_start=(index * 10) + 1,
                line_end=(index * 10) + 2,
                chunk_type="paragraph",
                language="cobol",
                codebase="gnucobol",
                name=paragraph_name,
                division="PROCEDURE",
                token_count=12,
                metadata={"paragraph_name": paragraph_name},
            )
        )
    return chunks


@dataclass
class _FakeEmbeddingResponse:
    embeddings: list[list[float]]


class _FakeVoyageClient:
    """Minimal fake for voyageai.Client with call tracking."""

    def __init__(
        self,
        *,
        dimensions: int = EMBEDDING_DIMENSIONS,
        raise_on_calls: dict[int, BaseException] | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.raise_on_calls = raise_on_calls or {}
        self.calls: list[dict[str, object]] = []
        self._next_vector_seed = 0

    def embed(self, *, texts: list[str], model: str, input_type: str) -> _FakeEmbeddingResponse:
        call_number = len(self.calls) + 1
        self.calls.append(
            {
                "texts": list(texts),
                "model": model,
                "input_type": input_type,
            }
        )

        failure = self.raise_on_calls.get(call_number)
        if failure is not None:
            raise failure

        vectors: list[list[float]] = []
        for _ in texts:
            seed = float(self._next_vector_seed)
            vectors.append([seed] * self.dimensions)
            self._next_vector_seed += 1

        return _FakeEmbeddingResponse(embeddings=vectors)


def test_empty_input_returns_empty_without_building_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_client_build() -> object:
        raise AssertionError("Client should not be built for empty input")

    monkeypatch.setattr(embedder, "_build_voyage_client", _unexpected_client_build)

    assert embed_chunks([]) == []


def test_returns_embedded_chunk_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(2)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    result = embed_chunks(chunks)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, EmbeddedChunk) for item in result)
    assert result[0].chunk is chunks[0]
    assert result[1].chunk is chunks[1]
    assert len(result[0].embedding) == EMBEDDING_DIMENSIONS


def test_single_chunk_makes_single_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(1)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    embed_chunks(chunks)

    assert len(fake_client.calls) == 1
    assert len(fake_client.calls[0]["texts"]) == 1


def test_batching_257_chunks_splits_into_128_128_1(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(257)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    embed_chunks(chunks)

    batch_sizes = [len(call["texts"]) for call in fake_client.calls]
    assert batch_sizes == [128, 128, 1]


def test_request_shape_uses_model_and_document_input_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = _build_chunks(3)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    embed_chunks(chunks, model="voyage-code-2-custom")

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["model"] == "voyage-code-2-custom"
    assert fake_client.calls[0]["input_type"] == "document"


def test_dimension_mismatch_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(1)
    fake_client = _FakeVoyageClient(dimensions=EMBEDDING_DIMENSIONS - 1)
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    with pytest.raises(EmbeddingDimensionError, match="expected 1536, got 1535"):
        embed_chunks(chunks)


def test_chunk_id_is_deterministic() -> None:
    chunk = _build_chunks(1)[0]

    first = _build_chunk_id(chunk)
    second = _build_chunk_id(chunk)

    assert first == second
    assert first == f"{chunk.codebase}:{chunk.file_path}:{chunk.line_start}"


def test_transient_timeout_recovers_before_third_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = _build_chunks(2)
    fake_client = _FakeVoyageClient(raise_on_calls={1: TimeoutError("temporary timeout")})
    sleep_calls: list[float] = []

    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)
    monkeypatch.setattr(embedder.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = embed_chunks(chunks, batch_size=2)

    assert len(result) == 2
    assert len(fake_client.calls) == 2
    assert sleep_calls == [0.5]


def test_permanent_timeout_fails_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = _build_chunks(2)
    fake_client = _FakeVoyageClient(
        raise_on_calls={
            1: TimeoutError("timeout #1"),
            2: TimeoutError("timeout #2"),
            3: TimeoutError("timeout #3"),
        }
    )
    sleep_calls: list[float] = []

    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)
    monkeypatch.setattr(embedder.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(EmbeddingRetryError, match="failed after 3 attempts"):
        embed_chunks(chunks, batch_size=2)

    assert len(fake_client.calls) == 3
    assert sleep_calls == [0.5, 1.0]


def test_output_order_matches_input_chunk_order(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(6)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    result = embed_chunks(chunks, batch_size=2)

    assert [item.chunk for item in result] == chunks
    assert [item.embedding[0] for item in result] == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_non_positive_batch_size_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _build_chunks(1)
    fake_client = _FakeVoyageClient()
    monkeypatch.setattr(embedder, "_build_voyage_client", lambda: fake_client)

    with pytest.raises(ValueError, match="batch_size must be greater than 0"):
        embed_chunks(chunks, batch_size=0)

