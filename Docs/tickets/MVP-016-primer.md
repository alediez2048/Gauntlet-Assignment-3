# MVP-016 Primer: End-to-End Smoke Test

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-015 (Render deployment hardening) should be complete before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-016 is the **MVP gate ticket** — it validates that the deployed RAG pipeline works end-to-end by running 10 manual production queries against the live Render API.

By MVP-015, the stack is deployed:

- API on Render (Docker)
- Qdrant Cloud (vector store)
- GnuCOBOL ingested (MVP codebase)
- `/api/health`, `/api/codebases`, `/api/query`, `/api/stream` available

MVP-016 confirms the full path works: query → retrieval → rerank → generation → cited answer.

### Why It Matters

- **MVP hard gate:** All 9 MVP requirements must pass. This ticket is the final validation.
- **Production confidence:** Catches misconfig (Qdrant URL, API keys, collection name) before G4 phase.
- **Baseline for G4:** G4-001 (Fortran preprocessor) depends on a stable MVP. Smoke test proves MVP is done.
- **Documentation:** Recorded outcomes become the handoff for grading and demos.

---

## What Was Already Done

- Render deployment hardened (MVP-015)
- API deployed and reachable at `https://<service>.onrender.com`
- GnuCOBOL codebase ingested in Qdrant
- CLI and API both support query with `feature` and `codebase` params
- All 8 features wired in API (code_explanation, dependency_mapping, pattern_detection, etc.)

---

## MVP-016 Contract (Critical Reference)

### MVP Scope

- **Codebase:** GnuCOBOL only (MVP does not require all 5 codebases)
- **Features:** All 8 are API-valid; smoke test should exercise at least 3–4 distinct features
- **Interface:** API (`POST /api/query`) and/or CLI (`python -m src.cli.main query "..."`)

### Success Criteria

1. All 10 queries return HTTP 200 (or CLI exit 0)
2. Each response includes an `answer` with file:line citations
3. No 500 errors attributable to retrieval, reranking, or generation
4. Cold start handled (retry once if first request times out)

### MVP Hard Gate Checklist (from PRD)

- [x] Ingest at least one legacy codebase (GnuCOBOL)
- [x] Chunk code files with syntax-aware splitting
- [x] Generate embeddings (Voyage Code 2)
- [x] Store in Qdrant
- [x] Semantic search (hybrid dense + BM25)
- [x] Natural language query interface (CLI + API)
- [x] Return code snippets with file/line references
- [x] Answer generation (GPT-4o)
- [ ] **Deployed and publicly accessible** — validated by this ticket

---

## What MVP-016 Must Accomplish

### Goal

Run 10 manual production queries against the deployed API, record results, fix any blocking bugs, and document outcomes so the MVP gate is passed.

### Deliverables Checklist

#### A. Smoke Test Execution

- [ ] Run 10 queries against the deployed Render API (or CLI pointing at deployed API)
- [ ] Cover at least 3–4 different features (e.g., code_explanation, dependency_mapping, pattern_detection, documentation_gen)
- [ ] Use `codebase: "gnucobol"` for all queries (MVP scope)
- [ ] Record each query, response status, and whether citations were present

#### B. Smoke Test Script or Checklist (Optional but Recommended)

- [ ] Create `Docs/reference/SMOKE_TEST.md` or `evaluation/smoke_test_queries.json` with the 10 queries
- [ ] Include curl/CLI commands for reproducibility
- [ ] Document expected behavior (200, cited answer, no 500)

#### C. Bug Fixes (If Required)

- [ ] Fix any blocking issues found (e.g., wrong env var, missing collection, query validation)
- [ ] Re-run smoke test after fixes until all 10 pass

#### D. Ticket Logging

- [ ] Add MVP-016 implementation entry in `Docs/tickets/DEVLOG.md`
- [ ] Capture: deployed URL, 10 queries, pass/fail counts, any observed issues
- [ ] Note unresolved non-blocking issues for G4 phase

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before implementation:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-016-smoke-test`
- Never commit directly to `main`.
- Use Conventional Commits (`test:`, `feat:`, `fix:`, `docs:`).
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-016-smoke-test`

