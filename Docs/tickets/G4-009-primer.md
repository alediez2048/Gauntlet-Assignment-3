# G4-009 Primer: Vercel Frontend — Codebase Selector & Multi-Codebase Demo

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 4, 2026
**Previous work:** G4-008 (ground truth evaluation) complete. All 5 codebases indexed. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-009 updates the Vercel-deployed Next.js frontend so users can **select which codebase to search** and **see which codebase each citation came from**. This makes the G4 multi-codebase work (5 codebases, 8 features) demonstrable through the web UI.

The current frontend sends only `query` and `feature` to the API — it never sends `codebase`. As a result, every query searches across all codebases and there is no way to target LAPACK, BLAS, OpenCOBOL Contrib, etc. from the UI.

### Why Does This Exist?

1. **Demo readiness:** Stakeholders need to see LAPACK, BLAS, COBOL, and Fortran queries in action — not just "one big search."
2. **API parity:** The backend already supports `codebase` filtering; the frontend should expose it.
3. **Citation clarity:** When querying "All" or when results span multiple codebases, each citation should show its source codebase.
4. **GFA prep:** This unblocks GFA-013 (demo video) and GFA-016 (final regression) — the demo script requires per-codebase queries from the web app.

### Current State

| Component | Status |
|-----------|--------|
| Backend `/api/query` | Accepts `codebase` (optional); returns chunks with `codebase` field |
| Backend `/api/codebases` | Returns list of 5 codebases with name, language, description |
| Frontend query page | Sends `query` + `feature` only — no `codebase` |
| Frontend citations | Show `file_path`, `line_start`, `line_end`, `name` — no codebase badge |
| Frontend `/api/codebases` | **Does not exist** — no proxy route to backend |

---

## What Was Already Done

- Next.js 14 frontend deployed on Vercel with feature selector, query input, response panel
- Backend API deployed at `https://gauntlet-assignment-3.onrender.com`
- `frontend/app/api/query/route.ts` proxies POST to backend; forwards request body as-is
- `frontend/lib/types.ts` has `QueryRequest` with optional `codebase`; `RetrievedChunk` has `codebase`
- `ResponsePanel` shows `response.codebase_filter` in metadata bar when present (but frontend never sends it)
- All 5 codebases indexed: gnucobol, lapack, blas, opencobol-contrib, gfortran

---

## G4-009 Contract

### Phase 1: Codebase API Proxy

Add a Next.js API route that proxies `GET /api/codebases` to the backend.

**Create:** `frontend/app/api/codebases/route.ts`

- On `GET`, call `LEGACYLENS_API_URL/api/codebases`
- Return `{ codebases: [...] }` with same shape as backend
- Handle errors (503 if API URL not configured, 502 if backend unreachable)
- Use same timeout pattern as `query/route.ts` (e.g. 15s for codebases)

### Phase 2: Codebase Selector Component

**Create:** `frontend/components/CodebaseSelector.tsx`

- Fetch codebases from `/api/codebases` on mount (or use SWR/React Query if preferred; simple `useEffect` + `fetch` is sufficient)
- Display a selector (dropdown or chip list) with:
  - **"All codebases"** — value `null` (search across everything)
  - One option per codebase from the API (e.g. `gnucobol`, `lapack`, `blas`, `opencobol-contrib`, `gfortran`)
- Use human-readable labels where helpful (e.g. "LAPACK", "BLAS", "OpenCOBOL Contrib", "GnuCOBOL", "GNU Fortran")
- Match the visual style of `FeatureSelector` (slate/emerald theme, rounded pills or similar)
- Props: `selected: string | null`, `onSelect: (codebase: string | null) => void`, `disabled?: boolean`
- Loading/error states: show "Loading codebases…" or fallback to "All" if fetch fails

### Phase 3: Integrate Codebase into Query Page

**Modify:** `frontend/app/page.tsx`

- Add state: `codebase: string | null` (default `null` = All)
- Add `CodebaseSelector` above or beside the Feature selector
- Include `codebase` in the request body when calling `/api/query`:
  - If `codebase === null`, omit the field or send `codebase: null` (backend treats null as "search all")
  - If `codebase` is a string, send it
- Clear `response` when codebase changes (same as when feature changes)

### Phase 4: Per-Chunk Codebase Display

**Modify:** `frontend/components/ResponsePanel.tsx`

