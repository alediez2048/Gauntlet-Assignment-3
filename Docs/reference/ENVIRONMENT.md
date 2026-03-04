# Environment Guide

Quick reference for running, testing, deploying, and troubleshooting the LegacyLens stack.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  LOCAL (Development)                  │  PRODUCTION                  │
│                                       │                              │
│  Python venv                          │  Render (free tier)          │
│    └─ FastAPI (:8000)  ←──────────→   │    └─ legacylens-api (Docker)│
│         ↕                             │         ↕                    │
│  Qdrant Cloud (shared)                │  Qdrant Cloud (same cluster) │
│         ↕                             │         ↕                    │
│  Voyage Code 2 API                    │  Voyage Code 2 API           │
│  OpenAI GPT-4o API                    │  OpenAI GPT-4o API           │
│  Cohere Rerank API                    │  Cohere Rerank API           │
│                                       │                              │
│  Next.js dev server (:3000)           │  Vercel (planned, GFA phase) │
│    └─ frontend/  ←───────────────→    │    └─ <pending>.vercel.app   │
│                                       │                              │
│  CLI (python -m src.cli.main)         │  CLI (hits deployed API)     │
└──────────────────────────────────────────────────────────────────────┘
```

**Both the FastAPI backend and Qdrant Cloud must be reachable before the system can answer queries.**

---

## 0. API Keys & External Services

### Required Accounts (Sign Up Before Starting)

| Service | Sign Up URL | What You Get | Cost |
|---|---|---|---|
| Voyage AI | https://dash.voyageai.com/ | `VOYAGE_API_KEY` — embedding API | Pay-per-use (~$5-10 for full ingestion) |
| OpenAI | https://platform.openai.com/ | `OPENAI_API_KEY` — GPT-4o generation | Pay-per-use (~$10-30 for sprint) |
| Cohere | https://dashboard.cohere.com/ | `COHERE_API_KEY` — rerank API | Free tier available |
| Qdrant Cloud | https://cloud.qdrant.io/ | `QDRANT_URL` + `QDRANT_API_KEY` — vector DB | Free tier (1GB) |
| Render | https://render.com/ | API hosting | Free tier |
| Vercel | https://vercel.com/ | Frontend hosting | Free tier |

### Verifying API Keys

```bash
# Voyage AI — should return embeddings
curl -sS https://api.voyageai.com/v1/embeddings \
  -H "Authorization: Bearer $VOYAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"voyage-code-2","input":["hello"]}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'data' in d else f'ERROR: {d}')"

# OpenAI — should return a chat completion
curl -sS https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'choices' in d else f'ERROR: {d}')"

# Qdrant Cloud — should return collections list
curl -sS "$QDRANT_URL/collections" \
  -H "api-key: $QDRANT_API_KEY" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'result' in d else f'ERROR: {d}')"

# Cohere — should return reranked results
curl -sS https://api.cohere.com/v2/rerank \
  -H "Authorization: Bearer $COHERE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"rerank-v3.5","query":"test","documents":["a","b"]}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'results' in d else f'ERROR: {d}')"
```

---

## 1. Local Development Environment

### 1.1 Initial Setup (First Time Only)

```bash
# 1. Clone the repo
git clone <repo-url>
cd legacylens

# 2. Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys (see section 0)

# 5. Verify setup
python -c "from src.config import VOYAGE_API_KEY, OPENAI_API_KEY, QDRANT_URL; print('Keys loaded:', all([VOYAGE_API_KEY, OPENAI_API_KEY, QDRANT_URL]))"
```

### 1.2 Start the API Server

```bash
# From repo root, with venv activated
uvicorn src.api.app:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Auto-reloads on file changes.

### 1.3 Verify Health

```bash
# API health
curl -s http://localhost:8000/api/health

# Qdrant connectivity (via API)
curl -s http://localhost:8000/api/codebases

# Full query test (after ingestion)
curl -sS -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does CALCULATE-INTEREST do?","codebase":"gnucobol","feature":"code_explanation"}'
```

### 1.4 Ingest a Codebase (GnuCOBOL for MVP)

