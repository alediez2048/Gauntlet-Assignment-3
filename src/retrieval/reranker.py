"""Metadata-first reranking for retrieval candidates (MVP-010)."""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import replace
from types import ModuleType
from typing import Protocol

from src.config import COHERE_API_KEY
from src.types.responses import Confidence, RetrievedChunk

LOGGER = logging.getLogger(__name__)

COHERE_RERANK_MODEL = "rerank-v3.5"
METADATA_BLEND_WEIGHT = 0.40
COHERE_BLEND_WEIGHT = 0.60

PARAGRAPH_NAME_BOOST = 0.20
DIVISION_BOOST = 0.10
CODEBASE_BOOST = 0.03
LANGUAGE_BOOST = 0.02
FILE_PATH_OVERLAP_BOOST = 0.05
DEPENDENCY_OVERLAP_BOOST = 0.05
FEATURE_DEPENDENCY_BOOST = 0.05
MAX_METADATA_BOOST = 0.30

HIGH_CONFIDENCE_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_THRESHOLD = 0.45
EQUAL_SCORE_NORMALIZED_VALUE = 0.50

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

DIVISION_HINTS: dict[str, set[str]] = {
    "PROCEDURE": {
        "procedure",
        "perform",
        "paragraph",
        "logic",
        "flow",
        "execution",
    },
    "DATA": {
        "data",
        "working-storage",
        "field",
        "record",
        "copybook",
    },
    "IDENTIFICATION": {"identification", "program-id"},
    "ENVIRONMENT": {"environment", "configuration", "file-control"},
}


class RerankerValidationError(ValueError):
    """Raised when reranker inputs are invalid."""


class CohereRerankError(RuntimeError):
    """Raised when Cohere reranking fails."""


