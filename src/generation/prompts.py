"""Prompt templates for LegacyLens generation flows (MVP-011)."""

from __future__ import annotations

from src.config import FEATURES
from src.types.responses import RetrievedChunk

SUPPORTED_LANGUAGES: set[str] = {"cobol"}
DEFAULT_FEATURE: str = "code_explanation"


class PromptValidationError(ValueError):
    """Raised when prompt-builder inputs are invalid."""


def _normalize_feature(feature: str) -> str:
    """Normalize feature name for deterministic fallback behavior."""
    normalized = feature.strip().lower()
    if not normalized:
        return DEFAULT_FEATURE
    return normalized


def _normalize_language(language: str) -> str:
    """Normalize language value for deterministic validation."""
    return language.strip().lower()


def _validate_query(query: str) -> None:
    """Validate query text expected by user prompt and message builders."""
    if not query.strip():
        raise PromptValidationError("query must not be blank")


def _validate_language(language: str) -> None:
    """Validate supported language values for prompt templates."""
    normalized_language = _normalize_language(language)
    if normalized_language not in SUPPORTED_LANGUAGES:
        supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
        raise PromptValidationError(
            f"unsupported language: {normalized_language}. supported languages: {supported}"
        )


def _validate_chunks(chunks: list[RetrievedChunk]) -> None:
    """Validate chunk list input shape."""
    if chunks is None:
        raise PromptValidationError("chunks must not be None")


def _validate_prompt_inputs(query: str, feature: str, language: str) -> None:
    """Validate all prompt-builder inputs that can produce deterministic errors."""
    _validate_query(query=query)
    _validate_language(language=language)
    _normalize_feature(feature=feature)


def _feature_prompt_insert(feature: str) -> str:
    """Return feature-specific system instruction with deterministic fallback."""
    normalized_feature = _normalize_feature(feature)
    if normalized_feature == "code_explanation":
        return (
            "Feature focus: code_explanation.\n"
            "Explain what the relevant COBOL logic does, why it matters, and how key"
            " paragraphs interact."
        )

    if normalized_feature in FEATURES:
        return (
            f"Feature focus: {normalized_feature}.\n"
            "Apply the feature intent while preserving grounding, citation, and"
            " confidence rules."
        )

    return (
        f"Feature focus: {normalized_feature}.\n"
        "Default feature behavior: treat this as code_explanation while preserving"
        " grounding and evidence-only reasoning."
    )


def _language_prompt_insert(language: str) -> str:
    """Return language-specific generation guidance."""
    normalized_language = _normalize_language(language)
    _validate_language(language=normalized_language)

    if normalized_language == "cobol":
        return (
            "Language focus: COBOL.\n"
            "Prefer COBOL terms such as paragraph, section, division, PERFORM, CALL,"
            " and WORKING-STORAGE when they are supported by evidence."
        )

    # This fallback is unreachable due to validation but kept explicit for clarity.
    raise PromptValidationError(f"unsupported language: {normalized_language}")


def _citation_instruction_block() -> str:
    """Return citation rules required by downstream API and UI contracts."""
    return (
        "Citation requirements:\n"
        "- Every material claim must include a citation in file:line format.\n"
        "- Prefer file:start-end when a range is available."
    )


def _confidence_instruction_block() -> str:
    """Return confidence labeling requirements."""
    return (
        "Confidence requirements:\n"
        "- End your answer with Confidence: HIGH, MEDIUM, or LOW.\n"
        "- HIGH = direct and complete evidence.\n"
        "- MEDIUM = partial evidence with minor inference.\n"
        "- LOW = weak or insufficient evidence."
    )


def _safe_line_range(line_start: int, line_end: int) -> tuple[int, int]:
    """Normalize anomalous line ranges into deterministic, non-decreasing values."""
    normalized_start = line_start if line_start >= 0 else 0
    normalized_end = line_end if line_end >= normalized_start else normalized_start
    return normalized_start, normalized_end


def _format_chunk_citation(chunk: RetrievedChunk) -> str:
    """Format chunk source into deterministic file:start-end citation string."""
    file_path = chunk.file_path.strip() if chunk.file_path.strip() else "unknown-file"
    line_start, line_end = _safe_line_range(chunk.line_start, chunk.line_end)
    return f"{file_path}:{line_start}-{line_end}"


def _chunk_name(chunk: RetrievedChunk) -> str:
    """Resolve deterministic chunk display name from fields and metadata."""
    if chunk.name.strip():
        return chunk.name.strip()

    raw_paragraph_name = chunk.metadata.get("paragraph_name")
    if isinstance(raw_paragraph_name, str) and raw_paragraph_name.strip():
        return raw_paragraph_name.strip()

    return "(unknown)"


def _chunk_division(chunk: RetrievedChunk) -> str:
    """Resolve optional division label with safe metadata fallback."""
    raw_division = chunk.metadata.get("division")
    if isinstance(raw_division, str) and raw_division.strip():
        return raw_division.strip()
    return ""


def _format_context_chunks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into deterministic context block for user prompt."""
    _validate_chunks(chunks=chunks)

    if not chunks:
        return (
            "No retrieved context was provided.\n"
            "Treat this as insufficient evidence and avoid unsupported claims."
        )

    formatted_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        lines: list[str] = [
            f"[Chunk {index}]",
            f"Source: {_format_chunk_citation(chunk)}",
            f"Name: {_chunk_name(chunk)}",
        ]

        division = _chunk_division(chunk)
        if division:
            lines.append(f"Division: {division}")

        lines.extend(
            [
                "Content:",
                chunk.content if chunk.content else "(empty chunk content)",
            ]
        )
        formatted_chunks.append("\n".join(lines))

    return "\n\n".join(formatted_chunks)


def build_system_prompt(
    feature: str = DEFAULT_FEATURE,
    language: str = "cobol",
) -> str:
    """Build deterministic system prompt with language + feature inserts."""
    normalized_language = _normalize_language(language)
    _validate_language(language=normalized_language)

    return (
        "You are LegacyLens, a legacy code intelligence assistant.\n"
        "Grounding rule: answer ONLY from the provided retrieved context.\n"
        "If evidence is insufficient, explicitly say the evidence is insufficient.\n\n"
        f"{_language_prompt_insert(language=normalized_language)}\n\n"
        f"{_feature_prompt_insert(feature=feature)}\n\n"
        f"{_citation_instruction_block()}\n\n"
        f"{_confidence_instruction_block()}"
    )


def build_user_prompt(
    query: str,
    chunks: list[RetrievedChunk],
) -> str:
    """Build deterministic user prompt containing query and retrieval context."""
    _validate_query(query=query)
    _validate_chunks(chunks=chunks)

    return (
        "User query:\n"
        f"{query.strip()}\n\n"
        "Retrieved context:\n"
        f"{_format_context_chunks(chunks=chunks)}\n\n"
        "If the context is insufficient, say so and avoid unsupported claims."
    )


def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = DEFAULT_FEATURE,
    language: str = "cobol",
) -> list[dict[str, str]]:
    """Build chat-completions style messages for downstream LLM invocation."""
    _validate_prompt_inputs(query=query, feature=feature, language=language)

    return [
        {"role": "system", "content": build_system_prompt(feature=feature, language=language)},
        {"role": "user", "content": build_user_prompt(query=query, chunks=chunks)},
    ]
