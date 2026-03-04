"""Hybrid retrieval search for LegacyLens (MVP-009)."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.models import Document, FieldCondition, Filter, MatchValue

from src.config import (
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
    VOYAGE_API_KEY,
)
from src.types.responses import Confidence, RetrievedChunk

IDENTIFIER_TOKEN_PATTERN = re.compile(r"\b[A-Z0-9_-]{4,}\b")
NON_IDENTIFIER_CHARS = re.compile(r"[^A-Za-z0-9_-]")

IDENTIFIER_QUERY_DENSE_WEIGHT = 0.4
IDENTIFIER_QUERY_SPARSE_WEIGHT = 0.6
SEMANTIC_QUERY_DENSE_WEIGHT = 0.7
SEMANTIC_QUERY_SPARSE_WEIGHT = 0.3

HIGH_CONFIDENCE_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_THRESHOLD = 0.45

SPARSE_BM25_MODEL = "Qdrant/bm25"


class SearchValidationError(ValueError):
    """Raised when hybrid search arguments are invalid."""


class SearchConfigError(RuntimeError):
    """Raised when hybrid search configuration is missing or invalid."""


class SearchEmbeddingError(RuntimeError):
    """Raised when query embedding fails."""


class SearchBackendError(RuntimeError):
    """Raised when Qdrant retrieval operations fail."""


class _VoyageClientProtocol(Protocol):
    """Subset of voyageai client used by this module."""

    def embed(self, *, texts: list[str], model: str, input_type: str) -> object:
        """Return embedding response object containing `.embeddings`."""


@dataclass
class _FusedPoint:
    """Internal fused point representation used before output mapping."""

    point_id: str
    payload: dict[str, object]
    fused_score: float
    dense_score: float
    sparse_score: float


def _validate_query_inputs(query: str, top_k: int) -> None:
    """Validate hybrid search arguments with deterministic messages."""
    if not query.strip():
        raise SearchValidationError("query must not be blank")
    if top_k <= 0:
        raise SearchValidationError("top_k must be greater than 0")


def _build_qdrant_client() -> QdrantClient:
    """Build Qdrant client from configured URL and API key."""
    if not QDRANT_URL:
        raise SearchConfigError(
            "QDRANT_URL is missing. Set it in your environment or .env file."
        )

    try:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    except (TypeError, ValueError) as exc:
        raise SearchConfigError(
            "Failed to create Qdrant client. Verify QDRANT_URL and QDRANT_API_KEY."
        ) from exc


def _import_voyageai_module() -> ModuleType:
    """Import voyageai lazily to keep test environments lightweight."""
    try:
        return importlib.import_module("voyageai")
    except ModuleNotFoundError as exc:
        raise SearchConfigError(
            "voyageai is not installed. Install dependencies before retrieval."
        ) from exc


def _build_voyage_client() -> _VoyageClientProtocol:
    """Build voyage query-embedding client from configured API key."""
    if not VOYAGE_API_KEY:
        raise SearchConfigError(
            "VOYAGE_API_KEY is missing. Set it in your environment or .env file."
        )

    voyageai_module = _import_voyageai_module()
    return voyageai_module.Client(api_key=VOYAGE_API_KEY)


def _extract_embeddings(response: object) -> list[list[float]]:
    """Extract embeddings from voyage response object."""
    embeddings_value: object | None

    if isinstance(response, dict):
        embeddings_value = response.get("embeddings")
    else:
        embeddings_value = getattr(response, "embeddings", None)

    if not isinstance(embeddings_value, list):
        raise SearchEmbeddingError("Query embedding response did not include embeddings.")

    vectors: list[list[float]] = []
    for vector in embeddings_value:
        if not isinstance(vector, list):
            raise SearchEmbeddingError("Query embedding vector had unexpected format.")
        vectors.append([float(value) for value in vector])

    return vectors


def _embed_query(client: _VoyageClientProtocol, query: str) -> list[float]:
    """Embed query text using voyage with retrieval query input type."""
    try:
        response = client.embed(texts=[query], model=EMBEDDING_MODEL, input_type="query")
    except Exception as exc:
        raise SearchEmbeddingError("Failed to embed query.") from exc

    vectors = _extract_embeddings(response)
    if not vectors:
        raise SearchEmbeddingError("Failed to embed query: no vectors returned.")

    return vectors[0]


def _build_query_filter(codebase: str | None) -> Filter | None:
    """Build optional codebase payload filter."""
    if codebase is None:
        return None

    return Filter(
        must=[FieldCondition(key="codebase", match=MatchValue(value=codebase))]
    )


def _is_identifier_query(query: str) -> bool:
    """Classify identifier-heavy queries to favor sparse/BM25 channel."""
    if IDENTIFIER_TOKEN_PATTERN.search(query):
        return True

    tokens = [token for token in query.split() if token]
    if not tokens:
        return False

    if any("-" in token or "_" in token for token in tokens):
        return True

    identifier_like_count = 0
    for token in tokens:
        normalized_token = NON_IDENTIFIER_CHARS.sub("", token)
        if not normalized_token:
            continue
        if normalized_token.upper() == normalized_token and len(normalized_token) >= 3:
            identifier_like_count += 1

    return identifier_like_count >= max(1, len(tokens) // 2) and len(tokens) <= 6


def _select_channel_weights(query: str) -> tuple[float, float]:
    """Select deterministic dense/sparse fusion weights from query type."""
    if _is_identifier_query(query):
        return (IDENTIFIER_QUERY_DENSE_WEIGHT, IDENTIFIER_QUERY_SPARSE_WEIGHT)
    return (SEMANTIC_QUERY_DENSE_WEIGHT, SEMANTIC_QUERY_SPARSE_WEIGHT)


def _channel_limit(top_k: int) -> int:
    """Fetch extra points per channel to improve post-fusion quality."""
    return max(top_k * 2, top_k)


def _extract_points(response: object) -> list[object]:
    """Extract scored points list from Qdrant query response shape."""
    points_value: object | None

    if isinstance(response, dict):
        points_value = response.get("points")
    else:
        points_value = getattr(response, "points", None)

    if not isinstance(points_value, list):
        return []
    return points_value


def _search_dense(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    query_filter: Filter | None,
    limit: int,
) -> list[object]:
    """Run dense vector retrieval channel in Qdrant."""
    try:
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        raise SearchBackendError("Dense retrieval failed.") from exc

    return _extract_points(response)


def _search_sparse_bm25(
    client: QdrantClient,
    collection_name: str,
    query_text: str,
    query_filter: Filter | None,
    limit: int,
) -> list[object]:
    """Run sparse/BM25 retrieval channel in Qdrant.

    Returns empty list if sparse/BM25 is not configured (e.g. collection has only
    dense vectors). This allows dense-only retrieval to work when sparse vectors
    were not indexed.
    """
    sparse_query = Document(text=query_text, model=SPARSE_BM25_MODEL)

    try:
        response = client.query_points(
            collection_name=collection_name,
            query=sparse_query,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return _extract_points(response)
    except Exception:
        try:
            fallback_response = client.query_points(
                collection_name=collection_name,
                query=query_text,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return _extract_points(fallback_response)
        except Exception:
            # Sparse/BM25 not configured (e.g. collection has only dense vectors).
            # Return empty so hybrid_search continues with dense-only results.
            return []


def _point_id(point: object) -> str:
    """Extract deterministic string point ID from scored point object."""
    raw_id: object
    if isinstance(point, dict):
        raw_id = point.get("id")
    else:
        raw_id = getattr(point, "id", "")
    return str(raw_id)


def _point_score(point: object) -> float:
    """Extract score from scored point object with float fallback."""
    raw_score: object
    if isinstance(point, dict):
        raw_score = point.get("score")
    else:
        raw_score = getattr(point, "score", 0.0)

    if isinstance(raw_score, (int, float)):
        return float(raw_score)
    return 0.0


def _point_payload(point: object) -> dict[str, object]:
    """Extract payload dict from scored point object with safe fallback."""
    raw_payload: object
    if isinstance(point, dict):
        raw_payload = point.get("payload")
    else:
        raw_payload = getattr(point, "payload", {})

    if isinstance(raw_payload, dict):
        return raw_payload
    return {}


def _normalize_score_map(score_map: dict[str, float]) -> dict[str, float]:
    """Normalize score map to [0.0, 1.0] with deterministic equal-score fallback."""
    if not score_map:
        return {}

    values = list(score_map.values())
    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return {point_id: 1.0 for point_id in score_map}

    span = maximum - minimum
    return {
        point_id: (score - minimum) / span
        for point_id, score in score_map.items()
    }


def _fuse_channel_results(
    dense_hits: list[object],
    sparse_hits: list[object],
    dense_weight: float,
    sparse_weight: float,
    top_k: int,
) -> list[_FusedPoint]:
    """Fuse dense and sparse channels deterministically using weighted normalization."""
    dense_scores: dict[str, float] = {}
    dense_payloads: dict[str, dict[str, object]] = {}
    for point in dense_hits:
        point_id = _point_id(point)
        point_score = _point_score(point)
        current = dense_scores.get(point_id)
        if current is None or point_score > current:
            dense_scores[point_id] = point_score
            dense_payloads[point_id] = _point_payload(point)

    sparse_scores: dict[str, float] = {}
    sparse_payloads: dict[str, dict[str, object]] = {}
    for point in sparse_hits:
        point_id = _point_id(point)
        point_score = _point_score(point)
        current = sparse_scores.get(point_id)
        if current is None or point_score > current:
            sparse_scores[point_id] = point_score
            sparse_payloads[point_id] = _point_payload(point)

    dense_normalized = _normalize_score_map(dense_scores)
    sparse_normalized = _normalize_score_map(sparse_scores)

    fused: list[_FusedPoint] = []
    all_ids = sorted(set(dense_scores.keys()) | set(sparse_scores.keys()))
    for point_id in all_ids:
        dense_score = dense_scores.get(point_id, 0.0)
        sparse_score = sparse_scores.get(point_id, 0.0)
        fused_score = (
            (dense_normalized.get(point_id, 0.0) * dense_weight)
            + (sparse_normalized.get(point_id, 0.0) * sparse_weight)
        )
        payload = dense_payloads.get(point_id) or sparse_payloads.get(point_id, {})
        fused.append(
            _FusedPoint(
                point_id=point_id,
                payload=payload,
                fused_score=fused_score,
                dense_score=dense_score,
                sparse_score=sparse_score,
            )
        )

    fused.sort(
        key=lambda point: (
            -point.fused_score,
            -point.dense_score,
            -point.sparse_score,
            point.point_id,
        )
    )
    return fused[:top_k]


def _to_int(value: object, fallback: int) -> int:
    """Convert payload value to int with deterministic fallback."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return fallback
    return fallback


