"""FastAPI route handlers for LegacyLens query orchestration."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.schemas import QueryRequest, QueryResponseSchema
from src.generation.llm import (
    GenerationConfigError,
    GenerationError,
    GenerationValidationError,
    generate_answer,
    stream_answer,
)
from src.retrieval.reranker import (
    CohereRerankError,
    RerankerValidationError,
    rerank_chunks,
)
from src.retrieval.search import (
    SearchBackendError,
    SearchConfigError,
    SearchEmbeddingError,
    SearchValidationError,
    hybrid_search,
)
from src.types.responses import QueryResponse, RetrievedChunk

router = APIRouter(prefix="/api")


def _run_retrieval(request: QueryRequest) -> list[RetrievedChunk]:
    """Run retrieval stage with stage-specific error mapping."""
    try:
        return hybrid_search(
            query=request.query,
            top_k=request.top_k,
            codebase=request.codebase,
        )
    except SearchValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"retrieval validation failed: {exc}",
        ) from exc
    except (SearchConfigError, SearchEmbeddingError, SearchBackendError) as exc:
        raise HTTPException(status_code=500, detail=f"retrieval failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="retrieval failed: internal error") from exc


def _run_rerank(
    *,
    request: QueryRequest,
    chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Run reranking stage with stage-specific error mapping."""
    try:
        return rerank_chunks(
            query=request.query,
            chunks=chunks,
            feature=request.feature,
        )
    except RerankerValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"reranking validation failed: {exc}",
        ) from exc
    except CohereRerankError as exc:
        raise HTTPException(status_code=500, detail=f"reranking failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="reranking failed: internal error") from exc


def _run_generation(
    *,
    request: QueryRequest,
    chunks: list[RetrievedChunk],
) -> QueryResponse:
    """Run generation stage with stage-specific error mapping."""
    try:
        return generate_answer(
            query=request.query,
            chunks=chunks,
            feature=request.feature,
            language=request.language,
            model=request.model,
        )
    except GenerationValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"generation validation failed: {exc}",
        ) from exc
    except (GenerationConfigError, GenerationError) as exc:
        raise HTTPException(status_code=500, detail=f"generation failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="generation failed: internal error") from exc


@router.post("/query", response_model=QueryResponseSchema)
async def query_route(request: QueryRequest) -> QueryResponseSchema:
    """Run retrieval -> rerank -> generation and return QueryResponse contract."""
    retrieved_chunks = _run_retrieval(request)
    reranked_chunks = _run_rerank(request=request, chunks=retrieved_chunks)
    response = _run_generation(request=request, chunks=reranked_chunks)
    return QueryResponseSchema.from_query_response(
        response,
        request_codebase=request.codebase,
    )


@router.post("/stream")
async def stream_route(request: QueryRequest) -> StreamingResponse:
    """Run retrieval -> rerank and stream generation output."""
    retrieved_chunks = _run_retrieval(request)
    reranked_chunks = _run_rerank(request=request, chunks=retrieved_chunks)

    def _stream_iterator() -> Iterator[str]:
        try:
            yield from stream_answer(
                query=request.query,
                chunks=reranked_chunks,
                feature=request.feature,
                language=request.language,
                model=request.model,
            )
        except GenerationValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"generation validation failed: {exc}",
            ) from exc
        except (GenerationConfigError, GenerationError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"generation failed: {exc}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="generation failed: internal error",
            ) from exc

    return StreamingResponse(_stream_iterator(), media_type="text/plain")
