"""HTTP transport client for CLI -> FastAPI query integration."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

import httpx

from src.config import DEFAULT_TOP_K, LEGACYLENS_API_URL
from src.types.responses import Confidence, QueryResponse, RetrievedChunk

DEFAULT_API_TIMEOUT_SECONDS: float = 30.0


class ApiClientError(RuntimeError):
    """Base error for CLI API transport/client failures."""


class ApiClientValidationError(ApiClientError, ValueError):
    """Raised when query payload or client options are invalid."""


class ApiClientTransportError(ApiClientError):
    """Raised when network/transport failures prevent API calls."""


class ApiClientHTTPError(ApiClientError):
    """Raised when API responds with non-success HTTP status."""

    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API request failed ({status_code}): {detail}")


class ApiClientResponseError(ApiClientError):
    """Raised when API response payload is missing expected fields."""


@dataclass(frozen=True)
class QueryRequestPayload:
    """Typed request payload for /api/query and /api/stream calls."""

    query: str
    feature: str = "code_explanation"
    codebase: str | None = None
    top_k: int = DEFAULT_TOP_K
    language: str = "cobol"
    model: str | None = None

    def to_json(self) -> dict[str, str | int | None]:
        """Convert payload into API-ready JSON body."""
        normalized_codebase = _normalize_optional_text(self.codebase)
        normalized_model = _normalize_optional_text(self.model)
        return {
            "query": self.query,
            "feature": self.feature,
            "codebase": normalized_codebase,
            "top_k": self.top_k,
            "language": self.language,
            "model": normalized_model,
        }


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip()
    if not normalized:
        raise ApiClientValidationError("base_url must not be blank")
    return normalized.rstrip("/")


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _validate_payload(payload: QueryRequestPayload) -> None:
    if not payload.query.strip():
        raise ApiClientValidationError("query must not be blank")
    if not payload.feature.strip():
        raise ApiClientValidationError("feature must not be blank")
    if payload.top_k <= 0:
        raise ApiClientValidationError("top_k must be greater than 0")
    if not payload.language.strip():
        raise ApiClientValidationError("language must not be blank")


def _validate_timeout(timeout_seconds: float) -> None:
    if timeout_seconds <= 0:
        raise ApiClientValidationError("timeout_seconds must be greater than 0")


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        text = response.text.strip()
        return text if text else "no error detail provided"

    if not isinstance(payload, dict):
        return "no error detail provided"

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):
        messages: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                message = item.get("msg")
                if isinstance(message, str) and message:
                    messages.append(message)
        if messages:
            return "; ".join(messages)

    return "no error detail provided"


def _require_string_field(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if isinstance(value, str):
        return value
    raise ApiClientResponseError(f"response field '{field}' must be a string")


def _optional_string_field(payload: Mapping[str, object], field: str) -> str | None:
    if field not in payload:
        return None
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ApiClientResponseError(f"response field '{field}' must be a string or null")


def _optional_float_field(payload: Mapping[str, object], field: str, default: float) -> float:
    value = payload.get(field, default)
    if isinstance(value, bool):
        raise ApiClientResponseError(f"response field '{field}' must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    raise ApiClientResponseError(f"response field '{field}' must be numeric")


def _parse_confidence(value: object, *, field_name: str) -> Confidence:
    if not isinstance(value, str):
        raise ApiClientResponseError(f"response field '{field_name}' must be a confidence string")
    normalized = value.strip().upper()
    if normalized == Confidence.HIGH.value:
        return Confidence.HIGH
    if normalized == Confidence.MEDIUM.value:
        return Confidence.MEDIUM
    if normalized == Confidence.LOW.value:
        return Confidence.LOW
    raise ApiClientResponseError(f"response field '{field_name}' has invalid confidence '{value}'")


def _parse_int_field(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiClientResponseError(f"response field '{field}' must be an integer")
    return value


def _parse_float_field(payload: Mapping[str, object], field: str, default: float = 0.0) -> float:
    value = payload.get(field, default)
    if isinstance(value, bool):
        raise ApiClientResponseError(f"response field '{field}' must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    raise ApiClientResponseError(f"response field '{field}' must be numeric")


def _parse_chunk_metadata(raw_metadata: object) -> dict[str, str]:
    if raw_metadata is None:
        return {}
    if not isinstance(raw_metadata, dict):
        raise ApiClientResponseError("response chunk field 'metadata' must be an object")

    metadata: dict[str, str] = {}
    for key, value in raw_metadata.items():
        if not isinstance(key, str):
            raise ApiClientResponseError("response chunk metadata keys must be strings")
        if isinstance(value, str):
            metadata[key] = value
        else:
            metadata[key] = str(value)
    return metadata


def _parse_retrieved_chunk(payload: object) -> RetrievedChunk:
    if not isinstance(payload, dict):
        raise ApiClientResponseError("response field 'chunks' must contain objects")

    content = _require_string_field(payload, "content")
    file_path = _require_string_field(payload, "file_path")
    line_start = _parse_int_field(payload, "line_start")
    line_end = _parse_int_field(payload, "line_end")
    name = _require_string_field(payload, "name")
    language = _require_string_field(payload, "language")
    codebase = _require_string_field(payload, "codebase")
    score = _parse_float_field(payload, "score", default=0.0)
    confidence = _parse_confidence(payload.get("confidence"), field_name="chunks[].confidence")
    metadata = _parse_chunk_metadata(payload.get("metadata"))

    return RetrievedChunk(
        content=content,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        name=name,
        language=language,
        codebase=codebase,
        score=score,
        confidence=confidence,
        metadata=metadata,
    )


def _parse_query_response(payload: object) -> QueryResponse:
    if not isinstance(payload, dict):
        raise ApiClientResponseError("query response must be a JSON object")

    answer = _require_string_field(payload, "answer")
    query = _require_string_field(payload, "query")
    feature = _require_string_field(payload, "feature")
    confidence = _parse_confidence(payload.get("confidence"), field_name="confidence")
    codebase_filter = _optional_string_field(payload, "codebase_filter")
    latency_ms = _optional_float_field(payload, "latency_ms", default=0.0)
    model = _optional_string_field(payload, "model") or ""

    raw_chunks = payload.get("chunks")
    if not isinstance(raw_chunks, list):
        raise ApiClientResponseError("response field 'chunks' must be a list")
    chunks = [_parse_retrieved_chunk(chunk_payload) for chunk_payload in raw_chunks]

    return QueryResponse(
        answer=answer,
        chunks=chunks,
        query=query,
        feature=feature,
        confidence=confidence,
        codebase_filter=codebase_filter,
        latency_ms=latency_ms,
        model=model,
    )


def post_query(
    payload: QueryRequestPayload,
    *,
    base_url: str = LEGACYLENS_API_URL,
    timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
) -> QueryResponse:
    """Call POST /api/query and parse the response into QueryResponse."""
    _validate_payload(payload)
    _validate_timeout(timeout_seconds)

    normalized_base_url = _normalize_base_url(base_url)
    query_url = f"{normalized_base_url}/api/query"

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(query_url, json=payload.to_json())
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        raise ApiClientTransportError(f"failed to reach API endpoint '{query_url}': {exc}") from exc

    if response.status_code >= 400:
        raise ApiClientHTTPError(
            status_code=response.status_code,
            detail=_extract_error_detail(response),
        )

    try:
        response_payload = response.json()
    except json.JSONDecodeError as exc:
        raise ApiClientResponseError("query response was not valid JSON") from exc

    return _parse_query_response(response_payload)


def stream_query(
    payload: QueryRequestPayload,
    *,
    base_url: str = LEGACYLENS_API_URL,
    timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
) -> Iterator[str]:
    """Call POST /api/stream and yield text chunks as they arrive."""
    _validate_payload(payload)
    _validate_timeout(timeout_seconds)

    normalized_base_url = _normalize_base_url(base_url)
    stream_url = f"{normalized_base_url}/api/stream"

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            with client.stream("POST", stream_url, json=payload.to_json()) as response:
                if response.status_code >= 400:
                    response.read()
                    raise ApiClientHTTPError(
                        status_code=response.status_code,
                        detail=_extract_error_detail(response),
                    )
                for chunk_text in response.iter_text():
                    if chunk_text:
                        yield chunk_text
    except ApiClientHTTPError:
        raise
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        raise ApiClientTransportError(
            f"failed to reach streaming endpoint '{stream_url}': {exc}"
        ) from exc
