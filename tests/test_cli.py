"""CLI integration tests for MVP-014."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import src.cli.main as cli_main
from src.api.client import ApiClientHTTPError, ApiClientResponseError, ApiClientTransportError
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
        score=0.92,
        confidence=Confidence.HIGH,
        metadata={"paragraph_name": "MAIN-LOGIC"},
    )


def _sample_response() -> QueryResponse:
    chunk = _sample_chunk()
    return QueryResponse(
        answer="MAIN-LOGIC initializes state before downstream processing.",
        chunks=[chunk],
        query="What does MAIN-LOGIC do?",
        feature="code_explanation",
        confidence=Confidence.HIGH,
        codebase_filter="gnucobol",
        latency_ms=18.4,
        model="gpt-4o",
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_query_command_success_renders_response(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[object] = []

    def _fake_post_query(payload: object) -> QueryResponse:
        captured_payloads.append(payload)
        return _sample_response()

    monkeypatch.setattr(cli_main, "post_query", _fake_post_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?"])

    assert result.exit_code == 0
    assert "MAIN-LOGIC initializes state before downstream processing." in result.output
    assert "Confidence: HIGH" in result.output
    assert "Model: gpt-4o" in result.output
    assert "Latency: 18.4ms" in result.output
    assert "data/raw/gnucobol/sample.cob:10-11" in result.output
    assert len(captured_payloads) == 1


def test_query_command_passes_options_to_api_payload(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[object] = []

    def _fake_post_query(payload: object) -> QueryResponse:
        captured_payloads.append(payload)
        return _sample_response()

    monkeypatch.setattr(cli_main, "post_query", _fake_post_query)

    result = runner.invoke(
        cli_main.cli,
        [
            "query",
            "Explain MAIN-LOGIC",
            "--feature",
            "dependency_mapping",
            "--codebase",
            "gnucobol",
            "--top-k",
            "7",
            "--language",
            "cobol",
            "--model",
            "gpt-4o-mini",
        ],
    )

    assert result.exit_code == 0
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert getattr(payload, "query") == "Explain MAIN-LOGIC"
    assert getattr(payload, "feature") == "dependency_mapping"
    assert getattr(payload, "codebase") == "gnucobol"
    assert getattr(payload, "top_k") == 7
    assert getattr(payload, "language") == "cobol"
    assert getattr(payload, "model") == "gpt-4o-mini"


def test_query_command_rejects_blank_query(
    runner: CliRunner,
) -> None:
    result = runner.invoke(cli_main.cli, ["query", "   "])

    assert result.exit_code != 0
    assert "query must not be blank" in result.output


def test_query_command_rejects_invalid_top_k(
    runner: CliRunner,
) -> None:
    result = runner.invoke(cli_main.cli, ["query", "test", "--top-k", "0"])

    assert result.exit_code != 0
    assert "top-k" in result.output


def test_query_command_maps_transport_failure_to_nonzero_exit(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_post_query(payload: object) -> QueryResponse:
        del payload
        raise ApiClientTransportError("request timed out")

    monkeypatch.setattr(cli_main, "post_query", _fake_post_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?"])

    assert result.exit_code != 0
    assert "Transport error" in result.output
    assert "request timed out" in result.output


def test_query_command_maps_api_4xx_failure_to_nonzero_exit(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_post_query(payload: object) -> QueryResponse:
        del payload
        raise ApiClientHTTPError(status_code=422, detail="query must not be blank")

    monkeypatch.setattr(cli_main, "post_query", _fake_post_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?"])

    assert result.exit_code != 0
    assert "API request failed (422)" in result.output
    assert "query must not be blank" in result.output


def test_query_command_maps_api_5xx_failure_to_nonzero_exit(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_post_query(payload: object) -> QueryResponse:
        del payload
        raise ApiClientHTTPError(status_code=500, detail="retrieval failed")

    monkeypatch.setattr(cli_main, "post_query", _fake_post_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?"])

    assert result.exit_code != 0
    assert "API request failed (500)" in result.output
    assert "retrieval failed" in result.output


def test_query_command_stream_mode_uses_stream_endpoint(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[object] = []

    def _fake_stream_query(payload: object) -> list[str]:
        captured_payloads.append(payload)
        return ["alpha ", "beta"]

    def _unexpected_post_query(payload: object) -> QueryResponse:
        del payload
        raise AssertionError("post_query should not be called when --stream is set")

    monkeypatch.setattr(cli_main, "stream_query", _fake_stream_query)
    monkeypatch.setattr(cli_main, "post_query", _unexpected_post_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?", "--stream"])

    assert result.exit_code == 0
    assert "alpha beta" in result.output
    assert len(captured_payloads) == 1


def test_query_command_stream_mode_maps_response_errors(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_stream_query(payload: object) -> list[str]:
        del payload
        raise ApiClientResponseError("stream closed unexpectedly")

    monkeypatch.setattr(cli_main, "stream_query", _fake_stream_query)

    result = runner.invoke(cli_main.cli, ["query", "What does MAIN-LOGIC do?", "--stream"])

    assert result.exit_code != 0
    assert "Invalid API response" in result.output
    assert "stream closed unexpectedly" in result.output
