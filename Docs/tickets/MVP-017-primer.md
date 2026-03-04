# MVP-017 Primer: Web Interface on Vercel

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 3, 2026
**Previous work:** MVP-015 (Render deployment), MVP-016 (smoke test). See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-017 delivers a **publicly accessible web interface** for LegacyLens, deployed on Vercel. This closes the MVP hard gate requirement: "Deployed and publicly accessible" with a real user-facing UI — not just a raw API.

### Current State

| Component | URL | Status |
|-----------|-----|--------|
| FastAPI backend | `https://gauntlet-assignment-3.onrender.com` | LIVE — `/api/health`, `/api/query` working |
| Web frontend | n/a | Does not exist — no `frontend/` directory in repo |

The RAG pipeline works end-to-end (query → retrieval → rerank → GPT-4o → cited answer). There is no usable web UI.

### Why Vercel?

- **Free tier** — generous for demo/grading traffic
- **Next.js-native** — zero-config deployment
- **API routes** — proxy requests to Render backend (hides backend URL, handles timeouts)
- **Instant deploys** — push to branch, get a preview URL

---

## What Was Already Done

- FastAPI backend deployed on Render with `/health` and `/query` endpoints
- Full RAG pipeline operational: query → hybrid search → rerank → GPT-4o generation → cited answer
- GnuCOBOL codebase ingested in Qdrant Cloud
- All 8 code understanding features wired in API
- CLI client built (MVP-014)

---

## MVP-017 Contract

### What the UI Must Demo

LegacyLens is a RAG system with **8 distinct code understanding features** operating over legacy COBOL/Fortran codebases. The UI should make it obvious that:

1. Users ask natural language questions about legacy code
2. The system retrieves relevant code via semantic search
3. GPT-4o generates answers **with file:line citations**
4. Multiple analysis features are available (not just Q&A)

### The 8 Features (from `src/config.py`)

All 8 must be selectable in the UI. These are the exact `feature` values the API accepts:

| Feature Value | What It Does | Example Query |
|---------------|-------------|---------------|
| `code_explanation` | Explain what code does in plain English | "What does the PROCEDURE DIVISION do?" |
| `dependency_mapping` | Trace PERFORM/CALL chains between paragraphs | "What paragraphs does MAIN-LOGIC call?" |
| `pattern_detection` | Find structurally similar code across the codebase | "Find patterns similar to error handling routines" |
| `impact_analysis` | Identify what breaks if a section changes | "What would break if INIT-DATA is modified?" |
| `documentation_gen` | Auto-generate documentation for undocumented code | "Generate documentation for the FILE SECTION" |
| `translation_hints` | Suggest modern language equivalents (Python) | "How would PROCESS-RECORDS look in Python?" |
| `bug_pattern_search` | Detect anti-patterns and potential bugs | "Find potential bug patterns in this codebase" |
| `business_logic` | Extract business rules in plain English | "What business rules are in CALCULATE-INTEREST?" |

### Architecture

```
┌────────────────────────┐       ┌──────────────────────────────────┐
│   Vercel (Next.js)     │       │  Render (FastAPI)                │
│                        │       │                                  │
│  Browser ──► Page      │       │                                  │
│              │         │       │                                  │
│         /api/query ────┼──────►│  /api/query  (RAG pipeline)     │
│    (API route proxy)   │       │  /api/health (health check)     │
│                        │       │  /api/codebases (codebase list) │
│                        │       │                                  │
└────────────────────────┘       └──────────────────────────────────┘
```

Next.js API routes act as a **proxy** to the Render backend. This:
- Keeps the backend URL server-side only (not exposed to browser)
- Adds timeout handling for Render cold starts

**Important:** The backend routes are all under `/api/` (e.g. `/api/query`, `/api/health`). The deployed backend is `https://gauntlet-assignment-3.onrender.com`.

### Deployed API Contract

The deployed backend at `https://gauntlet-assignment-3.onrender.com` uses the repo code. There is only one response format.

**Request:** `POST /api/query`
```json
{
  "query": "string (required)",
  "feature": "code_explanation (default)",
  "codebase": "gnucobol (optional — only ingested codebase for MVP)"
}
```

