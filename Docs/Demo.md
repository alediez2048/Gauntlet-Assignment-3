# LegacyLens MVP Demo Walkthrough

> A step-by-step guide to demonstrating that LegacyLens meets all 9 MVP hard gate requirements.

**Deployed API URL:** `https://legacylens-api.onrender.com` (replace with your actual Render URL)

---

## MVP Hard Gate Requirements

| # | Requirement | How to Verify |
|---|-------------|---------------|
| 1 | Ingest at least one legacy codebase (GnuCOBOL) | `/api/codebases` lists gnucobol |
| 2 | Chunk code files with syntax-aware splitting | Query returns chunks with paragraph names and line ranges |
| 3 | Generate embeddings for all chunks (Voyage Code 2) | Queries return semantically relevant results (not keyword-only) |
| 4 | Store embeddings in a vector database (Qdrant) | Queries succeed — Qdrant is the backend |
| 5 | Implement semantic search across the codebase (hybrid dense + BM25) | Queries return ranked, relevant chunks |
| 6 | Natural language query interface (CLI + API) | Demo both `curl` and CLI commands |
| 7 | Return relevant code snippets with file/line references | Response chunks include `file_path`, `line_start`, `line_end` |
| 8 | Basic answer generation using retrieved context (GPT-4o) | Response includes `answer` field with cited explanations |
| 9 | Deployed and publicly accessible | API reachable via public URL |

---

## Pre-Demo Checklist

Before starting the demo, confirm the stack is live:

```bash
# Set your deployed API URL
export API_URL="https://legacylens-api.onrender.com"

# 1. Health check — should return {"status": "ok"}
curl -s "$API_URL/api/health" | python3 -m json.tool

# 2. Codebases — should list gnucobol
curl -s "$API_URL/api/codebases" | python3 -m json.tool
```

**Expected output:**

```json
// /api/health
{ "status": "ok" }

// /api/codebases
{
  "codebases": [
    {
      "name": "gnucobol",
      "language": "cobol",
      "description": "Open source COBOL compiler"
    }
  ]
}
```

If the health check fails or times out, Render may be cold-starting. Wait 30 seconds and retry.

---

## Demo Step 1: Code Explanation (Requirement 8)

**What it proves:** The system retrieves relevant COBOL code and generates a natural language explanation with file:line citations.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does MAIN-LOGIC do?",
    "feature": "code_explanation",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "What does MAIN-LOGIC do?" \
  --feature code_explanation \
  --codebase gnucobol
```

### What to look for in the response

- `answer` — A plain English explanation of the MAIN-LOGIC paragraph
- `chunks` — Each chunk has `file_path`, `line_start`, `line_end`, `name`, `content`
- `confidence` — One of `HIGH`, `MEDIUM`, or `LOW`
- `model` — Should show `gpt-4o` (or `gpt-4o-mini` if fallback triggered)
- `latency_ms` — Total pipeline time

### Example response structure

```json
{
  "answer": "MAIN-LOGIC is the primary control paragraph that... (see cobc/cobc.c:142-158)",
  "chunks": [
    {
      "content": "MAIN-LOGIC.\n    PERFORM INIT-DATA\n    PERFORM PROCESS-RECORDS...",
      "file_path": "cobc/cobc.cob",
      "line_start": 142,
      "line_end": 158,
      "name": "MAIN-LOGIC",
      "language": "cobol",
      "codebase": "gnucobol",
      "score": 0.92
    }
  ],
  "query": "What does MAIN-LOGIC do?",
  "feature": "code_explanation",
  "confidence": "HIGH",
  "model": "gpt-4o",
  "latency_ms": 3200.5
}
```

---

## Demo Step 2: Dependency Mapping (Requirement 5, 7)

**What it proves:** The system can trace PERFORM/CALL chains and return the relevant code with line references.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What paragraphs does MAIN-LOGIC call?",
    "feature": "dependency_mapping",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "What paragraphs does MAIN-LOGIC call?" \
  --feature dependency_mapping \
  --codebase gnucobol
```

### What to look for

- Answer describes PERFORM/CALL relationships between paragraphs
- Citations reference specific files and line numbers
- Multiple chunks returned showing the call chain

---

## Demo Step 3: Pattern Detection (Requirement 5)

**What it proves:** Semantic search finds structurally similar code across the codebase.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find similar code patterns to MAIN-LOGIC",
    "feature": "pattern_detection",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "Find similar code patterns to MAIN-LOGIC" \
  --feature pattern_detection \
  --codebase gnucobol
```

### What to look for

- Answer identifies structural similarities between paragraphs
- Multiple chunks from different files showing similar patterns

---

## Demo Step 4: Documentation Generation (Requirement 8)

**What it proves:** The LLM generates structured documentation from retrieved code context.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Generate documentation for MAIN-LOGIC",
    "feature": "documentation_gen",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "Generate documentation for MAIN-LOGIC" \
  --feature documentation_gen \
  --codebase gnucobol
```

### What to look for

- Answer formatted as documentation (purpose, inputs, outputs, dependencies)
- File:line citations backing the generated docs

---

## Demo Step 5: Translation Hints (Requirement 8)

**What it proves:** The system can suggest modern language equivalents for legacy code.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How would MAIN-LOGIC look in Python?",
    "feature": "translation_hints",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "How would MAIN-LOGIC look in Python?" \
  --feature translation_hints \
  --codebase gnucobol
