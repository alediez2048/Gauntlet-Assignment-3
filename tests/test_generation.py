"""Unit tests for prompt template module (MVP-011)."""

from __future__ import annotations

import pytest

from src.generation.prompts import (
    PromptValidationError,
    build_messages,
    build_system_prompt,
    build_user_prompt,
)
from src.types.responses import Confidence, RetrievedChunk


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
