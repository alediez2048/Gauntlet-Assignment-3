"""LLM runtime for LegacyLens generation flows (MVP-012)."""

from __future__ import annotations

import importlib
import re
import time
from types import ModuleType
from typing import Iterator

from src.config import LLM_FALLBACK_MODEL, LLM_MODEL, OPENAI_API_KEY
from src.generation.prompts import build_messages
from src.types.responses import Confidence, QueryResponse, RetrievedChunk

CONFIDENCE_PATTERN = re.compile(r"\bconfidence\s*:\s*(?P<label>HIGH|MEDIUM|LOW)\b", re.IGNORECASE)
CITATION_PATTERN = re.compile(
    r"(?P<citation>[A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+:\d+(?:-\d+)?)"
)


class GenerationError(RuntimeError):
    """Raised for transport/runtime generation failures."""


class GenerationValidationError(GenerationError, ValueError):
    """Raised when generation inputs are invalid."""


class GenerationConfigError(GenerationError):
    """Raised when generation configuration is missing or invalid."""


class GenerationResponseError(GenerationError):
    """Raised when model responses do not match expected shape."""


def _now_ms() -> float:
    """Return high-resolution monotonic time in milliseconds."""
    return time.perf_counter() * 1000.0


def _validate_generation_inputs(
    query: str,
    chunks: list[RetrievedChunk] | None,
) -> None:
    """Validate generation inputs with deterministic error messages."""
    if not query.strip():
        raise GenerationValidationError("query must not be blank")
    if chunks is None:
        raise GenerationValidationError("chunks must not be None")


def _normalize_model_name(model: str | None) -> str:
    """Normalize model selection with deterministic fallback behavior."""
    if model is None:
        return LLM_MODEL

    normalized_model = model.strip()
    if normalized_model:
        return normalized_model
    return LLM_MODEL


def _import_openai_module() -> ModuleType:
    """Import openai lazily to keep test environments lightweight."""
    try:
        return importlib.import_module("openai")
    except ModuleNotFoundError as exc:
        raise GenerationConfigError(
            "openai is not installed. Install dependencies before generation."
        ) from exc


def _build_openai_client() -> object:
    """Build OpenAI client from configured API key."""
    if not OPENAI_API_KEY:
        raise GenerationConfigError(
            "OPENAI_API_KEY is missing. Set it in your environment or .env file."
        )

    openai_module = _import_openai_module()
    client_class = getattr(openai_module, "OpenAI", None)
    if not callable(client_class):
        raise GenerationConfigError("OpenAI client class is unavailable in installed SDK.")

    try:
        return client_class(api_key=OPENAI_API_KEY)
    except (TypeError, ValueError) as exc:
        raise GenerationConfigError(
            "Failed to create OpenAI client. Verify OPENAI_API_KEY configuration."
        ) from exc


def _get_chat_completions_api(client: object) -> object:
    """Get chat completions API surface from OpenAI client."""
    chat_api = getattr(client, "chat", None)
    if chat_api is None:
        raise GenerationError("OpenAI client is missing chat interface.")

    completions_api = getattr(chat_api, "completions", None)
    if completions_api is None:
        raise GenerationError("OpenAI client is missing chat completions interface.")

    create_method = getattr(completions_api, "create", None)
    if not callable(create_method):
        raise GenerationError("OpenAI client chat completions interface is invalid.")

    return completions_api


def _flatten_content_parts(parts: list[object]) -> str:
    """Flatten content parts list into deterministic plain text."""
    segments: list[str] = []
    for part in parts:
        if isinstance(part, str):
            segments.append(part)
            continue

        if isinstance(part, dict):
            raw_text = part.get("text")
            if isinstance(raw_text, str):
                segments.append(raw_text)
            continue

        raw_text_attr = getattr(part, "text", None)
        if isinstance(raw_text_attr, str):
            segments.append(raw_text_attr)

    return "".join(segments)


def _extract_message_content(response: object) -> str:
    """Extract assistant message content from chat-completion response."""
    if isinstance(response, dict):
        raw_choices = response.get("choices")
    else:
        raw_choices = getattr(response, "choices", None)

    if not isinstance(raw_choices, list) or not raw_choices:
        raise GenerationResponseError("Malformed completion response: missing choices.")

    first_choice = raw_choices[0]
    if isinstance(first_choice, dict):
        raw_message = first_choice.get("message")
    else:
        raw_message = getattr(first_choice, "message", None)

    if raw_message is None:
        raise GenerationResponseError("Malformed completion response: missing message.")

    if isinstance(raw_message, dict):
        raw_content = raw_message.get("content")
    else:
        raw_content = getattr(raw_message, "content", None)

    if isinstance(raw_content, str):
        return raw_content.strip()
    if isinstance(raw_content, list):
        return _flatten_content_parts(raw_content).strip()

    raise GenerationResponseError(
        "Malformed completion response: missing assistant message content."
    )


def _extract_stream_delta(event: object) -> str:
    """Extract streaming delta text from one chat-completion stream event."""
    if isinstance(event, dict):
        raw_choices = event.get("choices")
    else:
        raw_choices = getattr(event, "choices", None)

    if not isinstance(raw_choices, list) or not raw_choices:
        return ""

    first_choice = raw_choices[0]
    if isinstance(first_choice, dict):
        raw_delta = first_choice.get("delta")
    else:
        raw_delta = getattr(first_choice, "delta", None)

    if raw_delta is None:
        return ""

    if isinstance(raw_delta, dict):
        raw_content = raw_delta.get("content", "")
    else:
        raw_content = getattr(raw_delta, "content", "")

    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        return _flatten_content_parts(raw_content)

    return ""