```

### What to look for

- Answer includes a Python equivalent or pseudocode translation
- Original COBOL code cited for comparison

---

## Demo Step 6: Bug Pattern Search (Requirement 5, 8)

**What it proves:** The system identifies potential anti-patterns and code smells.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find potential bug patterns in gnucobol",
    "feature": "bug_pattern_search",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "Find potential bug patterns in gnucobol" \
  --feature bug_pattern_search \
  --codebase gnucobol
```

### What to look for

- Answer lists potential issues with severity context
- Specific code locations cited

---

## Demo Step 7: Business Logic Extraction (Requirement 8)

**What it proves:** The system identifies and extracts business rules from legacy code.

### Via API

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Extract business rules from gnucobol",
    "feature": "business_logic",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Via CLI

```bash
python -m src.cli.main query "Extract business rules from gnucobol" \
  --feature business_logic \
  --codebase gnucobol
```

### What to look for

- Answer describes business rules in plain English
- Rules mapped back to specific code locations

---

## Demo Step 8: Streaming Response

**What it proves:** The API supports streaming for lower perceived latency.

### Via API

```bash
curl -sS -N -X POST "$API_URL/api/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain the INIT-DATA paragraph",
    "feature": "code_explanation",
    "codebase": "gnucobol"
  }'
```

### Via CLI

```bash
python -m src.cli.main query "Explain the INIT-DATA paragraph" \
  --feature code_explanation \
  --codebase gnucobol \
  --stream
```

### What to look for

- Tokens appear incrementally (not all at once)
- Response is coherent when complete

---

## Demo Step 9: Additional Queries (Variety)

Two more queries to round out the 10-query smoke test and exercise different paragraph targets:

### Query 9 — Impact Analysis

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What breaks if CALCULATE-INTEREST changes?",
    "feature": "impact_analysis",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

### Query 10 — Second Explanation

```bash
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does CALCULATE-INTEREST do?",
    "feature": "code_explanation",
    "codebase": "gnucobol"
  }' | python3 -m json.tool
```

---

## Smoke Test Summary Table

Use this table to record results during the demo:

| # | Feature | Query | Status | Citations? | Notes |
|---|---------|-------|--------|------------|-------|
| 1 | code_explanation | What does MAIN-LOGIC do? | | | |
| 2 | dependency_mapping | What paragraphs does MAIN-LOGIC call? | | | |
| 3 | pattern_detection | Find similar code patterns to MAIN-LOGIC | | | |
| 4 | documentation_gen | Generate documentation for MAIN-LOGIC | | | |
| 5 | translation_hints | How would MAIN-LOGIC look in Python? | | | |
| 6 | bug_pattern_search | Find potential bug patterns in gnucobol | | | |
| 7 | business_logic | Extract business rules from gnucobol | | | |
| 8 | code_explanation | Explain the INIT-DATA paragraph (streamed) | | | |
| 9 | impact_analysis | What breaks if CALCULATE-INTEREST changes? | | | |
| 10 | code_explanation | What does CALCULATE-INTEREST do? | | | |

**Pass criteria:** At least 8 of 10 return HTTP 200 with cited answers.

---

## Supported Features Reference

All 8 features available via the `feature` parameter:

| Feature | Description | Example Query |
|---------|-------------|---------------|
| `code_explanation` | Plain English explanation of code | "What does X do?" |
| `dependency_mapping` | Trace PERFORM/CALL chains | "What does X call?" |
| `pattern_detection` | Find similar code structures | "Find patterns like X" |
| `impact_analysis` | What breaks if code changes | "What breaks if X changes?" |
| `documentation_gen` | Generate docs for undocumented code | "Document X" |
| `translation_hints` | Modern language equivalents | "How would X look in Python?" |
| `bug_pattern_search` | Find anti-patterns and code smells | "Find bugs in X" |
| `business_logic` | Extract business rules | "What business rules are in X?" |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Returns `{"status": "ok"}` |
| `/api/codebases` | GET | Lists indexed codebases |
| `/api/query` | POST | Full RAG pipeline, returns JSON response |
| `/api/stream` | POST | Streaming RAG pipeline, returns tokens as `text/plain` |

### Query Request Body

```json
{
  "query": "string (required)",
  "feature": "string (default: code_explanation)",
  "codebase": "string or null (optional filter)",
  "top_k": 10,
  "language": "cobol",
  "model": "string or null (optional override)"
}
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Request times out | Render cold start (free tier spins down after inactivity) | Wait 30s, retry once |
| 422 Unprocessable Entity | Invalid request body (bad feature name, blank query) | Check `feature` is one of the 8 supported values |
| 500 Internal Server Error | Pipeline failure (Qdrant unreachable, API key invalid) | Check Render env vars match Qdrant Cloud and API key dashboards |
| Empty/low-quality answer | GnuCOBOL not ingested or collection name mismatch | Verify `LEGACYLENS_COLLECTION` matches the ingested collection |
| CLI connection refused | `LEGACYLENS_API_URL` not set or pointing to localhost | Export: `export LEGACYLENS_API_URL="https://your-service.onrender.com"` |

---

## Tech Stack Summary

| Component | Technology | Role |
|-----------|------------|------|
| Embeddings | Voyage Code 2 (1536 dims) | Code-optimized vector embeddings |
| Vector DB | Qdrant Cloud | Hybrid dense + BM25 search |
| Reranker | Cohere Rerank | Layered relevance reranking |
| LLM | GPT-4o (fallback: GPT-4o-mini) | Answer generation with citations |
| API | FastAPI | Query orchestration |
| CLI | Click + Rich | Terminal interface |
| Deployment | Render (Docker) | Public hosting |
