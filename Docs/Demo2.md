# LegacyLens G4 Demo — What We Built and How to Show It Off

> A conversational walkthrough of everything we added and improved during the G4 sprint. Think of this as the "story" of the demo — what changed, why it matters, and how to show it off.

---

## The Big Picture

When we wrapped MVP, LegacyLens could search one COBOL codebase (GnuCOBOL) through the CLI and API. Solid foundation, but not exactly a multi-codebase legacy intelligence platform. G4 was about turning that into the real thing: **five codebases, two languages, eight features, and a web UI that actually lets you pick what you're searching.**

Here's what we did and how to demo it.

---

## 1. Fortran Support — A Whole Second Language

**What we built:** A full Fortran pipeline that mirrors the COBOL one. We added a Fortran preprocessor (`fortran_parser.py`) that handles both fixed-form (Fortran 77) and free-form (Fortran 90+) — column stripping, comment extraction, continuation lines, the works. Then we built a Fortran chunker (`fortran_chunker.py`) that splits on SUBROUTINE, FUNCTION, MODULE, and PROGRAM boundaries instead of COBOL paragraphs. Same adaptive sizing (64–768 tokens), same metadata schema, so everything downstream stays language-agnostic.

**Why it matters:** LAPACK, BLAS, and GNU Fortran are all Fortran. Without this, we'd have been stuck with COBOL forever.

**How to show it:** Pick LAPACK or BLAS in the web UI and ask something like "How does DGETRF perform LU factorization?" or "What does DGEMM do for matrix multiplication?" You'll get Fortran chunks with subroutine names and file:line citations. The answers are grounded in real LAPACK/BLAS source.

---

## 2. Five Codebases — Not Just GnuCOBOL Anymore

**What we built:** We ingested four more codebases on top of GnuCOBOL:

| Codebase | Language | Chunks | What It Is |
|----------|----------|--------|------------|
| gnucobol | COBOL | 3 | Open source COBOL compiler (MVP corpus) |
| opencobol-contrib | COBOL | 3,893 | Sample programs, tools, SQL copybooks — 281k LOC |
| lapack | Fortran | 12,515 | Linear algebra library — 1.5M LOC |
| blas | Fortran | 814 | Basic linear algebra subprograms |
| gfortran | Fortran | varies | GNU Fortran compiler test suite (ingestion throttled by API limits) |

We hit a few bumps along the way: Voyage token caps, chardet mis-detecting a handful of LAPACK files as UTF-7, and rate limits on the gfortran run. We worked through them with throttled batching, encoding fixes, and a reusable `ingest_codebase()` pipeline that any of these runners can call.

**Why it matters:** You can now ask questions across COBOL and Fortran, samples and production code, math libraries and compilers. That's the multi-codebase story.

**How to show it:** Use the codebase selector in the web UI. Switch between "All codebases," "LAPACK," "BLAS," "OpenCOBOL Contrib," and "GnuCOBOL." Run the same type of query (e.g., "How is X implemented?") and watch the citations change — LAPACK gives you Fortran routines, OpenCOBOL Contrib gives you COBOL samples.

---

## 3. Codebase Selector — The Web UI Finally Catches Up

**What we built:** The backend had supported a `codebase` filter for a while, but the web UI never sent it. We fixed that. We added a `/api/codebases` proxy so the frontend can fetch the list of codebases, a `CodebaseSelector` component (pills for "All codebases" plus each of the five), and we pass the selected codebase into every query. Citations now show a small codebase badge next to each chunk so you can see at a glance whether a result came from LAPACK, BLAS, or OpenCOBOL Contrib.

**Why it matters:** Before this, every query searched everything. Now you can target a specific codebase or search across all of them — and the UI makes that choice obvious.

**How to show it:** Open the web app. You'll see the codebase selector above the feature selector. Pick "LAPACK," run "How does DGETRF perform LU factorization?" — you'll get LAPACK chunks with a "lapack" badge. Switch to "All codebases" and ask "How is matrix multiplication implemented?" — you'll get a mix of LAPACK and BLAS with badges on each citation.

---

## 4. Evaluation — We Measured It

**What we built:** A ground truth dataset with 27 queries across all five codebases and six features, and an evaluation script (`evaluation/evaluate.py`) that hits the deployed API and computes precision@5. We ran it against production and got **81.5%** (22/27). Per-codebase: gnucobol 100%, opencobol-contrib 100%, lapack 86%, blas 88%. gfortran was 0% at eval time because ingestion was still pending — excluding it, we're at 91.7%.

**Why it matters:** We're not just claiming the system works; we have numbers. Retrieval precision above 70% was a target; we're above 80%.