---

## Suggested 10 Smoke Test Queries

Use these or equivalent GnuCOBOL-focused queries. Replace `<API_URL>` with your Render service URL.

| # | Feature | Query | Purpose |
|---|---------|-------|---------|
| 1 | code_explanation | What does MAIN-LOGIC do? | Basic explanation |
| 2 | code_explanation | Explain the INIT-DATA paragraph | Paragraph-specific |
| 3 | code_explanation | What does CALCULATE-INTEREST do? | Business logic |
| 4 | dependency_mapping | What PARAGRAPHS does MAIN-LOGIC call? | Dependency tracing |
| 5 | dependency_mapping | Trace PERFORM calls from MAIN-LOGIC | Call chain |
| 6 | pattern_detection | Find similar code patterns to MAIN-LOGIC | Similarity search |
| 7 | documentation_gen | Generate documentation for MAIN-LOGIC | Doc generation |
| 8 | translation_hints | How would MAIN-LOGIC look in Python? | Translation |
| 9 | bug_pattern_search | Find potential bug patterns in gnucobol | Bug detection |
| 10 | business_logic | Extract business rules from gnucobol | Rule extraction |

### Verification Commands

```bash
# Set deployed API URL (or use LEGACYLENS_API_URL in .env)
export API_URL="https://<your-render-service>.onrender.com"

# Health + codebases first
curl -s "$API_URL/api/health"
curl -s "$API_URL/api/codebases"

# Example query (1)
curl -sS -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What does MAIN-LOGIC do?","feature":"code_explanation","codebase":"gnucobol"}'

# CLI alternative (if LEGACYLENS_API_URL points to deployed API)
python -m src.cli.main query "What does MAIN-LOGIC do?" --codebase gnucobol --feature code_explanation
```

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `Docs/reference/SMOKE_TEST.md` | Create smoke test checklist (optional) |
| `evaluation/smoke_test_queries.json` | Create query list for reproducibility (optional) |
| `Docs/tickets/DEVLOG.md` | Add MVP-016 completion entry |

### Files You Should NOT Modify

- Core pipeline modules unless a smoke-test bug requires a fix
- `render.yaml`, `Dockerfile` (deployment is MVP-015 scope)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `Docs/reference/ENVIRONMENT.md` | Production verification commands |
| `src/api/schemas.py` | Query request schema (feature, codebase) |
| `src/config.py` | FEATURES list, CODEBASES |
| `Docs/tickets/MVP-015-primer.md` | Deployment handoff |

---

## Edge Cases to Handle

1. **Cold start:** First request after Render spin-down may take 10–30s. Retry once before failing.
2. **Empty collection:** If GnuCOBOL was never ingested, queries return empty or low-quality results. Verify ingestion first.
3. **Feature-specific failures:** Some features may have different code paths; document which pass/fail.
4. **Rate limits:** OpenAI/Cohere/Voyage may rate-limit. Space queries or wait between runs.
5. **Paragraph names:** GnuCOBOL paragraph names vary; use generic queries if specific names fail.

---

## Definition of Done for MVP-016

- [ ] 10 manual queries executed against deployed API
- [ ] At least 8 of 10 return 200 with cited answers (allow 2 for feature-specific or data gaps)
- [ ] Blocking bugs fixed and re-tested
- [ ] DEVLOG updated with MVP-016 implementation entry
- [ ] Feature branch pushed and PR opened for review

---

## Estimated Time: 45–90 minutes

| Task | Estimate |
|------|----------|
| Warm up API, run 10 queries | 20–35 min |
| Record results, document | 10–15 min |
| Bug fixes (if any) | 10–25 min |
| DEVLOG and optional smoke test doc | 5–15 min |

---

## After MVP-016: What Comes Next

- **MVP complete:** Tag `mvp-complete` and proceed to G4 phase.
- **G4-001:** Fortran preprocessor (fixed/free form detection).
- **G4-006:** Ingest OpenCOBOL Contrib (second COBOL codebase).

MVP-016 is the gate. Once it passes, the MVP hard gate is satisfied and G4 work can begin.