```bash
# Download GnuCOBOL source to data/raw/gnucobol/
# (exact method depends on source — see MVP-002 ticket)

# Trigger ingestion via CLI
python -m src.cli.main ingest --codebase gnucobol --path data/raw/gnucobol/

# Or via API
curl -sS -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"codebase":"gnucobol","path":"data/raw/gnucobol/"}'

# Verify ingestion
python -m src.cli.main status
```

### 1.5 Run Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_cobol_parser.py -v

# With coverage
python -m pytest tests/ -v --tb=short
```

### 1.6 Lint

```bash
ruff check . --fix
```

### 1.7 Start the Frontend (GFA Phase)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 1.8 Use the CLI

```bash
# Query (hits local API by default, or deployed API if LEGACYLENS_API_URL is set)
python -m src.cli.main query "What does CALCULATE-INTEREST do?"
python -m src.cli.main query "Show all subroutines in LAPACK" --codebase lapack
python -m src.cli.main query "Find bug patterns" --feature bug-patterns --codebase gnucobol
python -m src.cli.main query "What does DGEMM compute?" --json

# Status
python -m src.cli.main status

# Evaluate
python -m src.cli.main evaluate --dataset evaluation/ground_truth.json
```

---

## 2. Production Environment

### 2.1 Deployment Targets

| Service | Platform | URL (placeholder) | Config File |
|---|---|---|---|
| API Backend | Render (free tier, Docker) | `https://<service-name>.onrender.com` | `render.yaml` |
| Web Frontend | Vercel (free tier, Next.js) | `Pending (not deployed in Phase 0)` | `vercel.json` (planned in GFA-009) |
| Vector DB | Qdrant Cloud (free 1GB) | `https://your-cluster.qdrant.io:6333` | N/A (managed) |

### 2.2 Deploy API to Render

**Exact deployment flow:**

1. Connect GitHub repo to Render
2. Render auto-detects `render.yaml` and `Dockerfile`
3. Set these environment variables in Render dashboard (required; `sync: false` means set manually):
   - `VOYAGE_API_KEY`
   - `OPENAI_API_KEY`
   - `COHERE_API_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
4. Defaults (in `render.yaml`): `LEGACYLENS_LLM_MODEL=gpt-4o`, `LEGACYLENS_COLLECTION=legacylens`
5. Deploy triggers automatically on push to `main`

**Production verification commands (run after deploy):**

```bash
# Health — must return 200 and {"status":"ok"}
curl -s https://<your-render-service>.onrender.com/api/health

# Codebases — must return 200 and {"codebases":[...]}
curl -s https://<your-render-service>.onrender.com/api/codebases

# Query sanity (requires ingested codebase)
curl -sS -X POST https://<your-render-service>.onrender.com/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does MAIN-LOGIC do?","feature":"code_explanation","codebase":"gnucobol"}'
```

**Known free-tier behavior:** Render free tier spins down after ~15 min inactivity. First request after spin-down takes 10–30 seconds (cold start). Retry once before treating as failure.

### 2.3 Deploy Frontend to Vercel

**Important current status (Phase 0):**
- The repo currently has no `frontend/` directory and no `vercel.json`.
- Vercel can be account-prepped now, but frontend deployment is deferred until frontend scaffold work begins.

**What to do once frontend exists (GFA-001 / GFA-009):**
1. Import repo into Vercel
2. Set root directory to `frontend`
3. Select framework: Next.js
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`
5. Set that variable for both Preview and Production environments
6. Deploy and verify the frontend can successfully call the Render API

### 2.4 Verify Production Health

```bash
# API (replace with your Render service URL)
curl -s https://<your-render-service>.onrender.com/api/health
curl -s https://<your-render-service>.onrender.com/api/codebases

# Frontend — pending until GFA-009
# curl -s https://<your-vercel-domain>.vercel.app -o /dev/null -w "%{http_code}"
```

### 2.5 Prevent Render Spin-Down

Render free tier spins down after 15 minutes of inactivity. First request after spin-down takes 10-30 seconds.

**Solution:** UptimeRobot (free) pinging the health endpoint every 5 minutes.

1. Sign up at https://uptimerobot.com/
2. Add monitor: HTTP, `https://<your-render-service>.onrender.com/api/health`, every 5 min
3. The health endpoint returns `{"status":"ok"}` — it does not verify Qdrant; query failures indicate misconfigured QDRANT_URL/QDRANT_API_KEY

