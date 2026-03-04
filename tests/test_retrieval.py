"""Unit tests for retrieval reranking module (MVP-010)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.retrieval import reranker
from src.retrieval.reranker import RerankerValidationError, rerank_chunks
from src.types.responses import Confidence, RetrievedChunk


@dataclass
class _FakeCohereResult:
    index: int
    relevance_score: float


@dataclass
class _FakeCohereResponse:
    results: list[_FakeCohereResult]


class _FakeCohereClient:
    """Simple Cohere fake used to avoid network calls in unit tests."""

    def __init__(
        self,
        *,
        relevance_by_index: dict[int, float] | None = None,
        raise_error: bool = False,
    ) -> None:
        self.relevance_by_index = relevance_by_index or {}
        self.raise_error = raise_error
        self.calls: list[dict[str, object]] = []

    def rerank(
        self,
        *,
        model: str,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> _FakeCohereResponse:
        self.calls.append(
            {
                "model": model,
                "query": query,
                "documents": list(documents),
                "top_n": top_n,
            }
        )
        if self.raise_error:
            raise RuntimeError("cohere unavailable")
        return _FakeCohereResponse(
            results=[
                _FakeCohereResult(
                    index=index,
                    relevance_score=self.relevance_by_index.get(index, 0.0),
                )
                for index in range(len(documents))
            ]
        )


def _make_chunk(
    *,
    name: str,
    score: float,
    file_path: str = "data/raw/gnucobol/sample.cob",
    line_start: int = 10,
    language: str = "cobol",
    codebase: str = "gnucobol",
    division: str = "PROCEDURE",
    dependencies: str = "",
) -> RetrievedChunk:
    return RetrievedChunk(
        content=f"{name}. PERFORM SOMETHING.",
        file_path=file_path,
        line_start=line_start,
        line_end=line_start + 1,
        name=name,
        language=language,
        codebase=codebase,
        score=score,
        metadata={
            "paragraph_name": name,
            "division": division,
            "dependencies": dependencies,
        },
    )


def test_blank_query_raises_deterministic_validation_error() -> None:
    with pytest.raises(RerankerValidationError, match="query must not be blank"):
        rerank_chunks("   ", [_make_chunk(name="MAIN-LOGIC", score=0.8)])


def test_empty_chunk_list_returns_empty_list() -> None:
    assert rerank_chunks("what does main do", []) == []


def test_returns_retrieved_chunk_contract_and_updates_scores() -> None:
    chunks = [
        _make_chunk(name="MAIN-LOGIC", score=0.60, line_start=10),
        _make_chunk(name="INIT-DATA", score=0.55, line_start=20),
    ]

    reranked = rerank_chunks("explain MAIN-LOGIC procedure", chunks, enable_cohere=False)

    assert isinstance(reranked, list)
    assert len(reranked) == 2
    assert all(isinstance(chunk, RetrievedChunk) for chunk in reranked)
    assert all(0.0 <= chunk.score <= 1.0 for chunk in reranked)
    assert all(chunk.confidence in {Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW} for chunk in reranked)


def test_paragraph_name_match_gets_boosted() -> None:
    chunks = [
        _make_chunk(name="MAIN-LOGIC", score=0.50, line_start=10),
        _make_chunk(name="INIT-DATA", score=0.58, line_start=20),
    ]

    reranked = rerank_chunks("what does MAIN-LOGIC do", chunks, enable_cohere=False)

    assert reranked[0].name == "MAIN-LOGIC"


def test_division_aware_query_boosts_matching_division() -> None:
    chunks = [
        _make_chunk(name="PROC-STEP", score=0.40, division="PROCEDURE", line_start=10),
        _make_chunk(name="DATA-DEF", score=0.45, division="DATA", line_start=20),
    ]

    reranked = rerank_chunks("trace procedure flow", chunks, enable_cohere=False)

    assert reranked[0].name == "PROC-STEP"


def test_non_matching_chunks_keep_baseline_order() -> None:
    chunks = [
        _make_chunk(name="FIRST-PARA", score=0.80, line_start=10),
        _make_chunk(name="SECOND-PARA", score=0.70, line_start=20),
    ]

    reranked = rerank_chunks("unrelated tokens here", chunks, enable_cohere=False)

    assert [chunk.name for chunk in reranked] == ["FIRST-PARA", "SECOND-PARA"]


def test_dependency_overlap_boosts_matching_chunk() -> None:
    chunks = [
        _make_chunk(
            name="LOWER-BASE",
            score=0.50,
            line_start=10,
            dependencies="INIT-DATA,READ-FILE",
        ),
        _make_chunk(
            name="HIGHER-BASE",
            score=0.53,
            line_start=20,
            dependencies="WRITE-REPORT",
        ),
    ]

    reranked = rerank_chunks("where is INIT-DATA used", chunks, enable_cohere=False)

    assert reranked[0].name == "LOWER-BASE"


def test_confidence_mapping_high_medium_low_is_deterministic() -> None:
    chunks = [
        _make_chunk(name="TOP", score=0.90, line_start=10),
        _make_chunk(name="MIDDLE", score=0.50, line_start=20),
        _make_chunk(name="BOTTOM", score=0.10, line_start=30),
    ]

    reranked = rerank_chunks("unrelated prompt", chunks, enable_cohere=False)
    confidence_by_name = {chunk.name: chunk.confidence for chunk in reranked}

    assert confidence_by_name["TOP"] == Confidence.HIGH
    assert confidence_by_name["MIDDLE"] == Confidence.MEDIUM
    assert confidence_by_name["BOTTOM"] == Confidence.LOW


def test_sorting_uses_deterministic_tie_breakers() -> None:
    chunks = [
        _make_chunk(
            name="B-CHUNK",
            score=0.50,
            file_path="b/file.cob",
            line_start=20,
        ),
        _make_chunk(
            name="A-CHUNK",
            score=0.50,
            file_path="a/file.cob",
            line_start=30,
        ),
        _make_chunk(
            name="A-EARLIER",
            score=0.50,
            file_path="a/file.cob",
            line_start=10,
        ),
    ]

    reranked = rerank_chunks("no match tokens", chunks, enable_cohere=False)

    assert [chunk.name for chunk in reranked] == ["A-EARLIER", "A-CHUNK", "B-CHUNK"]


def test_cohere_stage_runs_when_enabled_and_api_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        _make_chunk(name="FIRST", score=0.80, line_start=10),
        _make_chunk(name="SECOND", score=0.70, line_start=20),
    ]
    fake_client = _FakeCohereClient(relevance_by_index={0: 0.10, 1: 0.95})
    monkeypatch.setattr(reranker, "COHERE_API_KEY", "test-key")
    monkeypatch.setattr(reranker, "_build_cohere_client", lambda: fake_client)

    reranked = rerank_chunks("some query", chunks, enable_cohere=True)

    assert len(fake_client.calls) == 1
    assert reranked[0].name == "SECOND"


def test_missing_cohere_api_key_uses_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        _make_chunk(name="FIRST", score=0.80, line_start=10),
        _make_chunk(name="SECOND", score=0.70, line_start=20),
    ]

    def _unexpected_client() -> object:
        raise AssertionError("Cohere client should not be built without API key.")

    monkeypatch.setattr(reranker, "COHERE_API_KEY", "")
    monkeypatch.setattr(reranker, "_build_cohere_client", _unexpected_client)

    reranked = rerank_chunks("no overlap", chunks, enable_cohere=True)

    assert [chunk.name for chunk in reranked] == ["FIRST", "SECOND"]


def test_cohere_error_path_falls_back_to_metadata_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        _make_chunk(name="FIRST", score=0.80, line_start=10),
        _make_chunk(name="SECOND", score=0.70, line_start=20),
    ]

    metadata_only = rerank_chunks("no overlap", chunks, enable_cohere=False)

    fake_client = _FakeCohereClient(raise_error=True)
    monkeypatch.setattr(reranker, "COHERE_API_KEY", "test-key")
    monkeypatch.setattr(reranker, "_build_cohere_client", lambda: fake_client)

    reranked = rerank_chunks("no overlap", chunks, enable_cohere=True)

    assert [chunk.name for chunk in reranked] == [chunk.name for chunk in metadata_only]
