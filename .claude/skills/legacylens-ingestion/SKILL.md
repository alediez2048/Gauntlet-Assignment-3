---
name: legacylens-ingestion
description: Legacy code ingestion pipeline for LegacyLens — COBOL and Fortran preprocessing, syntax-aware chunking, batch embedding, and Qdrant indexing. Use when implementing or modifying any module in src/ingestion/, or when working with COBOL/Fortran source processing, chunking strategies, embedding, or vector storage.
---

# LegacyLens Ingestion Pipeline

## Pipeline Stages

```
File Discovery → Language Detection → Preprocessing → Chunking → Metadata → Embedding → Qdrant Storage
```

Each stage has a dedicated module in `src/ingestion/`. Follow this order — each stage depends on the previous.

## Language Detection (`detector.py`)

Dispatch by file extension using the codebase registry in `src/config.py`:

| Extensions | Language | Preprocessor | Chunker |
|-----------|----------|--------------|---------|
| `.cob`, `.cbl`, `.cpy` | cobol | `cobol_parser` | `cobol_chunker` |
| `.f`, `.f90`, `.f77`, `.f95` | fortran | `fortran_parser` | `fortran_chunker` |

Skip unknown extensions with a logged warning. Never crash on unknown files.

## Preprocessing

COBOL and Fortran have fundamentally different source formats. Read [references/cobol-format.md](references/cobol-format.md) for COBOL column layout details and [references/fortran-format.md](references/fortran-format.md) for Fortran fixed/free form rules.

Both preprocessors must:
1. Detect encoding via `chardet` (skip file if confidence < 0.7)
2. Strip language-specific formatting
3. Separate comments from code
4. Return a `ProcessedFile` dataclass

## Chunking

COBOL: paragraph-based. Fortran: subroutine-based. Both use adaptive sizing (64–768 tokens via `tiktoken` `cl100k_base`).

Rules:
- Merge adjacent small chunks (< 64 tokens) into one
- Split oversized chunks (> 768 tokens) at sentence/statement boundaries
- Every chunk must have a `name` (paragraph or subroutine name)
- Set `chunk_type` to `"paragraph"`, `"subroutine"`, `"function"`, or `"program"`

## Metadata Extraction

Every `Chunk` dataclass must populate all fields:

```python
Chunk(
    content=str,          # cleaned source text
    file_path=str,        # relative path within codebase
    line_start=int,       # 1-indexed
    line_end=int,
    chunk_type=str,       # "paragraph" | "subroutine" | "function" | "program"
    language=str,         # "cobol" | "fortran"
    codebase=str,         # "gnucobol" | "gfortran" | "lapack" | "blas" | "opencobol-contrib"
    name=str,             # paragraph/subroutine name
    division=str,         # COBOL division or Fortran module name
    dependencies=list,    # PERFORM/CALL targets
    token_count=int,      # via tiktoken
)
```

## Batch Embedding (`embedder.py`)

- Model: Voyage Code 2 via `voyageai` SDK
- Batch size: 128 texts per API call
- Dimensions: 1536
- Retry: exponential backoff, 3 attempts on timeout
- Input: list of `Chunk` → output: list of `EmbeddedChunk`

```python
import voyageai

client = voyageai.Client(api_key=VOYAGE_API_KEY)
result = client.embed(texts=batch, model="voyage-code-2", input_type="document")
```

For queries, use `input_type="query"`.

## Qdrant Storage (`indexer.py`)

Single shared collection `"legacylens"` with payload indexes:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

client.create_collection(
    collection_name="legacylens",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

# Create payload indexes for fast filtering
for field in ["codebase", "language", "file_path", "name", "division"]:
    client.create_payload_index(
        collection_name="legacylens",
        field_name=field,
        field_schema=PayloadSchemaType.KEYWORD,
    )
```

Upsert in batches. Generate deterministic `chunk_id` from `f"{codebase}:{file_path}:{line_start}"`.
