"""API endpoint tests for MVP-013 FastAPI orchestration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.api import routes
from src.api.app import app
from src.types.responses import Confidence, QueryResponse, RetrievedChunk


def _sample_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        content="MAIN-LOGIC. PERFORM INIT-DATA.",
        file_path="data/raw/gnucobol/sample.cob",
        line_start=10,
        line_end=11,
        name="MAIN-LOGIC",
        language="cobol",
        codebase="gnucobol",
        score=0.81,
        confidence=Confidence.HIGH,
        metadata={"division": "PROCEDURE", "paragraph_name": "MAIN-LOGIC"},
    )


def _sample_response(chunks: list[RetrievedChunk]) -> QueryResponse:
    return QueryResponse(
        answer=(
            "MAIN-LOGIC initializes working variables.\n"
            "Citations: data/raw/gnucobol/sample.cob:10-11\n"
            "Confidence: HIGH"
        ),
        chunks=chunks,
        query="What does MAIN-LOGIC do?",
        feature="code_explanation",
        confidence=Confidence.HIGH,
        codebase_filter="gnucobol",
        latency_ms=12.3,
        model="gpt-4o",
    )


def _detail_contains(response: TestClient, text: str) -> bool:
    payload = response.json()
    detail = payload.get("detail")
    if isinstance(detail, str):
        return text in detail
    if isinstance(detail, list):
        for item in detail:
            if isinstance(item, dict):
                message = item.get("msg", "")
                if isinstance(message, str) and text in message:
                    return True
    return False


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_query_route_returns_query_response_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()
    expected = _sample_response(chunks=[chunk])

    monkeypatch.setattr(
        routes,
        "hybrid_search",
        lambda query, top_k, codebase: [chunk],
    )
    monkeypatch.setattr(
        routes,
        "rerank_chunks",
        lambda query, chunks, feature: chunks,
    )
    monkeypatch.setattr(
        routes,
        "generate_answer",
        lambda query, chunks, feature, language, model: expected,
    )

    response = client.post(
        "/api/query",
        json={"query": "What does MAIN-LOGIC do?", "codebase": "gnucobol"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["answer"].startswith("MAIN-LOGIC initializes")
    assert payload["query"] == "What does MAIN-LOGIC do?"
    assert payload["feature"] == "code_explanation"
    assert payload["confidence"] == "HIGH"
    assert payload["model"] == "gpt-4o"
    assert payload["latency_ms"] == pytest.approx(12.3)
    assert payload["codebase_filter"] == "gnucobol"
    assert len(payload["chunks"]) == 1
    assert payload["chunks"][0]["file_path"] == "data/raw/gnucobol/sample.cob"
    assert payload["chunks"][0]["confidence"] == "HIGH"


def test_query_blank_query_returns_validation_error(client: TestClient) -> None:
    response = client.post("/api/query", json={"query": "   "})
    assert response.status_code == 422
    assert _detail_contains(response, "query must not be blank")


def test_query_top_k_must_be_positive(client: TestClient) -> None:
    response = client.post("/api/query", json={"query": "test", "top_k": 0})
    assert response.status_code == 422
    assert _detail_contains(response, "top_k must be greater than 0")


def test_query_unknown_feature_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/query",
        json={"query": "test", "feature": "unknown_feature"},
    )
    assert response.status_code == 422
    assert _detail_contains(response, "unsupported feature")


def test_query_pipeline_stage_invocation_order(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()
    generated = _sample_response(chunks=[chunk])
    call_order: list[str] = []

    def _fake_hybrid_search(query: str, top_k: int, codebase: str | None) -> list[RetrievedChunk]:
        del query, top_k, codebase
        call_order.append("retrieval")
        return [chunk]

    def _fake_rerank_chunks(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
    ) -> list[RetrievedChunk]:
        del query, feature
        call_order.append("rerank")
        return chunks

    def _fake_generate_answer(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
        language: str,
        model: str | None,
    ) -> QueryResponse:
        del query, chunks, feature, language, model
        call_order.append("generation")
        return generated

    monkeypatch.setattr(routes, "hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr(routes, "rerank_chunks", _fake_rerank_chunks)
    monkeypatch.setattr(routes, "generate_answer", _fake_generate_answer)

    response = client.post("/api/query", json={"query": "What does MAIN-LOGIC do?"})
    assert response.status_code == 200
    assert call_order == ["retrieval", "rerank", "generation"]


def test_query_passes_codebase_and_top_k_to_retrieval(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()
    generated = _sample_response(chunks=[chunk])
    captured: dict[str, object] = {}

    def _fake_hybrid_search(query: str, top_k: int, codebase: str | None) -> list[RetrievedChunk]:
        captured["query"] = query
        captured["top_k"] = top_k
        captured["codebase"] = codebase
        return [chunk]

    monkeypatch.setattr(routes, "hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr(
        routes,
        "rerank_chunks",
        lambda query, chunks, feature: chunks,
    )
    monkeypatch.setattr(
        routes,
        "generate_answer",
        lambda query, chunks, feature, language, model: generated,
    )

    response = client.post(
        "/api/query",
        json={
            "query": "What does MAIN-LOGIC do?",
            "codebase": "gnucobol",
            "top_k": 7,
        },
    )
    assert response.status_code == 200
    assert captured["query"] == "What does MAIN-LOGIC do?"
    assert captured["top_k"] == 7
    assert captured["codebase"] == "gnucobol"


def test_query_maps_retrieval_failure_to_http_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_hybrid_search(query: str, top_k: int, codebase: str | None) -> list[RetrievedChunk]:
        del query, top_k, codebase
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(routes, "hybrid_search", _fake_hybrid_search)

    response = client.post("/api/query", json={"query": "What does MAIN-LOGIC do?"})
    assert response.status_code == 500
    assert _detail_contains(response, "retrieval failed")


def test_query_maps_generation_failure_to_http_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()

    monkeypatch.setattr(
        routes,
        "hybrid_search",
        lambda query, top_k, codebase: [chunk],
    )
    monkeypatch.setattr(
        routes,
        "rerank_chunks",
        lambda query, chunks, feature: chunks,
    )

    def _fake_generate_answer(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
        language: str,
        model: str | None,
    ) -> QueryResponse:
        del query, chunks, feature, language, model
        raise RuntimeError("openai timeout")

    monkeypatch.setattr(routes, "generate_answer", _fake_generate_answer)

    response = client.post("/api/query", json={"query": "What does MAIN-LOGIC do?"})
    assert response.status_code == 500
    assert _detail_contains(response, "generation failed")


def test_stream_route_streams_text_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()

    monkeypatch.setattr(
        routes,
        "hybrid_search",
        lambda query, top_k, codebase: [chunk],
    )
    monkeypatch.setattr(
        routes,
        "rerank_chunks",
        lambda query, chunks, feature: chunks,
    )
    monkeypatch.setattr(
        routes,
        "stream_answer",
        lambda query, chunks, feature, language, model: iter(["alpha ", "beta"]),
    )

    response = client.post("/api/stream", json={"query": "What does MAIN-LOGIC do?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "alpha beta"


def test_health_returns_deterministic_200_payload(client: TestClient) -> None:
    """Deployment readiness: health route returns stable contract for Render health checks."""
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok"}


def test_codebases_returns_deterministic_200_payload(client: TestClient) -> None:
    """Deployment readiness: codebases route returns configured codebase metadata."""
    response = client.get("/api/codebases")
    assert response.status_code == 200
    payload = response.json()
    assert "codebases" in payload
    codebases = payload["codebases"]
    assert isinstance(codebases, list)
    assert len(codebases) >= 1
    for item in codebases:
        assert "name" in item
        assert "language" in item
        assert "description" in item
        assert isinstance(item["name"], str)
        assert isinstance(item["language"], str)
        assert isinstance(item["description"], str)


def test_query_maps_reranker_failure_to_http_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _sample_chunk()

    monkeypatch.setattr(
        routes,
        "hybrid_search",
        lambda query, top_k, codebase: [chunk],
    )

    def _fake_rerank_chunks(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
    ) -> list[RetrievedChunk]:
        del query, chunks, feature
        raise RuntimeError("cohere unavailable")

    monkeypatch.setattr(routes, "rerank_chunks", _fake_rerank_chunks)

    response = client.post("/api/query", json={"query": "What does MAIN-LOGIC do?"})
    assert response.status_code == 500
    assert _detail_contains(response, "reranking failed")