**Response** (from `QueryResponseSchema` in `src/api/schemas.py`):
```json
{
  "answer": "The pipe-open function initializes a pipe...",
  "chunks": [
    {
      "content": "...",
      "file_path": "data/raw/gnucobol/gnucobol-contrib/tools/cobweb/cobweb-pipes/cobweb-pipes.cob",
      "line_start": 13,
      "line_end": 62,
      "name": "GOBACK+REPOSITORY",
      "language": "cobol",
      "codebase": "gnucobol",
      "score": 1.0,
      "confidence": "HIGH",
      "metadata": {}
    }
  ],
  "query": "What does pipe-open do?",
  "feature": "code_explanation",
  "confidence": "HIGH",
  "codebase_filter": "gnucobol",
  "latency_ms": 6002.9,
  "model": "gpt-4o"
}
```

The proxy layer can pass this through directly — no format normalization needed.

### Success Criteria

1. Public Vercel URL loads a functional web UI
2. Users can select any of the 8 features and submit a natural language query
3. Response displays the answer, any available citations, and latency
4. Loading state during API processing (can be 10-30s on cold start)
5. Error states handled (timeout, API down)
6. Works on desktop and mobile

---

## Deliverables Checklist

### A. Next.js Project Setup

- [ ] Create `frontend/` with Next.js 14 (App Router), TypeScript, Tailwind CSS
- [ ] `frontend/.env.local` with `LEGACYLENS_API_URL=https://gauntlet-assignment-3.onrender.com` (server-side only, NOT `NEXT_PUBLIC_`)
- [ ] `frontend/.env.example` documenting the required var

### B. API Route Proxy

- [ ] `frontend/app/api/query/route.ts` — POST proxy to Render `/api/query`
- [ ] `frontend/app/api/health/route.ts` — GET proxy to Render `/api/health`
- [ ] 45-second timeout (Render free tier cold starts)
- [ ] Pass through backend response directly (single format from `QueryResponseSchema`)
- [ ] Error responses as `{ error: string }`

### C. UI — Single Page Layout

The page has 4 sections stacked vertically:

#### 1. Header
- **Title:** "LegacyLens"
- **Subtitle:** "RAG-powered legacy code intelligence — ask questions about COBOL and Fortran codebases in natural language"
- Keep it simple, informative, sets context for what the tool is

#### 2. Feature Selector + Query Input
- **Feature dropdown or pill selector** — all 8 features listed with human-readable labels
- **Query input** — text field with contextual placeholder that changes per feature:

| Feature | Placeholder |
|---------|-------------|
| `code_explanation` | "e.g., What does the PROCEDURE DIVISION do?" |
| `dependency_mapping` | "e.g., What paragraphs does MAIN-LOGIC call?" |
| `pattern_detection` | "e.g., Find patterns similar to error handling" |
| `impact_analysis` | "e.g., What breaks if INIT-DATA changes?" |
| `documentation_gen` | "e.g., Generate docs for the FILE SECTION" |
| `translation_hints` | "e.g., How would PROCESS-RECORDS look in Python?" |
| `bug_pattern_search` | "e.g., Find potential bug patterns" |
| `business_logic` | "e.g., What business rules are in CALCULATE-INTEREST?" |

- **Submit button** — "Ask" or "Analyze" (disabled while loading)
- **Example queries section** — 3-4 clickable example queries that populate the input. These should change when the user switches features.

#### 3. Response Area
- **Answer** — rendered as formatted text (support basic markdown: paragraphs, bold, code blocks, lists)
- **Citations** — if chunks are present, show them as a collapsible list with `file_path:line_start-line_end` format
- **Metadata bar** — show latency, confidence level (if available), model name (if available)
- **Empty state** — before any query, show a brief "Select a feature and ask a question" message
- **Loading state** — spinner/skeleton with "Analyzing codebase..." text. Add a note: "First request may take up to 30 seconds while the server warms up."
- **Error state** — clear error message with a "Try again" button

#### 4. Footer (minimal)
- "Built with Voyage Code 2, Qdrant, GPT-4o" or similar tech attribution
- Optional: link back to GitHub repo

### D. Vercel Deployment

- [ ] Add `LEGACYLENS_API_URL=https://gauntlet-assignment-3.onrender.com` in Vercel project settings
- [ ] Deploy via `vercel` CLI or GitHub integration
- [ ] Verify: open public URL → select feature → submit query → get answer

