# MVP-015 Primer: Render Deployment Hardening

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 4, 2026  
**Previous work:** MVP-014 (CLI integration via FastAPI backend) should be complete before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-015 hardens deployment so the current MVP stack can run reliably on Render as a production API service.

By MVP-014, the core query path is wired:

- retrieval (`src/retrieval/search.py`)
- reranking (`src/retrieval/reranker.py`)
- generation (`src/generation/llm.py`)
- API orchestration (`src/api/routes.py`)
- CLI client to API (`src/api/client.py`, `src/cli/main.py`)

MVP-015 should focus on shipping that backend safely with deployment config, runtime checks, and production-operational docs.

### Why It Matters

- **Deployment reliability:** avoid "works locally, fails in Render" issues.
- **Operational clarity:** required env vars and health expectations are explicit.
- **Release confidence:** MVP-016 smoke testing can run on a stable deployed target.
- **Single source of truth:** deployment behavior is encoded in repo config, not tribal knowledge.

---

## What Was Already Done

- Render baseline service exists (`render.yaml` + `Dockerfile`) with health endpoint wiring.
- API app exists and serves:
  - `GET /api/health`
  - `GET /api/codebases`
  - `POST /api/query`
  - `POST /api/stream`
- CLI now targets API contracts (`src/api/client.py` + `src/cli/main.py`) from MVP-014.
- Environment and deployment guide exists (`Docs/reference/ENVIRONMENT.md`) but needs hardening-level alignment with current runtime expectations.

---

## MVP-015 Contract (Critical Reference)

### Deployment Target

Primary deployment target for MVP:

- **Platform:** Render (Docker runtime)
- **Service:** FastAPI backend only
- **Vector store:** Qdrant Cloud (managed, external)

### Required Production Env Vars

```text
VOYAGE_API_KEY
OPENAI_API_KEY
COHERE_API_KEY
QDRANT_URL
QDRANT_API_KEY
LEGACYLENS_LLM_MODEL
LEGACYLENS_COLLECTION
```

### Minimum Production-Ready Behavior

1. container builds reproducibly from `Dockerfile`
2. service starts without manual shell steps
3. health route returns deterministic `200` payload
4. codebase metadata route returns deterministic `200` payload
5. query route failure modes are actionable (validation vs runtime)
6. deployment assumptions are documented for handoff and smoke testing

---

## What MVP-015 Must Accomplish

### Goal

Make Render deployment deterministic and operator-friendly so MVP-016 can run production smoke tests against a stable backend.

### Deliverables Checklist

#### A. Deployment Config Hardening (`Dockerfile`, `render.yaml`)

- [ ] Verify Docker build and startup command are production-safe
- [ ] Ensure Render service config reflects current API entrypoint and health path
- [ ] Ensure env var set is complete for runtime dependencies
- [ ] Confirm collection/model defaults are explicit and documented
- [ ] Resolve any obvious config drift between repo docs and deploy config

#### B. Runtime Readiness and API Baseline (`src/api/app.py`, optional `src/api/routes.py`)

- [ ] Keep `/api/health` deterministic and useful for platform health checks
- [ ] Keep `/api/codebases` stable for operational sanity checks
- [ ] Avoid introducing heavy startup coupling that breaks cold-start behavior
- [ ] Add minimal hardening only where needed (no feature-scope expansion)

#### C. Deployment Verification Coverage (`tests/test_api.py`)

- [ ] TDD first for any new/adjusted deployment-readiness behavior
- [ ] Add/extend tests for baseline operational routes:
  - health response contract
  - codebases response contract
  - any modified deployment-facing behavior
- [ ] Keep tests focused on MVP-015 scope (deployment/readiness, not feature logic)

#### D. Operational Documentation (`Docs/reference/ENVIRONMENT.md`, `README.md`)

- [ ] Document exact Render deployment flow and required env vars
- [ ] Document production verification commands (health, codebases, query sanity)
- [ ] Document known free-tier behavior (cold start expectations)
- [ ] Ensure README deployed API reference matches actual service assumptions

#### E. Ticket Logging