def _complete_once(
    *,
    client: object,
    messages: list[dict[str, str]],
    model: str,
) -> str:
    """Execute one non-streaming chat completion call."""
    completions_api = _get_chat_completions_api(client)

    response = completions_api.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return _extract_message_content(response)


def _stream_once(
    *,
    client: object,
    messages: list[dict[str, str]],
    model: str,
) -> Iterator[str]:
    """Execute one streaming chat completion call."""
    completions_api = _get_chat_completions_api(client)
    stream_response = completions_api.create(
        model=model,
        messages=messages,
        temperature=0,
        stream=True,
    )

    iterator_method = getattr(stream_response, "__iter__", None)
    if not callable(iterator_method):
        raise GenerationResponseError("Malformed streaming response: expected an iterator.")

    for event in stream_response:
        delta_text = _extract_stream_delta(event)
        if delta_text:
            yield delta_text


def _is_retryable_error(exc: Exception) -> bool:
    """Return whether an exception likely represents retryable transport failure."""
    if isinstance(exc, TimeoutError):
        return True

    error_name = exc.__class__.__name__.lower()
    message = str(exc).lower()

    if error_name in {"apitimeouterror", "ratelimiterror", "apiconnectionerror"}:
        return True

    if "timeout" in error_name or "timeout" in message:
        return True
    if "rate" in error_name and "limit" in error_name:
        return True
    if "rate limit" in message or "ratelimit" in message:
        return True
    if "connection" in error_name and "error" in error_name:
        return True

    return False


def _complete_with_fallback(
    *,
    messages: list[dict[str, str]],
    model: str,
) -> tuple[str, str]:
    """Run completion with fallback model on retryable transport failures."""
    client = _build_openai_client()
    primary_model = _normalize_model_name(model)
    fallback_model = _normalize_model_name(LLM_FALLBACK_MODEL)
    primary_error: Exception | None = None

    try:
        content = _complete_once(client=client, messages=messages, model=primary_model)
        return content, primary_model
    except Exception as primary_exc:
        primary_error = primary_exc
        if not _is_retryable_error(primary_exc):
            if isinstance(primary_exc, GenerationError):
                raise
            raise GenerationError(
                f"Generation failed using model '{primary_model}'."
            ) from primary_exc

    if primary_error is None:
        raise GenerationError(
            f"Generation failed using model '{primary_model}' before fallback handling."
        )

    if fallback_model == primary_model:
        raise GenerationError(
            f"Generation failed using model '{primary_model}', and no distinct fallback model is configured."
        ) from primary_error

    try:
        content = _complete_once(client=client, messages=messages, model=fallback_model)
        return content, fallback_model
    except Exception as fallback_exc:
        raise GenerationError(
            f"Generation failed for primary model '{primary_model}' and fallback model '{fallback_model}'."
        ) from fallback_exc


def _parse_confidence(text: str) -> Confidence:
    """Parse confidence label from model output with deterministic LOW fallback."""
    match = CONFIDENCE_PATTERN.search(text)
    if match is None:
        return Confidence.LOW

    label = match.group("label").upper()
    if label == Confidence.HIGH.value:
        return Confidence.HIGH
    if label == Confidence.MEDIUM.value:
        return Confidence.MEDIUM
    if label == Confidence.LOW.value:
        return Confidence.LOW

    return Confidence.LOW


def _extract_citations(text: str) -> list[str]:
    """Extract unique citation tokens in first-seen order."""
    citations: list[str] = []
    seen: set[str] = set()

    for match in CITATION_PATTERN.finditer(text):
        citation = match.group("citation")
        if citation in seen:
            continue
        citations.append(citation)
        seen.add(citation)

    return citations


def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
    model: str | None = None,
) -> QueryResponse:
    """Generate a grounded answer from query + retrieved chunks."""
    _validate_generation_inputs(query=query, chunks=chunks)
    start_ms = _now_ms()

    messages = build_messages(
        query=query,
        chunks=chunks,
        feature=feature,
        language=language,
    )

    selected_model = _normalize_model_name(model)
    output_text, used_model = _complete_with_fallback(
        messages=messages,
        model=selected_model,
    )

    confidence = _parse_confidence(output_text)
    _extract_citations(output_text)
    latency_ms = _now_ms() - start_ms

    return QueryResponse(
        answer=output_text,
        chunks=chunks,
        query=query,
        feature=feature,
        confidence=confidence,
        model=used_model,
        latency_ms=latency_ms,
    )


def stream_answer(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
    model: str | None = None,
) -> Iterator[str]:
    """Stream answer chunks from OpenAI with fallback on retryable failures."""
    _validate_generation_inputs(query=query, chunks=chunks)

    messages = build_messages(
        query=query,
        chunks=chunks,
        feature=feature,
        language=language,
    )

    selected_model = _normalize_model_name(model)
    fallback_model = _normalize_model_name(LLM_FALLBACK_MODEL)
    client = _build_openai_client()
    primary_error: Exception | None = None

    try:
        yield from _stream_once(client=client, messages=messages, model=selected_model)
        return
    except Exception as primary_exc:
        primary_error = primary_exc
        if not _is_retryable_error(primary_exc):
            if isinstance(primary_exc, GenerationError):
                raise
            raise GenerationError(
                f"Streaming generation failed using model '{selected_model}'."
            ) from primary_exc

    if primary_error is None:
        raise GenerationError(
            f"Streaming generation failed using model '{selected_model}' before fallback handling."
        )

    if fallback_model == selected_model:
        raise GenerationError(
            f"Streaming generation failed using model '{selected_model}', and no distinct fallback model is configured."
        ) from primary_error

    try:
        yield from _stream_once(client=client, messages=messages, model=fallback_model)
    except Exception as fallback_exc:
        raise GenerationError(
            f"Streaming generation failed for primary model '{selected_model}' and fallback model '{fallback_model}'."
        ) from fallback_exc