- In the citations section, for each chunk display a small **codebase badge** next to the file path
- Use `chunk.codebase` (already present in `RetrievedChunk`)
- Style: subtle pill/badge (e.g. `rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-500`) — distinct from the `name` badge
- Layout: `file_path:line_start-line_end` on one line; `name` and `codebase` as badges (e.g. `name` on right, `codebase` below or inline)
- When `response.codebase_filter` is set, the filter is redundant with chunk codebase; still show per-chunk codebase for consistency and for future "All" queries

---

## Deliverables Checklist

- [ ] `frontend/app/api/codebases/route.ts` — proxy to backend `/api/codebases`
- [ ] `frontend/components/CodebaseSelector.tsx` — selector with "All" + 5 codebases
- [ ] `frontend/app/page.tsx` — codebase state, CodebaseSelector, pass `codebase` in query body
- [ ] `frontend/components/ResponsePanel.tsx` — codebase badge per citation
- [ ] Manual verification: select LAPACK, run "How does DGETRF perform LU factorization?", confirm LAPACK chunks
- [ ] Manual verification: select "All", run "How is matrix multiplication implemented?", confirm mixed codebases with badges
- [ ] DEVLOG updated with G4-009 entry

### Files to Create

| File | Action |
|------|--------|
| `frontend/app/api/codebases/route.ts` | Create — proxy GET to backend |
| `frontend/components/CodebaseSelector.tsx` | Create — codebase selector component |

### Files to Modify

| File | Action |
|------|--------|
| `frontend/app/page.tsx` | Add codebase state, CodebaseSelector, pass codebase in query |
| `frontend/components/ResponsePanel.tsx` | Add codebase badge per citation |
| `Docs/tickets/DEVLOG.md` | Add G4-009 entry |

### Files You Should READ for Context

- `frontend/app/page.tsx` — current query flow, state, and layout
- `frontend/components/FeatureSelector.tsx` — visual pattern for selector components
- `frontend/components/ResponsePanel.tsx` — citation layout, badge styling
- `frontend/app/api/query/route.ts` — proxy pattern, env var usage
- `frontend/lib/types.ts` — `QueryRequest`, `RetrievedChunk`, `QueryResponse`
- `src/api/app.py` — backend `/api/codebases` endpoint (lines 35–47)

### Files You Should NOT Modify

- Any source code in `src/` (backend)
- `frontend/app/api/query/route.ts` — it already forwards the body; no changes needed
- `frontend/lib/types.ts` — types already support `codebase`
- Ingestion scripts, evaluation scripts, config files

---

## Implementation Notes

### Codebase Label Mapping

The backend returns `name` (e.g. `gnucobol`, `opencobol-contrib`). Use friendly labels for the UI:

| Backend `name` | Display Label |
|----------------|---------------|
| gnucobol | GnuCOBOL |
| opencobol-contrib | OpenCOBOL Contrib |
| lapack | LAPACK |
| blas | BLAS |
| gfortran | GNU Fortran |

### API Contract (Reference)

**Backend `GET /api/codebases` response:**
```json
{
  "codebases": [
    {
      "name": "gnucobol",
      "language": "cobol",
      "description": "Open source COBOL compiler"
    },
    ...
  ]
}
```

**Backend `POST /api/query` request (relevant fields):**
```json
{
  "query": "string",
  "feature": "code_explanation",
  "codebase": "lapack"   // or null / omitted for "all"
}
```

### Demo Script (For Verification)

1. **LAPACK:** Select "LAPACK" → "How does DGETRF perform LU factorization?" → Expect LAPACK chunks, codebase badge "lapack"
2. **BLAS:** Select "BLAS" → "What does DGEMM do for matrix multiplication?" → Expect BLAS chunks
3. **OpenCOBOL Contrib:** Select "OpenCOBOL Contrib" → "What COBOL sample programs are available?" → Expect opencobol-contrib chunks
4. **All:** Select "All codebases" → "How is matrix multiplication implemented?" → Expect mixed lapack/blas chunks with badges
5. **Feature + codebase:** Select "BLAS" + "Translation Hints" → "How would DAXPY look in Python?" → Expect translation-styled answer with BLAS citations

---

## Definition of Done

- [ ] Codebase selector visible on query page; user can pick "All" or any of 5 codebases
- [ ] Query requests include `codebase` when a specific codebase is selected
- [ ] Citations display codebase badge per chunk
- [ ] Manual demo flow (LAPACK, BLAS, OpenCOBOL Contrib, All) verified in browser
- [ ] No regressions: existing feature selector and query flow still work
- [ ] DEVLOG updated with G4-009 entry