### 2.6 Production Ingestion

Codebases are ingested once and stored in Qdrant Cloud. The production API reads from the same Qdrant cluster used during development (shared collection).

If you need to re-ingest on production:
```bash
# Set production env vars locally, then run ingestion
QDRANT_URL=<production-url> QDRANT_API_KEY=<production-key> \
  python -m src.cli.main ingest --codebase gnucobol --path data/raw/gnucobol/
```

---

## 3. Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `VOYAGE_API_KEY` | Yes | — | Voyage AI API key for embeddings |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4o generation |
| `COHERE_API_KEY` | Yes | — | Cohere API key for rerank |
| `QDRANT_URL` | Yes | — | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Yes | — | Qdrant Cloud API key |
| `LEGACYLENS_EMBEDDING_MODEL` | No | `voyage-code-2` | Embedding model name |
| `LEGACYLENS_LLM_MODEL` | No | `gpt-4o` | Primary LLM for generation |
| `LEGACYLENS_LLM_FALLBACK_MODEL` | No | `gpt-4o-mini` | Fallback LLM on rate limit |
| `LEGACYLENS_COLLECTION` | No | `legacylens` | Qdrant collection name |
| `LEGACYLENS_API_HOST` | No | `0.0.0.0` | API bind address |
| `LEGACYLENS_API_PORT` | No | `8000` | API port |
| `LEGACYLENS_API_URL` | No | `http://0.0.0.0:8000` | Deployed API URL (CLI + frontend) |

---

## 4. Key Files

| File | Purpose |
|---|---|
| `.env` | Local environment variables (gitignored — never commit) |
| `.env.example` | Template for `.env` — copy and fill in |
| `src/config.py` | Centralized config loading from env vars |
| `requirements.txt` | Python dependencies with minimum versions |
| `Dockerfile` | API container definition (Python 3.11-slim + uvicorn) |
| `render.yaml` | Render deployment config (free tier, Docker, env vars) |
| `agents.md` | Agent context — architecture priorities + constraints |
| `CLAUDE.md` | Build/test/lint commands for Claude Code CLI |
| `Docs/architecture/system-design.md` | Data flow diagrams, component map, API endpoints |
| `Docs/tickets/DEVLOG.md` | Development log — updated after every ticket |
| `Docs/reference/ENVIRONMENT.md` | This file — environment setup guide |
| `Docs/requirements/LegacyLens_PRD_Maximalist.md` | Maximalist PRD |
| `Docs/interviews/` | Interview guide and notes |
| `evaluation/ground_truth.json` | 50+ query/answer pairs for precision measurement |
| `evaluation/evaluate.py` | Precision@5 evaluation script |

---

## 5. Common Pitfalls and Fixes

### "Module not found" Errors

**Symptom:** `ModuleNotFoundError: No module named 'src'`

**Cause:** Running from the wrong directory or without the venv activated.

**Fix:**
```bash
# Always run from repo root
cd /path/to/legacylens

# Activate venv
source .venv/bin/activate

# Run with module syntax
python -m src.cli.main query "test"
# NOT: python src/cli/main.py
```

### Qdrant Connection Refused

**Symptom:** `ConnectionError: Cannot connect to Qdrant`

**Cause:** Wrong `QDRANT_URL` or `QDRANT_API_KEY` in `.env`.

**Fix:**
```bash
# Verify URL format (must include port)
echo $QDRANT_URL  # Should be: https://xxx.qdrant.io:6333

# Test connectivity directly
curl -s "$QDRANT_URL/collections" -H "api-key: $QDRANT_API_KEY"
```

### Voyage API 401 / 403

**Symptom:** Embedding calls fail with authentication error.

**Cause:** Invalid or expired `VOYAGE_API_KEY`.

**Fix:** Generate a new key at https://dash.voyageai.com/ and update `.env`.

### OpenAI Rate Limiting (429)

**Symptom:** Generation fails with `RateLimitError`.

**Cause:** Too many concurrent requests or hitting tier limits.

**Fix:** The system auto-falls back to `gpt-4o-mini`. If persistent, wait 60 seconds or check your OpenAI usage dashboard.

### Render Cold Start (10-30s on First Request)

**Symptom:** First request after idle takes 10-30 seconds, then subsequent requests are fast.