### E. Repo Housekeeping

- [ ] Update `README.md` with Vercel URL and frontend setup instructions
- [ ] Update `.gitignore` with `frontend/.env.local`, `frontend/node_modules/`, `frontend/.next/`
- [ ] Add MVP-017 entry to `Docs/tickets/DEVLOG.md`

---

## Branch & Merge Workflow

```bash
git switch main && git pull
git switch -c feature/mvp-017-web-interface
# ... implement ...
git push -u origin feature/mvp-017-web-interface
```

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `style:`.

---

## Technical Specification

### File Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout, fonts, metadata
│   ├── page.tsx            # Main single-page app
│   ├── globals.css         # Tailwind base + custom styles
│   └── api/
│       ├── query/
│       │   └── route.ts    # POST proxy → Render /query
│       └── health/
│           └── route.ts    # GET proxy → Render /health
├── components/
│   ├── Header.tsx          # Title + subtitle
│   ├── FeatureSelector.tsx # All 8 features as pills/dropdown
│   ├── QueryInput.tsx      # Input + submit + example queries
│   └── ResponsePanel.tsx   # Answer + citations + metadata + states
├── lib/
│   ├── types.ts            # QueryRequest, QueryResponse, RetrievedChunk
│   └── features.ts         # Feature config: labels, placeholders, examples
├── tailwind.config.ts
├── next.config.js
├── tsconfig.json
├── package.json
├── .env.example
└── .env.local              # (gitignored)
```

### Feature Configuration (`lib/features.ts`)

```typescript
export const FEATURES = [
  {
    value: "code_explanation",
    label: "Code Explanation",
    description: "Explain what code does in plain English",
    placeholder: "e.g., What does the PROCEDURE DIVISION do?",
    examples: [
      "What does the PROCEDURE DIVISION do?",
      "Explain the INIT-DATA paragraph",
      "What does CALCULATE-INTEREST do?",
    ],
  },
  {
    value: "dependency_mapping",
    label: "Dependency Mapping",
    description: "Trace PERFORM/CALL chains between paragraphs",
    placeholder: "e.g., What paragraphs does MAIN-LOGIC call?",
    examples: [
      "What paragraphs does MAIN-LOGIC call?",
      "Trace PERFORM calls from PROCESS-RECORDS",
      "What are the dependencies of the INIT section?",
    ],
  },
  {
    value: "pattern_detection",
    label: "Pattern Detection",
    description: "Find structurally similar code across the codebase",
    placeholder: "e.g., Find patterns similar to error handling",
    examples: [
      "Find patterns similar to error handling routines",
      "What code patterns repeat across the codebase?",
      "Find similar code to CALCULATE-INTEREST",
    ],
  },
  {
    value: "impact_analysis",
    label: "Impact Analysis",
    description: "What breaks if this code changes?",
    placeholder: "e.g., What breaks if INIT-DATA changes?",
    examples: [
      "What would break if INIT-DATA is modified?",
      "What depends on CALCULATE-INTEREST?",
      "Impact of changing the FILE SECTION",
    ],
  },
  {
    value: "documentation_gen",
    label: "Documentation",
    description: "Auto-generate docs for undocumented code",
    placeholder: "e.g., Generate docs for the FILE SECTION",
    examples: [
      "Generate documentation for the FILE SECTION",
      "Document the MAIN-LOGIC paragraph",
      "Write docs for PROCESS-RECORDS",
    ],
  },
  {
    value: "translation_hints",
    label: "Translation Hints",
    description: "Modern language equivalents (Python)",
    placeholder: "e.g., How would PROCESS-RECORDS look in Python?",
    examples: [
      "How would PROCESS-RECORDS look in Python?",
      "Translate CALCULATE-INTEREST to Python",
      "What's the modern equivalent of this COBOL pattern?",
    ],
  },
  {
    value: "bug_pattern_search",
    label: "Bug Patterns",
    description: "Detect anti-patterns and potential bugs",
    placeholder: "e.g., Find potential bug patterns",
    examples: [
      "Find potential bug patterns in this codebase",
      "Are there any common anti-patterns?",
      "Check for error handling issues",
    ],
  },
  {
    value: "business_logic",
    label: "Business Logic",
    description: "Extract business rules in plain English",
    placeholder: "e.g., What business rules are in CALCULATE-INTEREST?",
    examples: [
      "What business rules are in CALCULATE-INTEREST?",
      "Extract business logic from the PROCEDURE DIVISION",
      "What calculations does this program perform?",
    ],
  },
] as const;
```

### Types (`lib/types.ts`)

These types match the actual `QueryResponseSchema` from `src/api/schemas.py`:

```typescript
export interface RetrievedChunk {
  content: string;
  file_path: string;
  line_start: number;
  line_end: number;
  name: string;
  language: string;
  codebase: string;
  score: number;
  confidence: string;
  metadata: Record<string, string>;
}