class _CohereClientProtocol(Protocol):
    """Protocol for the subset of Cohere client used by reranker."""

    def rerank(
        self,
        *,
        model: str,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> object:
        """Return response with ranked results."""


def _validate_inputs(query: str, chunks: list[RetrievedChunk]) -> None:
    """Validate reranker inputs with deterministic error messages."""
    if not query.strip():
        raise RerankerValidationError("query must not be blank")
    if chunks is None:
        raise RerankerValidationError("chunks must not be None")


def _tokenize_text(text: str) -> set[str]:
    """Tokenize a string into lowercased identifier-like terms."""
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _tokenize_query(query: str) -> set[str]:
    """Tokenize user query for deterministic metadata matching."""
    return _tokenize_text(query)


def _metadata_value(chunk: RetrievedChunk, key: str, fallback: str) -> str:
    """Get metadata value as string with safe fallback."""
    raw_value = chunk.metadata.get(key)
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return str(raw_value)
    return fallback


def _dependency_tokens(chunk: RetrievedChunk) -> set[str]:
    """Extract dependency tokens from chunk metadata if present."""
    raw_value = chunk.metadata.get("dependencies")
    if isinstance(raw_value, str):
        return _tokenize_text(raw_value)

    if isinstance(raw_value, (list, tuple, set)):
        tokens: set[str] = set()
        for item in raw_value:
            if isinstance(item, str):
                tokens.update(_tokenize_text(item))
        return tokens

    return set()


def _division_hint_matches(query_tokens: set[str], division: str) -> bool:
    """Return whether query hints align with a chunk division."""
    normalized_division = division.strip().upper()
    if not normalized_division:
        return False

    if normalized_division.lower() in query_tokens:
        return True

    hint_tokens = DIVISION_HINTS.get(normalized_division, set())
    return bool(hint_tokens.intersection(query_tokens))


def _metadata_boost_for_chunk(
    query_tokens: set[str],
    chunk: RetrievedChunk,
    feature: str,
) -> float:
    """Compute bounded metadata boost for a chunk."""
    boost = 0.0

    paragraph_name = _metadata_value(chunk, "paragraph_name", chunk.name)
    paragraph_tokens = _tokenize_text(paragraph_name)
    if paragraph_tokens and paragraph_tokens.issubset(query_tokens):
        boost += PARAGRAPH_NAME_BOOST

    division = _metadata_value(chunk, "division", "")
    if _division_hint_matches(query_tokens, division):
        boost += DIVISION_BOOST

    if _tokenize_text(chunk.file_path).intersection(query_tokens):
        boost += FILE_PATH_OVERLAP_BOOST

    dependency_overlap = bool(_dependency_tokens(chunk).intersection(query_tokens))
    if dependency_overlap:
        boost += DEPENDENCY_OVERLAP_BOOST
        if feature == "dependency_mapping":
            boost += FEATURE_DEPENDENCY_BOOST

    if chunk.codebase.lower() in query_tokens:
        boost += CODEBASE_BOOST
    if chunk.language.lower() in query_tokens:
        boost += LANGUAGE_BOOST

    return min(boost, MAX_METADATA_BOOST)


def _apply_metadata_rerank(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str,
) -> list[RetrievedChunk]:
    """Apply deterministic metadata boosts on top of incoming scores."""
    query_tokens = _tokenize_query(query)

    return [
        replace(
            chunk,
            score=float(chunk.score) + _metadata_boost_for_chunk(query_tokens, chunk, feature),
        )
        for chunk in chunks
    ]


def _normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Normalize scores into [0.0, 1.0] for stable confidence thresholds."""
    if not chunks:
        return []

    scores = [float(chunk.score) for chunk in chunks]
    minimum_score = min(scores)
    maximum_score = max(scores)

    if maximum_score == minimum_score:
        return [
            replace(chunk, score=EQUAL_SCORE_NORMALIZED_VALUE)
            for chunk in chunks
        ]

    score_span = maximum_score - minimum_score
    return [
        replace(chunk, score=(float(chunk.score) - minimum_score) / score_span)
        for chunk in chunks
    ]


def _cohere_enabled() -> bool:
    """Return whether Cohere reranking is available by configuration."""
    return bool(COHERE_API_KEY.strip())


def _import_cohere_module() -> ModuleType:
    """Import Cohere lazily to keep runtime/test coupling minimal."""
    try:
        return importlib.import_module("cohere")
    except ModuleNotFoundError as exc:
        raise CohereRerankError(
            "cohere is not installed. Install dependencies before reranking."
        ) from exc


def _build_cohere_client() -> _CohereClientProtocol:
    """Build Cohere client from configured API key."""
    if not COHERE_API_KEY:
        raise CohereRerankError(
            "COHERE_API_KEY is missing. Falling back to metadata-only reranking."
        )

    cohere_module = _import_cohere_module()
    client_v2 = getattr(cohere_module, "ClientV2", None)
    if callable(client_v2):
        return client_v2(api_key=COHERE_API_KEY)

    client = getattr(cohere_module, "Client", None)
    if callable(client):
        return client(api_key=COHERE_API_KEY)

    raise CohereRerankError("Cohere client class is unavailable in installed SDK.")


def _extract_cohere_scores(
    response: object,
    expected_documents: int,
) -> dict[int, float]:
    """Extract index->relevance score map from Cohere rerank response."""
    if isinstance(response, dict):
        raw_results = response.get("results")
    else:
        raw_results = getattr(response, "results", None)

    if not isinstance(raw_results, list):
        raise CohereRerankError("Cohere response did not include a valid results list.")

    scores: dict[int, float] = {}
    for raw_result in raw_results:
        if isinstance(raw_result, dict):
            raw_index = raw_result.get("index")
            raw_score = raw_result.get("relevance_score")
        else:
            raw_index = getattr(raw_result, "index", None)
            raw_score = getattr(raw_result, "relevance_score", None)

        if not isinstance(raw_index, int):
            continue
        if raw_index < 0 or raw_index >= expected_documents:
            continue
        if not isinstance(raw_score, (int, float)):
            continue

        scores[raw_index] = float(raw_score)

    if not scores:
        raise CohereRerankError("Cohere response did not contain valid ranked scores.")

    return scores


def _apply_cohere_rerank(
    query: str,
    chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Apply Cohere cross-encoder rerank and blend with metadata-normalized scores."""
    if not chunks:
        return []

    client = _build_cohere_client()
    documents = [chunk.content for chunk in chunks]

    try:
        response = client.rerank(
            model=COHERE_RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=len(documents),
        )
    except Exception as exc:
        raise CohereRerankError("Cohere rerank request failed.") from exc

    cohere_scores = _extract_cohere_scores(response, expected_documents=len(chunks))
    blended_chunks: list[RetrievedChunk] = []

    for index, chunk in enumerate(chunks):
        cohere_score = cohere_scores.get(index, 0.0)
        blended_score = (
            (METADATA_BLEND_WEIGHT * float(chunk.score))
            + (COHERE_BLEND_WEIGHT * cohere_score)
        )
        blended_chunks.append(replace(chunk, score=blended_score))

    return blended_chunks


def _confidence_from_score(score: float) -> Confidence:
    """Map normalized score to discrete confidence level."""
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return Confidence.HIGH
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return Confidence.MEDIUM
    return Confidence.LOW


def _assign_confidence(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Attach confidence labels using normalized score thresholds."""
    return [
        replace(chunk, confidence=_confidence_from_score(float(chunk.score)))
        for chunk in chunks
    ]


def _sort_chunks_deterministically(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Sort by score desc, then deterministic metadata tie-breakers."""
    return sorted(
        chunks,
        key=lambda chunk: (
            -float(chunk.score),
            chunk.file_path,
            chunk.line_start,
            chunk.line_end,
            chunk.name,
        ),
    )


def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    enable_cohere: bool = True,
) -> list[RetrievedChunk]:
    """Rerank retrieved chunks using metadata signals and optional Cohere stage."""
    _validate_inputs(query=query, chunks=chunks)
    if not chunks:
        return []

    metadata_scored = _apply_metadata_rerank(query=query, chunks=chunks, feature=feature)
    metadata_normalized = _normalize_scores(metadata_scored)

    reranked_chunks = metadata_normalized
    if enable_cohere and _cohere_enabled():
        try:
            reranked_chunks = _apply_cohere_rerank(query=query, chunks=metadata_normalized)
            reranked_chunks = _normalize_scores(reranked_chunks)
        except CohereRerankError as exc:
            LOGGER.warning(
                "Cohere rerank unavailable, using metadata-only ranking: %s",
                exc,
            )
    elif enable_cohere and not _cohere_enabled():
        LOGGER.info("COHERE_API_KEY missing; using metadata-only reranking.")

    with_confidence = _assign_confidence(reranked_chunks)
    return _sort_chunks_deterministically(with_confidence)