def _metadata_to_str_map(payload: dict[str, object]) -> dict[str, str]:
    """Convert payload metadata values to string map for RetrievedChunk contract."""
    metadata: dict[str, str] = {}
    for key, value in payload.items():
        if key == "content":
            continue
        if isinstance(value, str):
            metadata[key] = value
        elif isinstance(value, (int, float, bool)):
            metadata[key] = str(value)
        elif isinstance(value, list):
            metadata[key] = ",".join(str(item) for item in value)
    return metadata


def _confidence_from_score(score: float) -> Confidence:
    """Map fused score to confidence labels."""
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return Confidence.HIGH
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return Confidence.MEDIUM
    return Confidence.LOW


def _to_retrieved_chunk(point: _FusedPoint) -> RetrievedChunk:
    """Map fused point payload into RetrievedChunk output contract."""
    payload = point.payload

    line_start = _to_int(payload.get("line_start"), 0)
    line_end = _to_int(payload.get("line_end"), line_start)
    if line_end < line_start:
        line_end = line_start

    paragraph_name = payload.get("paragraph_name")
    name_value = paragraph_name if isinstance(paragraph_name, str) else ""
    if not name_value:
        raw_name = payload.get("name")
        if isinstance(raw_name, str):
            name_value = raw_name

    raw_content = payload.get("content")
    raw_file_path = payload.get("file_path")
    raw_language = payload.get("language")
    raw_codebase = payload.get("codebase")

    return RetrievedChunk(
        content=raw_content if isinstance(raw_content, str) else "",
        file_path=raw_file_path if isinstance(raw_file_path, str) else "",
        line_start=line_start,
        line_end=line_end,
        name=name_value,
        language=raw_language if isinstance(raw_language, str) else "",
        codebase=raw_codebase if isinstance(raw_codebase, str) else "",
        score=float(point.fused_score),
        confidence=_confidence_from_score(float(point.fused_score)),
        metadata=_metadata_to_str_map(payload),
    )


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    codebase: str | None = None,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> list[RetrievedChunk]:
    """Run Qdrant-native dense + sparse retrieval and return fused RetrievedChunk values."""
    _validate_query_inputs(query=query, top_k=top_k)

    qdrant_client = _build_qdrant_client()
    voyage_client = _build_voyage_client()

    query_vector = _embed_query(voyage_client, query)
    query_filter = _build_query_filter(codebase=codebase)

    channel_limit = _channel_limit(top_k)
    dense_hits = _search_dense(
        client=qdrant_client,
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=channel_limit,
    )
    sparse_hits = _search_sparse_bm25(
        client=qdrant_client,
        collection_name=collection_name,
        query_text=query,
        query_filter=query_filter,
        limit=channel_limit,
    )

    if not dense_hits and not sparse_hits:
        return []

    dense_weight, sparse_weight = _select_channel_weights(query)
    fused_points = _fuse_channel_results(
        dense_hits=dense_hits,
        sparse_hits=sparse_hits,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        top_k=top_k,
    )

    return [_to_retrieved_chunk(point) for point in fused_points]
