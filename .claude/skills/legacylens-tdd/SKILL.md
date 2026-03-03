---
name: legacylens-tdd
description: Test-driven development workflow for LegacyLens RAG pipeline modules. Use when implementing any new module, feature, or endpoint in LegacyLens. Triggers on tasks involving src/ or tests/ directories, or when creating new functionality.
---

# LegacyLens TDD Workflow

## Cycle

For every module or feature:

1. Write the test file first (`tests/test_<module>.py`)
2. Run the test — confirm it **fails** with the expected assertion
3. Implement the minimum code in `src/` to make it pass
4. Refactor only after tests are green
5. Run `python -m pytest tests/ -v` to verify no regressions

Never skip step 2. A test that passes before implementation is a bad test.

## Test File Mapping

| Source Module | Test File |
|---------------|-----------|
| `src/ingestion/detector.py` | `tests/test_detector.py` |
| `src/ingestion/cobol_parser.py` | `tests/test_cobol_parser.py` |
| `src/ingestion/fortran_parser.py` | `tests/test_fortran_parser.py` |
| `src/ingestion/cobol_chunker.py` | `tests/test_cobol_chunker.py` |
| `src/ingestion/fortran_chunker.py` | `tests/test_fortran_chunker.py` |
| `src/ingestion/embedder.py` | `tests/test_embedder.py` |
| `src/retrieval/search.py` | `tests/test_retrieval.py` |
| `src/generation/llm.py` | `tests/test_generation.py` |
| `src/features/router.py` | `tests/test_features.py` |
| `src/api/app.py` | `tests/test_api.py` |
| `src/cli/main.py` | `tests/test_cli.py` |

## Assertion Patterns by Module Type

### Preprocessors (cobol_parser, fortran_parser)

```python
def test_cobol_column_stripping():
    raw = "000100 IDENTIFICATION DIVISION.                                        PROG01"
    result = preprocess_cobol(raw)
    assert "000100" not in result.code  # cols 1-6 stripped
    assert "PROG01" not in result.code  # cols 73-80 stripped
    assert "IDENTIFICATION DIVISION" in result.code

def test_cobol_comment_detection():
    raw = "000100*THIS IS A COMMENT"
    result = preprocess_cobol(raw)
    assert "THIS IS A COMMENT" in result.comments
```

### Chunkers (cobol_chunker, fortran_chunker)

```python
def test_chunk_respects_paragraph_boundaries():
    chunks = chunk_cobol(processed_file)
    for chunk in chunks:
        assert 64 <= chunk.token_count <= 768
        assert chunk.name != ""  # every chunk has a name
        assert chunk.line_start < chunk.line_end

def test_small_paragraphs_merged():
    # Two 20-token paragraphs should merge into one chunk
    chunks = chunk_cobol(file_with_small_paragraphs)
    assert len(chunks) < num_paragraphs
```

### Retrieval (search, reranker)

```python
def test_relevant_chunk_in_top5():
    results = hybrid_search("What does CALCULATE-INTEREST do?", top_k=5)
    chunk_names = [r.name for r in results]
    assert "CALCULATE-INTEREST" in chunk_names

def test_codebase_filter():
    results = hybrid_search("main entry", codebase="gnucobol")
    assert all(r.codebase == "gnucobol" for r in results)
```

### Features

```python
def test_feature_returns_citations():
    response = explain_code("What does PROCESS-RECORD do?")
    assert len(response.citations) > 0
    assert all(":" in c for c in response.citations)  # file:line format
```

### API Endpoints

```python
@pytest.mark.asyncio
async def test_query_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/query", json={"query": "test", "feature": "code_explanation"})
        assert resp.status_code == 200
        assert "answer" in resp.json()

async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
```

## Test Fixtures

Use `conftest.py` for shared fixtures:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_cobol_source() -> str:
    """Minimal valid COBOL with known paragraph boundaries."""
    return """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. TEST-PROG.
000300 PROCEDURE DIVISION.
000400 MAIN-LOGIC.
000500     DISPLAY "HELLO".
000600     STOP RUN.
"""

@pytest.fixture
def sample_fortran_source() -> str:
    """Minimal valid Fortran with known subroutine boundaries."""
    return """      SUBROUTINE COMPUTE(X, Y, RESULT)
      REAL X, Y, RESULT
      RESULT = X + Y
      RETURN
      END
"""
```

## Evaluation Tests

```python
def test_precision_at_5():
    """Run against ground truth dataset."""
    results = evaluate("evaluation/ground_truth.json")
    assert results["precision_at_5"] >= 0.85
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Single module
python -m pytest tests/test_cobol_parser.py -v

# With coverage
python -m pytest tests/ -v --tb=short
```
