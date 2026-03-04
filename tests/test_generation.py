"""Unit tests for prompt template module (MVP-011)."""

from __future__ import annotations

import pytest

from src.generation import llm
from src.generation.llm import (
    GenerationError,
    GenerationResponseError,
    GenerationValidationError,
    generate_answer,
)
from src.generation.prompts import (
    PromptValidationError,
    build_messages,
    build_system_prompt,
    build_user_prompt,
)
from src.types.responses import Confidence, QueryResponse, RetrievedChunk


@pytest.fixture
def sample_retrieved_chunks() -> list[RetrievedChunk]:
    """Build deterministic sample retrieval output for prompt tests."""
    return [
        RetrievedChunk(
            content="MAIN-LOGIC. PERFORM INIT-DATA.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=10,
            line_end=11,
            name="MAIN-LOGIC",
            language="cobol",
            codebase="gnucobol",
            score=0.82,
            confidence=Confidence.HIGH,
            metadata={"division": "PROCEDURE", "paragraph_name": "MAIN-LOGIC"},
        ),
        RetrievedChunk(
            content="INIT-DATA. MOVE 1 TO WS-COUNT.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=20,
            line_end=21,
            name="INIT-DATA",
            language="cobol",
            codebase="gnucobol",
            score=0.74,
            confidence=Confidence.MEDIUM,
            metadata={"division": "PROCEDURE", "paragraph_name": "INIT-DATA"},
        ),
    ]


def test_build_system_prompt_returns_string() -> None:
    system_prompt = build_system_prompt()
    assert isinstance(system_prompt, str)