**Cause:** Render free tier spins down after 15 min of inactivity.

**Fix:** Set up UptimeRobot keepalive (section 2.5). For grading/demo windows, hit the health endpoint manually 2 min before to warm up.

### "Collection not found" on Query

**Symptom:** Search returns error about missing Qdrant collection.

**Cause:** Ingestion hasn't been run yet, or the collection name doesn't match.

**Fix:**
```bash
# Check collection exists
curl -s "$QDRANT_URL/collections" -H "api-key: $QDRANT_API_KEY" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['result']['collections'], indent=2))"

# Re-run ingestion if needed
python -m src.cli.main ingest --codebase gnucobol --path data/raw/gnucobol/
```

### Frontend Can't Reach API (CORS)

**Symptom:** Browser console shows `CORS policy` errors.

**Cause:** FastAPI CORS middleware not configured for the frontend origin.

**Fix:** Ensure `src/api/app.py` includes CORS middleware allowing the frontend origin:
```python
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "https://<your-vercel-domain>.vercel.app"], ...)
```

### Chunking Produces Zero Chunks

**Symptom:** Ingestion completes but no vectors appear in Qdrant.

**Cause:** File extension mismatch or preprocessor error silently skipping all files.

**Fix:**
```bash
# Verify files exist with correct extensions
ls data/raw/gnucobol/**/*.cob data/raw/gnucobol/**/*.cbl 2>/dev/null | head -10

# Run with verbose logging to see which files are processed
LEGACYLENS_LOG_LEVEL=DEBUG python -m src.cli.main ingest --codebase gnucobol --path data/raw/gnucobol/
```

---

## 6. Quick Reference Card

```
SETUP:     python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
CONFIG:    cp .env.example .env  (then edit with your API keys)
START:     uvicorn src.api.app:app --reload --port 8000
TEST:      python -m pytest tests/ -v
LINT:      ruff check . --fix
CLI:       python -m src.cli.main query "What does CALCULATE-INTEREST do?"
INGEST:    python -m src.cli.main ingest --codebase gnucobol --path data/raw/gnucobol/
STATUS:    python -m src.cli.main status
EVALUATE:  python -m src.cli.main evaluate --dataset evaluation/ground_truth.json
FRONTEND:  cd frontend && npm run dev
HEALTH:    curl localhost:8000/api/health
DEPLOY:    git push origin main  (auto-deploys to Render now; Vercel after frontend scaffold)
```

---

## 7. Pre-Demo Checklist

Before any demo or grading session, run these checks:

### 7.1 Production Health

```bash
# Replace <your-render-service> with your actual Render service URL
curl -s https://<your-render-service>.onrender.com/api/health
curl -s https://<your-render-service>.onrender.com/api/codebases
# After GFA frontend deploy:
# curl -s https://<your-vercel-domain>.vercel.app -o /dev/null -w "%{http_code}\n"
```

Render endpoints should return 200. If the API returns nothing, it's in cold start — wait 30s and retry.

### 7.2 Query Smoke Test

```bash
# Baseline operational check
curl -s https://<your-render-service>.onrender.com/api/health
curl -s https://<your-render-service>.onrender.com/api/codebases | python3 -c "import sys,json; d=json.load(sys.stdin); print('Codebases:', len(d.get('codebases', [])))"

# Query smoke test (requires ingested codebase)
curl -sS -X POST https://<your-render-service>.onrender.com/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does MAIN-LOGIC do?","feature":"code_explanation","codebase":"gnucobol"}'
```

Expected: health `{"status":"ok"}`; codebases count 5; query returns cited answer.

### 7.3 Evaluation Run

```bash
python -m src.cli.main evaluate --dataset evaluation/ground_truth.json
```

Target: Precision@5 > 85%.

### 7.4 Summary

| Check | Blocking for Demo? |
|---|---|
| Production API healthy | Yes |
| Production frontend deployed | Not yet (GFA phase) |
| Query returns cited answer | Not yet (MVP-013+) |
| Evaluation precision > 85% | Yes |
| All 5 codebases queryable | Yes (G4+) |
| All 8 features work | Yes (G4+) |
| Streaming works in web UI | Recommended (GFA) |
| CLI works with deployed API | Recommended |
