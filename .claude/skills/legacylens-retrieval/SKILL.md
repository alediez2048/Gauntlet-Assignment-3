---
name: legacylens-retrieval
description: Hybrid search, layered re-ranking, and dynamic context assembly for the LegacyLens RAG pipeline. Use when implementing or modifying src/retrieval/ modules (search.py, reranker.py, context.py), or when working on query processing, search quality, re-ranking strategies, or context window management.
---

# LegacyLens Retrieval Pipeline

## Pipeline Flow

```
Query → Classification → Embedding → Hybrid Search → Re-ranking (3 layers) → Context Assembly → Feature Router
```

All retrieval logic lives in `src/retrieval/`.

## Query Classification

Classify each query before search to tune retrieval weights:

| Type | Signal | Search Weight |
|------|--------|---------------|
| Identifier query | Contains UPPER-CASE-NAMES, specific paragraph/subroutine names | Boost BM25 (keyword match matters more) |
| Semantic query | Natural language question, no specific identifiers | Boost dense (meaning matters more) |

## Query Embedding

Use Voyage Code 2 with `input_type="query"` (different from ingestion which uses `"document"`):

```python
result = voyage_client.embed(texts=[query], model="voyage-code-2", input_type="query")
```

## Hybrid Search (`search.py`)

Use Qdrant's native hybrid search combining dense vectors and BM25 sparse:

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = client.query_points(
    collection_name="legacylens",
    query=query_embedding,
    limit=top_k,
    query_filter=Filter(
        must=[FieldCondition(key="codebase", match=MatchValue(value=codebase))]
    ) if codebase else None,
)
```

- Default `top_k`: 10 (from `src/config.py`)
- When `codebase` is None, search across all codebases
- When specified, filter to that codebase only

## Re-ranking (3 Layers)

Execute in this exact order:

### Layer 1: Metadata Re-ranking (free, fast)

Boost scores based on metadata signals:
- Exact paragraph/subroutine name match with query terms → +0.3
- Same division as query context → +0.1
- File path relevance → +0.05

### Layer 2: Cohere Cross-Encoder

```python
import cohere

co = cohere.Client(api_key=COHERE_API_KEY)
reranked = co.rerank(
    query=query,
    documents=[chunk.content for chunk in candidates],
    model="rerank-english-v3.0",
    top_n=top_k,
)
```

Fallback: if Cohere API fails, use metadata-only ranking from Layer 1.

### Layer 3: Diversity Re-ranking

Prevent redundancy — demote chunks from the same file/paragraph that overlap significantly. Ensure top-5 results span at least 2 different files when possible.

## Dynamic Context Assembly (`context.py`)

Total budget: **5,000 tokens** (from `src/config.py`).

Allocation strategy:
1. **Top-1 expansion** (2,000 tokens): Expand the highest-ranked chunk by including surrounding lines from the same file (before and after) to provide full context
2. **Breadth chunks** (3,000 tokens): Fill remaining budget with chunks 2–N, each truncated if needed to fit

Token counting via `tiktoken` with `cl100k_base` encoding.

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")
token_count = len(enc.encode(text))
```

## Zero-Result Degradation

When the top similarity score falls below a confidence threshold, degrade gracefully through four tiers:

1. **Normal** — scores above threshold → standard pipeline
2. **Partial match** — some results but low confidence → add caveat to response
3. **Keyword fallback** — no good vector matches → BM25-only search
4. **Suggestions** — nothing relevant → suggest related paragraph/subroutine names from the index

Never return an empty response without an explanation.

## Codebase Filtering

- Default: search all codebases (no filter)
- User can specify `codebase` param → add Qdrant `Filter` on `codebase` field
- The `/api/codebases` endpoint lists available codebases with status

## Output Type

Return `list[RetrievedChunk]` — see `src/types/responses.py`:

```python
RetrievedChunk(
    content=str,
    file_path=str,
    line_start=int,
    line_end=int,
    name=str,
    language=str,
    codebase=str,
    score=float,
    confidence=Confidence,  # HIGH | MEDIUM | LOW
)
```