- [ ] Add MVP-015 implementation entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Capture final deployed URL, verification commands, and observed outcomes
- [ ] Note unresolved non-scope issues (if any) without silently fixing unrelated modules

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before implementation:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-015-render-deployment-hardening`
- Never commit directly to `main`.
- Use Conventional Commits (`test:`, `feat:`, `fix:`, `docs:`).
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-015-render-deployment-hardening`

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `Dockerfile` | Harden container startup/build assumptions |
| `render.yaml` | Align Render runtime config and env declarations |
| `src/api/app.py` | Baseline health/codebases hardening only if required |
| `tests/test_api.py` | Add deployment-readiness route tests |
| `Docs/reference/ENVIRONMENT.md` | Update deploy/runbook verification steps |
| `README.md` | Keep deployment summary consistent with actual setup |
| `Docs/tickets/DEVLOG.md` | Add MVP-015 completion entry |

### Files You Should NOT Modify

- `src/retrieval/search.py` (MVP-009 scope)
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/generation/prompts.py` (MVP-011 scope)
- `src/generation/llm.py` (MVP-012 scope)
- `src/api/client.py` and `src/cli/main.py` unless deployment bugfix is required
- ingestion modules in `src/ingestion/*`
- feature modules in `src/features/*`

### Files You Should READ for Context

| File | Why |
|------|-----|
| `render.yaml` | Current Render service configuration |
| `Dockerfile` | Current container runtime assumptions |
| `src/api/app.py` | Current health and baseline routes |
| `src/config.py` | Env vars/defaults used by runtime |
| `tests/test_api.py` | Existing API contract tests |
| `Docs/reference/ENVIRONMENT.md` | Existing deployment and verification workflow |
| `README.md` | Public-facing deploy/setup references |
| `Docs/tickets/MVP-014-primer.md` | Prior ticket handoff and constraints |

---

## Suggested Implementation Pattern

### Local Container Verification First

```bash
docker build -t legacylens-api:local .
docker run --rm -p 8000:8000 --env-file .env legacylens-api:local
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/codebases
```

### Render Config Alignment

- Keep `healthCheckPath` on a deterministic route (`/api/health`)
- Ensure all required env vars are declared in `render.yaml`
- Keep startup path consistent with `uvicorn src.api.app:app`

### Production Verification (Post-Deploy)

```bash
curl -s https://<render-service>/api/health
curl -s https://<render-service>/api/codebases
curl -sS -X POST https://<render-service>/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does MAIN-LOGIC do?","feature":"code_explanation","codebase":"gnucobol"}'
```

---

## Edge Cases to Handle

1. Render service boots but listens on wrong port or wrong command path
2. Required env vars missing in Render dashboard
3. Qdrant URL/API key mismatch (service healthy but query path fails)
4. Health endpoint passes while runtime query dependencies are misconfigured
5. Cold starts on free tier interpreted as failures without retry/wait guidance
6. README/ENV docs drifting from actual deployed service behavior
7. Invalid deployment assumptions carried into MVP-016 smoke test

---

## Definition of Done for MVP-015

- [ ] Render deployment config is hardened and consistent with repo runtime
- [ ] Health + codebases operational routes are stable and tested
- [ ] Deployment/readiness tests added or updated in `tests/test_api.py`
- [ ] Environment/deployment docs updated with exact verification steps
- [ ] DEVLOG updated with MVP-015 implementation entry
- [ ] Feature branch pushed and PR opened for review

---

## Estimated Time: 75-120 minutes

| Task | Estimate |
|------|----------|
| Deployment config audit + hardening | 20-35 min |
| Add/adjust deployment-readiness tests | 15-30 min |
| Local container and endpoint verification | 15-25 min |
| Render verification + troubleshooting | 15-20 min |
| DEVLOG and docs updates | 10-15 min |

---

## After MVP-015: What Comes Next

- **MVP-016:** run full end-to-end smoke test suite (10 manual production queries).
- **G4 phase:** begin Fortran support and multi-codebase expansion after deployment baseline is stable.

MVP-015 should leave deployment predictable enough that MVP-016 is validating behavior, not discovering configuration drift.

