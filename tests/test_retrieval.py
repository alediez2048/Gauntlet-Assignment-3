"""Unit tests for hybrid retrieval module (MVP-009)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from qdrant_client.models import Document

from src.retrieval import search
from src.retrieval.search import (
    SearchBackendError,
    SearchConfigError,
    SearchEmbeddingError,
    SearchValidationError,
    _build_query_filter,
    _select_channel_weights,
    hybrid_search,
)
from src.types.responses import RetrievedChunk


@dataclass
class _FakeScoredPoint:
    id: str
    score: float
    payload: dict[str, object]


@dataclass
class _FakeQueryResponse:
    points: list[_FakeScoredPoint]


@dataclass
class _FakeEmbeddingResponse:
    embeddings: list[list[float]]


class _FakeVoyageClient:
    """Minimal voyage client fake with deterministic embeddings."""

    def __init__(self, *, vectors: list[list[float]] | None = None, raise_error: bool = False) -> None:
        self.vectors = vectors or [[0.1, 0.2, 0.3]]
        self.raise_error = raise_error
        self.calls: list[dict[str, object]] = []

    def embed(self, *, texts: list[str], model: str, input_type: str) -> _FakeEmbeddingResponse:
        self.calls.append({"texts": list(texts), "model": model, "input_type": input_type})
        if self.raise_error:
            raise RuntimeError("voyage failure")
        return _FakeEmbeddingResponse(embeddings=self.vectors)


class _FakeQdrantClient:
    """Minimal Qdrant client fake with dense/sparse channel tracking."""

    def __init__(
        self,
        *,
        dense_points: list[_FakeScoredPoint] | None = None,
        sparse_points: list[_FakeScoredPoint] | None = None,
        raise_error: bool = False,
    ) -> None:
        self.dense_points = dense_points or []
        self.sparse_points = sparse_points or []
        self.raise_error = raise_error
        self.calls: list[dict[str, object]] = []

    def query_points(
        self,
        *,
        collection_name: str,
        query: object,
        query_filter: object = None,
        limit: int = 10,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> _FakeQueryResponse:
        self.calls.append(
            {
                "collection_name": collection_name,
                "query": query,
                "query_filter": query_filter,
                "limit": limit,
                "with_payload": with_payload,
                "with_vectors": with_vectors,
            }
        )
        if self.raise_error:
            raise RuntimeError("qdrant failure")

        if isinstance(query, list):
            return _FakeQueryResponse(points=self.dense_points[:limit])
        if isinstance(query, Document):
            return _FakeQueryResponse(points=self.sparse_points[:limit])
        return _FakeQueryResponse(points=[])


def _build_payload(
    *,
    name: str,
    line_start: int,
    language: str = "cobol",
    codebase: str = "gnucobol",
) -> dict[str, object]:
    return {
        "content": f"{name}. PERFORM INIT-DATA.",
        "file_path": "data/raw/gnucobol/sample.cob",
        "line_start": line_start,
        "line_end": line_start + 1,
        "name": name,
        "paragraph_name": name,
        "division": "PROCEDURE",
        "chunk_type": "paragraph",
        "language": language,
        "codebase": codebase,
        "dependencies": ["INIT-DATA"],
    }


def test_blank_query_raises_validation_error() -> None:
    with pytest.raises(SearchValidationError, match="query must not be blank"):
        hybrid_search("   ")


def test_non_positive_top_k_raises_validation_error() -> None:
    with pytest.raises(SearchValidationError, match="top_k must be greater than 0"):
        hybrid_search("what does main do", top_k=0)


def test_missing_qdrant_url_raises_actionable_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search, "QDRANT_URL", "")

    with pytest.raises(SearchConfigError, match="QDRANT_URL is missing"):
        search._build_qdrant_client()


def test_missing_voyage_api_key_raises_actionable_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search, "VOYAGE_API_KEY", "")

    with pytest.raises(SearchConfigError, match="VOYAGE_API_KEY is missing"):
        search._build_voyage_client()


def test_identifier_query_selects_bm25_heavy_weights() -> None:
    dense_weight, sparse_weight = _select_channel_weights("CALCULATE-INTEREST")
    assert dense_weight == 0.4
    assert sparse_weight == 0.6


def test_semantic_query_selects_dense_heavy_weights() -> None:
    dense_weight, sparse_weight = _select_channel_weights("what does this paragraph do")
    assert dense_weight == 0.7
    assert sparse_weight == 0.3


def test_build_query_filter_none_returns_none() -> None:
    assert _build_query_filter(codebase=None) is None


def test_build_query_filter_with_codebase_contains_expected_condition() -> None:
    query_filter = _build_query_filter(codebase="gnucobol")
    assert query_filter is not None
    assert query_filter.must[0].key == "codebase"
    assert query_filter.must[0].match.value == "gnucobol"


def test_hybrid_search_returns_retrieved_chunk_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qdrant = _FakeQdrantClient(
        dense_points=[_FakeScoredPoint(id="chunk-1", score=0.9, payload=_build_payload(name="MAIN-LOGIC", line_start=10))],
        sparse_points=[_FakeScoredPoint(id="chunk-2", score=0.8, payload=_build_payload(name="INIT-DATA", line_start=20))],
    )
    fake_voyage = _FakeVoyageClient(vectors=[[0.11, 0.22, 0.33]])
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    results = hybrid_search("what does this paragraph do", top_k=3)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(item, RetrievedChunk) for item in results)
    first = results[0]
    assert first.content != ""
    assert first.file_path.endswith(".cob")
    assert first.line_start > 0
    assert first.line_end >= first.line_start
    assert first.name != ""
    assert first.language == "cobol"
    assert first.codebase == "gnucobol"
    assert 0.0 <= first.score <= 1.0


def test_codebase_filter_is_passed_to_both_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qdrant = _FakeQdrantClient()
    fake_voyage = _FakeVoyageClient()
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    hybrid_search("main entry", top_k=2, codebase="gnucobol")

    assert len(fake_qdrant.calls) == 2
    assert all(call["query_filter"] is not None for call in fake_qdrant.calls)


def test_fusion_dedupes_duplicate_ids_and_orders_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dense_points = [
        _FakeScoredPoint(id="A", score=0.80, payload=_build_payload(name="A-PARA", line_start=10)),
        _FakeScoredPoint(id="B", score=0.30, payload=_build_payload(name="B-PARA", line_start=20)),
    ]
    sparse_points = [
        _FakeScoredPoint(id="A", score=0.20, payload=_build_payload(name="A-PARA", line_start=10)),
        _FakeScoredPoint(id="C", score=0.95, payload=_build_payload(name="C-PARA", line_start=30)),
    ]
    fake_qdrant = _FakeQdrantClient(dense_points=dense_points, sparse_points=sparse_points)
    fake_voyage = _FakeVoyageClient()
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    results = hybrid_search("CALCULATE-INTEREST", top_k=5)

    # Duplicate point A should appear only once.
    assert [result.name for result in results].count("A-PARA") == 1
    assert len(results) == 3
    assert results[0].score >= results[1].score >= results[2].score


def test_top_k_limit_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    dense_points = [
        _FakeScoredPoint(id="A", score=0.90, payload=_build_payload(name="A-PARA", line_start=10)),
        _FakeScoredPoint(id="B", score=0.80, payload=_build_payload(name="B-PARA", line_start=20)),
        _FakeScoredPoint(id="C", score=0.70, payload=_build_payload(name="C-PARA", line_start=30)),
    ]
    sparse_points = []
    fake_qdrant = _FakeQdrantClient(dense_points=dense_points, sparse_points=sparse_points)
    fake_voyage = _FakeVoyageClient()
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    results = hybrid_search("semantic question", top_k=2)

    assert len(results) == 2


def test_empty_channels_return_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_qdrant = _FakeQdrantClient(dense_points=[], sparse_points=[])
    fake_voyage = _FakeVoyageClient()
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    assert hybrid_search("what does this do", top_k=3) == []


def test_qdrant_failures_surface_as_typed_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qdrant = _FakeQdrantClient(raise_error=True)
    fake_voyage = _FakeVoyageClient()
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    with pytest.raises(SearchBackendError, match="Dense retrieval failed"):
        hybrid_search("what does this do")


def test_voyage_failures_surface_as_typed_embedding_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qdrant = _FakeQdrantClient()
    fake_voyage = _FakeVoyageClient(raise_error=True)
    monkeypatch.setattr(search, "_build_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(search, "_build_voyage_client", lambda: fake_voyage)

    with pytest.raises(SearchEmbeddingError, match="Failed to embed query"):
        hybrid_search("what does this do")