def test_build_user_prompt_returns_string(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    user_prompt = build_user_prompt(
        query="Explain what MAIN-LOGIC does.",
        chunks=sample_retrieved_chunks,
    )
    assert isinstance(user_prompt, str)


def test_build_messages_returns_role_ordered_messages(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    messages = build_messages(
        query="Explain what MAIN-LOGIC does.",
        chunks=sample_retrieved_chunks,
    )
    assert isinstance(messages, list)
    assert messages == [
        {"role": "system", "content": build_system_prompt()},
        {
            "role": "user",
            "content": build_user_prompt(
                query="Explain what MAIN-LOGIC does.",
                chunks=sample_retrieved_chunks,
            ),
        },
    ]


def test_blank_query_raises_prompt_validation_error() -> None:
    with pytest.raises(PromptValidationError, match="query must not be blank"):
        build_user_prompt(query="   ", chunks=[])


def test_unsupported_language_raises_prompt_validation_error() -> None:
    with pytest.raises(PromptValidationError, match="unsupported language"):
        build_system_prompt(language="rust")


def test_system_prompt_includes_file_line_citation_instruction() -> None:
    system_prompt = build_system_prompt()
    assert "file:line" in system_prompt


def test_system_prompt_includes_high_medium_low_confidence_instruction() -> None:
    system_prompt = build_system_prompt()
    assert "HIGH" in system_prompt
    assert "MEDIUM" in system_prompt
    assert "LOW" in system_prompt


def test_user_prompt_context_includes_source_lines_name_and_content(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    user_prompt = build_user_prompt(
        query="Explain what MAIN-LOGIC does.",
        chunks=sample_retrieved_chunks,
    )
    assert "Source: data/raw/gnucobol/sample.cob:10-11" in user_prompt
    assert "Name: MAIN-LOGIC" in user_prompt
    assert "MAIN-LOGIC. PERFORM INIT-DATA." in user_prompt


def test_unknown_feature_falls_back_deterministically() -> None:
    first = build_system_prompt(feature="totally_unknown_feature")
    second = build_system_prompt(feature="totally_unknown_feature")
    assert first == second
    assert "Default feature behavior" in first


def test_empty_chunk_list_includes_uncertainty_guidance() -> None:
    user_prompt = build_user_prompt(
        query="What does this code do?",
        chunks=[],
    )
    assert "No retrieved context was provided." in user_prompt
    assert "insufficient evidence" in user_prompt


def test_user_prompt_output_is_deterministic_for_identical_inputs(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    first = build_user_prompt(
        query="Explain what MAIN-LOGIC does.",
        chunks=sample_retrieved_chunks,
    )
    second = build_user_prompt(
        query="Explain what MAIN-LOGIC does.",
        chunks=sample_retrieved_chunks,
    )
    assert first == second


def test_context_format_recovers_from_line_range_anomaly() -> None:
    anomalous_chunk = RetrievedChunk(
        content="ANOMALOUS-LOGIC. STOP RUN.",
        file_path="data/raw/gnucobol/anomaly.cob",
        line_start=50,
        line_end=49,
        name="ANOMALOUS-LOGIC",
        language="cobol",
        codebase="gnucobol",
        score=0.61,
        confidence=Confidence.MEDIUM,
        metadata={"division": "PROCEDURE"},
    )
    user_prompt = build_user_prompt(
        query="Explain ANOMALOUS-LOGIC.",
        chunks=[anomalous_chunk],
    )
    assert "Source: data/raw/gnucobol/anomaly.cob:50-50" in user_prompt


def test_context_format_handles_missing_metadata_fields_without_crashing() -> None:
    chunk_with_missing_metadata = RetrievedChunk(
        content="FALLBACK-PARA. STOP RUN.",
        file_path="data/raw/gnucobol/fallback.cob",
        line_start=1,
        line_end=1,
        name="",
        language="cobol",
        codebase="gnucobol",
        score=0.55,
        confidence=Confidence.MEDIUM,
        metadata={},
    )

    user_prompt = build_user_prompt(
        query="Explain FALLBACK-PARA.",
        chunks=[chunk_with_missing_metadata],
    )

    assert "Source: data/raw/gnucobol/fallback.cob:1-1" in user_prompt
    assert "Name: (unknown)" in user_prompt


def test_generate_answer_returns_query_response_contract(
    monkeypatch: pytest.MonkeyPatch,
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    def _fake_build_messages(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
        language: str,
    ) -> list[dict[str, str]]:
        assert query == "Explain MAIN-LOGIC."
        assert chunks == sample_retrieved_chunks
        assert feature == "code_explanation"
        assert language == "cobol"
        return [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]

    def _fake_complete_with_fallback(
        *, messages: list[dict[str, str]], model: str
    ) -> tuple[str, str]:
        assert messages == [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]
        assert model == "gpt-4o"
        return (
            "MAIN-LOGIC initializes values.\n"
            "Citations: data/raw/gnucobol/sample.cob:10-11\n"
            "Confidence: HIGH",
            "gpt-4o",
        )

    clock = iter([1000.0, 1015.0])
    monkeypatch.setattr(llm, "build_messages", _fake_build_messages)
    monkeypatch.setattr(llm, "_complete_with_fallback", _fake_complete_with_fallback)
    monkeypatch.setattr(llm, "_now_ms", lambda: next(clock))

    response = generate_answer(
        query="Explain MAIN-LOGIC.",
        chunks=sample_retrieved_chunks,
    )

    assert isinstance(response, QueryResponse)
    assert response.query == "Explain MAIN-LOGIC."
    assert response.feature == "code_explanation"
    assert response.chunks == sample_retrieved_chunks
    assert response.model == "gpt-4o"
    assert response.confidence == Confidence.HIGH
    assert response.latency_ms == pytest.approx(15.0)
    assert "MAIN-LOGIC initializes values." in response.answer


def test_generate_answer_blank_query_raises_generation_validation_error() -> None:
    with pytest.raises(GenerationValidationError, match="query must not be blank"):
        generate_answer(query="   ", chunks=[])


def test_generate_answer_none_chunks_raises_generation_validation_error() -> None:
    with pytest.raises(GenerationValidationError, match="chunks must not be None"):
        generate_answer(query="Explain this", chunks=None)  # type: ignore[arg-type]


def test_generate_answer_calls_build_messages_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    calls: list[tuple[str, list[RetrievedChunk], str, str]] = []

    def _fake_build_messages(
        query: str,
        chunks: list[RetrievedChunk],
        feature: str,
        language: str,
    ) -> list[dict[str, str]]:
        calls.append((query, chunks, feature, language))
        return [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]

    monkeypatch.setattr(llm, "build_messages", _fake_build_messages)
    monkeypatch.setattr(
        llm,
        "_complete_with_fallback",
        lambda *, messages, model: ("Answer.\nConfidence: MEDIUM", model),
    )
    clock = iter([10.0, 15.0])
    monkeypatch.setattr(llm, "_now_ms", lambda: next(clock))

    _ = generate_answer(
        query="Explain MAIN-LOGIC.",
        chunks=sample_retrieved_chunks,
        feature="code_explanation",
        language="cobol",
    )

    assert len(calls) == 1
    assert calls[0] == (
        "Explain MAIN-LOGIC.",
        sample_retrieved_chunks,
        "code_explanation",
        "cobol",
    )


def test_complete_with_fallback_primary_model_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_order: list[str] = []

    def _fake_complete_once(
        *, client: object, messages: list[dict[str, str]], model: str
    ) -> str:
        del client, messages
        call_order.append(model)
        return "Primary answer.\nConfidence: HIGH"

    monkeypatch.setattr(llm, "_build_openai_client", lambda: object())
    monkeypatch.setattr(llm, "_complete_once", _fake_complete_once)

    content, used_model = llm._complete_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o",
    )

    assert used_model == "gpt-4o"
    assert content.startswith("Primary answer.")
    assert call_order == ["gpt-4o"]


def test_complete_with_fallback_uses_fallback_on_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_order: list[str] = []

    def _fake_complete_once(
        *, client: object, messages: list[dict[str, str]], model: str
    ) -> str:
        del client, messages
        call_order.append(model)
        if model == "gpt-4o":
            raise TimeoutError("timed out")
        return "Fallback answer.\nConfidence: MEDIUM"

    monkeypatch.setattr(llm, "_build_openai_client", lambda: object())
    monkeypatch.setattr(llm, "_complete_once", _fake_complete_once)
    monkeypatch.setattr(llm, "LLM_FALLBACK_MODEL", "gpt-4o-mini")

    content, used_model = llm._complete_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o",
    )

    assert used_model == "gpt-4o-mini"
    assert content.startswith("Fallback answer.")
    assert call_order == ["gpt-4o", "gpt-4o-mini"]


def test_complete_with_fallback_raises_generation_error_when_both_models_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_complete_once(
        *, client: object, messages: list[dict[str, str]], model: str
    ) -> str:
        del client, messages, model
        raise TimeoutError("rate limit")

    monkeypatch.setattr(llm, "_build_openai_client", lambda: object())
    monkeypatch.setattr(llm, "_complete_once", _fake_complete_once)
    monkeypatch.setattr(llm, "LLM_FALLBACK_MODEL", "gpt-4o-mini")

    with pytest.raises(GenerationError, match="primary model"):
        llm._complete_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o",
        )


def test_parse_confidence_maps_high_medium_low_labels() -> None:
    assert llm._parse_confidence("Confidence: HIGH") == Confidence.HIGH
    assert llm._parse_confidence("confidence: medium") == Confidence.MEDIUM
    assert llm._parse_confidence("Confidence: LOW") == Confidence.LOW


def test_parse_confidence_defaults_to_low_when_missing_or_invalid_label() -> None:
    assert llm._parse_confidence("No confidence label here.") == Confidence.LOW
    assert llm._parse_confidence("Confidence: CERTAIN") == Confidence.LOW


def test_extract_citations_returns_unique_ordered_matches() -> None:
    text = (
        "See data/raw/gnucobol/sample.cob:10 and "
        "data/raw/gnucobol/sample.cob:10 again. "
        "Then data/raw/gnucobol/other.cob:20-25."
    )
    assert llm._extract_citations(text) == [
        "data/raw/gnucobol/sample.cob:10",
        "data/raw/gnucobol/other.cob:20-25",
    ]


def test_generate_answer_is_deterministic_for_identical_mocked_inputs(
    monkeypatch: pytest.MonkeyPatch,
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    monkeypatch.setattr(
        llm,
        "build_messages",
        lambda query, chunks, feature, language: [
            {"role": "system", "content": f"{feature}:{language}"},
            {"role": "user", "content": f"{query}:{len(chunks)}"},
        ],
    )
    monkeypatch.setattr(
        llm,
        "_complete_with_fallback",
        lambda *, messages, model: (
            "Deterministic answer.\nConfidence: HIGH\n"
            "Citations: data/raw/gnucobol/sample.cob:10-11",
            model,
        ),
    )
    clock = iter([100.0, 150.0, 200.0, 250.0])
    monkeypatch.setattr(llm, "_now_ms", lambda: next(clock))

    first = generate_answer(
        query="Explain MAIN-LOGIC.",
        chunks=sample_retrieved_chunks,
        feature="code_explanation",
        language="cobol",
    )
    second = generate_answer(
        query="Explain MAIN-LOGIC.",
        chunks=sample_retrieved_chunks,
        feature="code_explanation",
        language="cobol",
    )

    assert first == second


def test_complete_once_raises_typed_error_on_malformed_response() -> None:
    class _FakeCompletions:
        def create(
            self,
            *,
            model: str,
            messages: list[dict[str, str]],
            temperature: float,
        ) -> dict[str, list[dict[str, str]]]:
            del model, messages, temperature
            return {"choices": []}

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    with pytest.raises(GenerationResponseError, match="Malformed completion response"):
        llm._complete_once(
            client=_FakeClient(),
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4o",
        )
