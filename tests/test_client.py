"""Direct unit tests for src.api.client (MVP-014)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.api.client import (
    ApiClientHTTPError,
    ApiClientResponseError,
    ApiClientTransportError,
    ApiClientValidationError,
    QueryRequestPayload,
    post_query,
    stream_query,
)
from src.types.responses import Confidence


def _valid_query_payload() -> QueryRequestPayload:
    return QueryRequestPayload(
        query="What does MAIN-LOGIC do?",
        feature="code_explanation",
        codebase="gnucobol",
        top_k=10,
        language="cobol",
        model=None,
    )


def _valid_query_response_json() -> dict:
    return {
        "answer": "MAIN-LOGIC initializes state.",
        "chunks": [
            {
                "content": "MAIN-LOGIC. PERFORM INIT.",
                "file_path": "data/raw/gnucobol/sample.cob",
                "line_start": 10,
                "line_end": 11,
                "name": "MAIN-LOGIC",
                "language": "cobol",
                "codebase": "gnucobol",
                "score": 0.92,
                "confidence": "HIGH",
                "metadata": {},
            }
        ],
        "query": "What does MAIN-LOGIC do?",
        "feature": "code_explanation",
        "confidence": "HIGH",
        "codebase_filter": "gnucobol",
        "latency_ms": 18.4,
        "model": "gpt-4o",
    }


def test_post_query_success_returns_parsed_response() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _valid_query_response_json()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        result = post_query(_valid_query_payload(), base_url="http://test")

    assert result.answer == "MAIN-LOGIC initializes state."
    assert result.query == "What does MAIN-LOGIC do?"
    assert result.feature == "code_explanation"
    assert result.confidence == Confidence.HIGH
    assert result.model == "gpt-4o"
    assert result.latency_ms == 18.4
    assert len(result.chunks) == 1
    assert result.chunks[0].file_path == "data/raw/gnucobol/sample.cob"
    assert result.chunks[0].line_start == 10
    assert result.chunks[0].line_end == 11


def test_post_query_http_4xx_raises_api_client_http_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {"detail": "query must not be blank"}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientHTTPError) as exc_info:
            post_query(_valid_query_payload(), base_url="http://test")

    assert exc_info.value.status_code == 422
    assert "query must not be blank" in exc_info.value.detail


def test_post_query_http_5xx_raises_api_client_http_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"detail": "retrieval failed"}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientHTTPError) as exc_info:
            post_query(_valid_query_payload(), base_url="http://test")

    assert exc_info.value.status_code == 500
    assert "retrieval failed" in exc_info.value.detail


def test_post_query_transport_error_raises_api_client_transport_error() -> None:
    import httpx

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("request timed out")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientTransportError) as exc_info:
            post_query(_valid_query_payload(), base_url="http://test")

    assert "timed out" in str(exc_info.value)


def test_post_query_blank_query_raises_validation_error() -> None:
    payload = QueryRequestPayload(query="   ", feature="code_explanation")

    with pytest.raises(ApiClientValidationError) as exc_info:
        post_query(payload, base_url="http://test")

    assert "query must not be blank" in str(exc_info.value)


def test_post_query_invalid_top_k_raises_validation_error() -> None:
    payload = QueryRequestPayload(
        query="test",
        feature="code_explanation",
        top_k=0,
    )

    with pytest.raises(ApiClientValidationError) as exc_info:
        post_query(payload, base_url="http://test")

    assert "top_k" in str(exc_info.value)


def test_post_query_malformed_json_raises_response_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientResponseError) as exc_info:
            post_query(_valid_query_payload(), base_url="http://test")

    assert "JSON" in str(exc_info.value)


def test_post_query_missing_required_field_raises_response_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "chunks": [],
        "query": "test",
        "feature": "code_explanation",
        "confidence": "HIGH",
    }

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientResponseError) as exc_info:
            post_query(_valid_query_payload(), base_url="http://test")

    assert "answer" in str(exc_info.value)


def test_stream_query_success_yields_text_chunks() -> None:
    mock_stream_response = MagicMock()
    mock_stream_response.status_code = 200
    mock_stream_response.iter_text.return_value = iter(["alpha ", "beta"])

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_response)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        chunks = list(stream_query(_valid_query_payload(), base_url="http://test"))

    assert chunks == ["alpha ", "beta"]


def test_stream_query_http_4xx_raises_api_client_http_error() -> None:
    mock_stream_response = MagicMock()
    mock_stream_response.status_code = 422
    mock_stream_response.read = MagicMock()
    mock_stream_response.json.return_value = {"detail": "validation failed"}

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_response)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientHTTPError) as exc_info:
            list(stream_query(_valid_query_payload(), base_url="http://test"))

    assert exc_info.value.status_code == 422
    assert "validation failed" in exc_info.value.detail
    mock_stream_response.read.assert_called_once()


def test_stream_query_transport_error_raises_api_client_transport_error() -> None:
    import httpx

    mock_client = MagicMock()
    mock_client.stream.side_effect = httpx.RequestError("connection refused")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("src.api.client.httpx.Client", return_value=mock_client):
        with pytest.raises(ApiClientTransportError) as exc_info:
            list(stream_query(_valid_query_payload(), base_url="http://test"))

    assert "connection" in str(exc_info.value).lower() or "refused" in str(exc_info.value).lower()
