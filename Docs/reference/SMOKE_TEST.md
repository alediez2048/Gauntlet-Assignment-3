# MVP-016 Smoke Test Checklist

End-to-end validation of the deployed LegacyLens RAG pipeline. Run 10 manual queries against the live Render API.

## Prerequisites

- Deployed API at `https://gauntlet-assignment-3.onrender.com` (or set `API_URL` below)
- GnuCOBOL codebase ingested in Qdrant
- Cold start: first request may take 10–30s; retry once before failing

## Setup

```bash
export API_URL="${LEGACYLENS_API_URL:-https://gauntlet-assignment-3.onrender.com}"
```

## Pre-flight Checks

```bash
# Health — must return 200 and {"status":"ok"}
curl -s "$API_URL/api/health"

# Codebases — must return 200 and {"codebases":[...]}
curl -s "$API_URL/api/codebases"
```

## 10 Smoke Test Queries

All queries use `codebase: "gnucobol"`. Cover at least 3–4 distinct features.

| # | Feature | Query | Pass? | Notes |
|---|---------|-------|-------|-------|
| 1 | code_explanation | What does MAIN-LOGIC do? | | |
| 2 | code_explanation | Explain the INIT-DATA paragraph | | |
| 3 | code_explanation | What does CALCULATE-INTEREST do? | | |
| 4 | dependency_mapping | What PARAGRAPHS does MAIN-LOGIC call? | | |
| 5 | dependency_mapping | Trace PERFORM calls from MAIN-LOGIC | | |
| 6 | pattern_detection | Find similar code patterns to MAIN-LOGIC | | |
| 7 | documentation_gen | Generate documentation for MAIN-LOGIC | | |
| 8 | translation_hints | How would MAIN-LOGIC look in Python? | | |
| 9 | bug_pattern_search | Find potential bug patterns in gnucobol | | |
| 10 | business_logic | Extract business rules from gnucobol | | |

## curl Commands (Copy-Paste)

```bash
# 1. code_explanation
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What does MAIN-LOGIC do?","feature":"code_explanation","codebase":"gnucobol"}'

# 2. code_explanation
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain the INIT-DATA paragraph","feature":"code_explanation","codebase":"gnucobol"}'

# 3. code_explanation
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What does CALCULATE-INTEREST do?","feature":"code_explanation","codebase":"gnucobol"}'

# 4. dependency_mapping
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What PARAGRAPHS does MAIN-LOGIC call?","feature":"dependency_mapping","codebase":"gnucobol"}'

# 5. dependency_mapping
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Trace PERFORM calls from MAIN-LOGIC","feature":"dependency_mapping","codebase":"gnucobol"}'

# 6. pattern_detection
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Find similar code patterns to MAIN-LOGIC","feature":"pattern_detection","codebase":"gnucobol"}'

# 7. documentation_gen
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Generate documentation for MAIN-LOGIC","feature":"documentation_gen","codebase":"gnucobol"}'

# 8. translation_hints
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"How would MAIN-LOGIC look in Python?","feature":"translation_hints","codebase":"gnucobol"}'

# 9. bug_pattern_search
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Find potential bug patterns in gnucobol","feature":"bug_pattern_search","codebase":"gnucobol"}'

# 10. business_logic
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Extract business rules from gnucobol","feature":"business_logic","codebase":"gnucobol"}'
```

## CLI Alternative

```bash
export LEGACYLENS_API_URL="$API_URL"

python -m src.cli.main query "What does MAIN-LOGIC do?" --codebase gnucobol --feature code_explanation
# ... repeat for each query
```

## Expected Behavior

- **HTTP 200** (or CLI exit 0)
- **Cited answer:** response includes `answer` with file:line references
- **No 500** attributable to retrieval, reranking, or generation

## Success Criteria (MVP-016)

- At least **8 of 10** queries return 200 with cited answers
- Allow 2 failures for feature-specific or data gaps (e.g., paragraph not in GnuCOBOL)
- Blocking bugs fixed and re-tested before marking complete

## Troubleshooting

### "retrieval failed: Failed to embed query"

- **Cause:** Voyage AI embedding API not reachable or `VOYAGE_API_KEY` missing/invalid.
- **Fix:** Verify `VOYAGE_API_KEY` in `.env` (local) or Render dashboard (production). See `Docs/reference/ENVIRONMENT.md` for verification commands.

### Run Script (Optional)

```bash
API_URL="https://gauntlet-assignment-3.onrender.com" python evaluation/run_smoke_test.py
```