export interface QueryResponse {
  answer: string;
  chunks: RetrievedChunk[];
  query: string;
  feature: string;
  confidence: string;
  codebase_filter: string | null;
  latency_ms: number;
  model: string;
}

export interface QueryRequest {
  query: string;
  feature: string;
  codebase?: string;
}
```

---

## Important Context

### Files to Create

| File | Action |
|------|--------|
| `frontend/` (entire directory) | Create Next.js 14 project |
| `frontend/.env.example` | Document `LEGACYLENS_API_URL` |

### Files to Modify

| File | Action |
|------|--------|
| `README.md` | Add Vercel URL, frontend setup instructions |
| `.gitignore` | Add `frontend/.env.local`, `frontend/node_modules/`, `frontend/.next/` |
| `Docs/tickets/DEVLOG.md` | Add MVP-017 entry |

### Files You Should NOT Modify

- Any `src/` Python code (backend is stable and deployed)
- `Dockerfile`, `render.yaml` (backend deployment is separate concern)
- Existing test files

### Files to READ for Context

| File | Why |
|------|-----|
| `src/config.py` | FEATURES list (all 8), CODEBASES dict |
| `src/api/schemas.py` | Query request/response schema (new format) |
| `src/api/app.py` | CORS settings (`allow_origins=["*"]`), route structure |
| `Docs/Demo.md` | Full list of demo queries across all features |

---

## Edge Cases to Handle

1. **Render cold start:** Free tier spins down after inactivity. First request takes 10-30s. Show a loading state with warm-up messaging.
2. **Empty chunks:** If retrieval finds nothing relevant, the API returns `"chunks": []` (empty). Display the answer gracefully even with no citations — don't show an empty citations section.
3. **API timeout:** If 45s passes with no response, show a retry button: "The server may be starting up. Please try again."
4. **Backend down:** If Render is completely unreachable, show "Service temporarily unavailable."
5. **Long answers:** Answers can be multiple paragraphs. The response area must scroll.
6. **Mobile:** Feature selector and input should stack vertically on small screens.
7. **Query relevance:** The ingested GnuCOBOL corpus is from gnucobol-contrib. Example queries referencing specific paragraph names (e.g. MAIN-LOGIC, CALCULATE-INTEREST) may not match. Use broader queries or names from the actual corpus (e.g. `pipe-open`, `pipe-read`).

---

## Styling

- Use a **dark theme** — dark background, light text. Standard for developer tools.
- Use Tailwind's `slate` or `gray` palette for backgrounds and text.
- Use a distinct accent color for the active feature and submit button.
- Keep it clean and professional — this is a developer tool, not a consumer app.
- No need to match any specific reference. The layout should feel natural for a "select feature → type query → see results" workflow.

---

## Definition of Done for MVP-017

- [ ] Next.js app in `frontend/` with feature selector, query input, response display
- [ ] All 8 features selectable with contextual placeholders and example queries
- [ ] API route proxy normalizes both backend response formats
- [ ] Loading and error states handle cold starts gracefully
- [ ] Deployed to Vercel with public URL
- [ ] End-to-end: open browser → select feature → type query → see cited answer
- [ ] README updated with Vercel URL
- [ ] DEVLOG updated with MVP-017 entry
- [ ] Feature branch pushed and PR opened

---

## After MVP-017

With the web UI deployed:
- MVP hard gate "Deployed and publicly accessible" is fully satisfied with a real user interface
- Share the Vercel URL for grading and teammate testing
- Future improvements: conversation history, streaming responses, code syntax highlighting, multi-codebase selector