**How to show it:** Run `python evaluation/evaluate.py` (or with `--api-url` if you're pointing at a different endpoint). You'll get a precision@5 summary and a per-codebase breakdown. The script is reproducible — same queries, same expected answers, same metric.

---

## 5. Multi-Codebase Verification — No Leaks, No Confusion

**What we built:** A verification script (`scripts/verify_g4_007.py`) that checks (1) Qdrant counts per codebase, (2) per-codebase filtered queries return only chunks from that codebase, (3) unfiltered queries return chunks from multiple codebases, and (4) different features produce different answer styles for the same query. Everything passed. No filter leaks, no cross-contamination.

**Why it matters:** When you select "LAPACK," you get LAPACK. When you select "All," you get a mix. The metadata filtering works.

**How to show it:** Run `PYTHONPATH=. python scripts/verify_g4_007.py`. It'll hit the API, run the checks, and report. Or just demo manually: filter to BLAS, ask about DGEMM, confirm all citations are from BLAS. Then switch to All and confirm you see both LAPACK and BLAS.

---

## 6. Ingestion Hardening — Throttling, Encoding, Reusability

**What we built:** A reusable `ingest_codebase()` function that any runner script can call. It discovers files by language, preprocesses (COBOL or Fortran), chunks, embeds in batch, and indexes to Qdrant. We added rate-limit-aware embedding with configurable sub-batch size and delay, plus exponential backoff on Voyage rate limit errors. We fixed encoding issues (UTF-7 mis-detection in a few LAPACK files) and added dry-scan gates so we catch problems before we burn API credits.

**Why it matters:** Ingestion used to be "run the script and hope." Now it's reproducible, resilient to provider limits, and shared across all codebases.

**How to show it:** The runner scripts (`run_ingest_lapack.py`, `run_ingest_blas.py`, `run_ingest_opencobol_contrib.py`, etc.) are the entry points. They all call `ingest_codebase()` with the right `data_dir`, `codebase`, and `language`. You can re-run any of them for selective re-indexing.

---

## 7. All Eight Features — Still There, Still Working

**What we built:** Nothing new here — we audited and confirmed all eight features work end-to-end. Code Explanation, Dependency Mapping, Pattern Detection, Impact Analysis, Documentation Gen, Translation Hints, Bug Pattern Search, Business Logic. They all flow through the same pipeline; the `feature` param shapes the prompt and (where relevant) the reranker. No custom retrieval strategies were needed; prompt differentiation was enough.

**Why it matters:** G4 wasn't about adding features; it was about making the existing ones work across five codebases and two languages. They do.

**How to show it:** Pick a codebase, pick a feature, ask a question. Try "Translation Hints" + BLAS + "How would DAXPY look in Python?" Then try "Dependency Mapping" + LAPACK + "What subroutines does DGESV call?" Different features, different answer styles, same citation quality.

---

## Quick Demo Script (Conversational Order)

1. **Open the web app** — Make sure `LEGACYLENS_API_URL` is set in Vercel so the codebase list loads. You should see "All codebases" plus LAPACK, BLAS, GnuCOBOL, OpenCOBOL Contrib, GNU Fortran.

2. **LAPACK + Code Explanation** — Select LAPACK, ask "How does DGETRF perform LU factorization?" Show the answer and the citations. Point out the "lapack" badge.

3. **BLAS + Translation** — Select BLAS, pick "Translation Hints," ask "How would DAXPY look in Python?" Show the translation-style answer with BLAS citations.

4. **OpenCOBOL Contrib** — Select OpenCOBOL Contrib, ask "What COBOL sample programs are available?" Show the mix of samples and tools.

5. **All codebases** — Select "All codebases," ask "How is matrix multiplication implemented?" Show the mixed LAPACK/BLAS results with badges.

6. **Evaluation** — Run `python evaluation/evaluate.py` and show the precision@5 output. "We're at 81.5% on retrieval; target was 70%."

---

## What's Different From Demo.md?

Demo.md was the MVP walkthrough — one codebase (GnuCOBOL), CLI and API, proving the pipeline worked. Demo2 is the G4 story: five codebases, two languages, a web UI that lets you choose, evaluation numbers, and verification that multi-codebase filtering works. Same tech stack, same API shape, but a system that's ready to demo as a real multi-codebase legacy intelligence platform.

---

## URLs and Commands (Quick Reference)

| What | Where |
|------|-------|
| API | `https://gauntlet-assignment-3.onrender.com` |
| Web UI | Your Vercel deployment (e.g. `https://frontend-pied-alpha-71.vercel.app`) |
| Evaluation | `python evaluation/evaluate.py` |
| Multi-codebase verify | `PYTHONPATH=. python scripts/verify_g4_007.py` |
| Health check | `curl https://gauntlet-assignment-3.onrender.com/api/health` |
| Codebases list | `curl https://gauntlet-assignment-3.onrender.com/api/codebases` |

---

*Built during the G4 sprint, Mar 4–5, 2026. All 5 codebases, 8 features, dual interface, evaluation metrics, and a web UI that finally lets you pick what you're searching.*
