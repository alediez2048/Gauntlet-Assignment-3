# LegacyLens — Product Requirements Document (Maximalist Edition)

**RAG-Powered Legacy Code Intelligence System**

> Author: Jorge Alejandro Diez
> Date: March 3, 2026
> Project: G4 Week 3 — Gauntlet AI Program
> Version: 2.0 — Maximalist Approach
> Guiding Principle: *"Max out every requirement. Ship all codebases, all 8 features, both interfaces, and exceed every performance target."*

---

## Executive Summary

LegacyLens is a Retrieval-Augmented Generation (RAG) system that makes legacy enterprise codebases (COBOL and Fortran) queryable through natural language. This maximalist PRD targets full coverage of every assignment requirement: all 5 target codebases ingested, all 8 code understanding features implemented, both CLI and web interfaces shipped, cost projections at all 4 user tiers (100/1K/10K/100K), and every deliverable polished to the highest standard.

This document synthesizes the original project specification, 30 architecture interview recommendations across 3 rounds, and pre-search research into a single actionable implementation guide. It follows the Phase 0 configuration-first methodology proven in the CollabBoard pre-search format.

### Maximalist Scope vs. Spec Minimum

| Dimension | Spec Minimum | Our Target |
|---|---|---|
| Target Codebases | 1 primary | All 5 (GnuCOBOL + GNU Fortran + LAPACK + BLAS + OpenCOBOL Contrib) |
| Code Understanding Features | 4 of 8 | All 8 of 8 |
| Query Interface | CLI or Web | Both CLI + Web (Next.js) |
| Retrieval Precision | >70% top-5 | >85% top-5 with layered re-ranking |
| Cost Analysis | Dev spend + projections | Dev spend + all 4 tiers (100/1K/10K/100K) |
| Architecture Doc | 1-2 pages | Comprehensive with diagrams, metrics, failure modes |
| Demo Video | 3-5 minutes | Narrative-driven with architecture + live queries + metrics |
| Deployment | Publicly accessible | Render + Qdrant Cloud + cron keepalive + health checks |
| Re-ranking | Optional | Mandatory: metadata-first + Cohere cross-encoder |
| Hybrid Search | Not required | Native Qdrant dense + sparse fusion |
| Streaming | Not required | SSE streaming for perceived <1s latency |

### Key Performance Targets (Elevated)

| Metric | Spec Target | Our Target | Measurement |
|---|---|---|---|
| Query Latency | <3 seconds | <1.5s perceived (streaming first-token <500ms) | End-to-end timing |
| Retrieval Precision | >70% top-5 | >85% top-5 | Ground truth evaluation script |
| File Coverage | 100% indexed | 100% across all 5 codebases | Ingestion verification |
| Ingestion Throughput | 10K+ LOC <5 min | 200K+ LOC <10 min (all codebases) | Batch pipeline timing |
| Answer Accuracy | Correct file/line refs | Correct refs + confidence + source citations | Manual + automated eval |
| Codebase Count | 1 | 5 | Ingestion pipeline |
| Features | 4 | 8 | Feature endpoint verification |
| Interfaces | 1 | 2 (CLI + Web) | Both deployed |

---

# Phase 0: Cursor & Claude Code Configuration

Before touching any project code, the development environment must be configured to maximize AI-first output quality. This phase establishes the context boundaries that prevent hallucination, enforce consistency, and keep the coding agent aligned with our architectural decisions throughout the sprint.

## 0.1 — Cursor Setup

### Model Selection Strategy

| Task Type | Model | Rationale |
|---|---|---|
| Boilerplate, file scaffolding, simple CRUD | Composer 1.5 | Cheapest, fast, sufficient for routine code |
| RAG pipeline logic, embedding integration, multi-codebase chunking | Claude Sonnet 4.5 | Strong at complex multi-file reasoning |
| Debugging retrieval bugs, architectural decisions, pipeline design | Claude Opus | Reserve for fickle bugs and architectural decisions |
| Quick code review, linting suggestions | GPT-4o / Codex Mini | Fast turnaround, low cost |

**Turn off "Auto" model selection immediately.** Manually choose models per task to control cost and quality.

### Workspace Configuration Checklist

- [ ] Open Agent Chat (Cmd+L), Terminal, and File Explorer as the triple-view default
- [ ] Verify codebase indexing status in `Cursor Settings > Indexing` — must show "Indexed"
- [ ] Disable Max Mode unless debugging a critical pipeline bug
- [ ] Check context usage indicator (bottom bar) regularly to avoid overflow

### External Documentation to Index

Add these URLs in `Cursor Settings > Features > Docs`:

- Qdrant: https://qdrant.tech/documentation/
- Voyage AI: https://docs.voyageai.com/
- OpenAI API: https://platform.openai.com/docs/
- FastAPI: https://fastapi.tiangolo.com/
- Jinja2: https://jinja.palletsprojects.com/
- Next.js: https://nextjs.org/docs
- tiktoken: https://github.com/openai/tiktoken
- Cohere Rerank: https://docs.cohere.com/docs/rerank
- chardet: https://chardet.readthedocs.io/
- Click (CLI framework): https://click.palletsprojects.com/
- Rich (terminal formatting): https://rich.readthedocs.io/

## 0.2 — .cursorrules (Non-Negotiable Project Rules)

Create `.cursor/rules/` directory with the following rule files:

### tech-stack.mdc — Enforces version pinning

```
Description: Enforce project tech stack versions
Always: true

- Language: Python 3.11+ (strict typing with type hints)
- Vector Database: Qdrant (qdrant-client >= 1.7)
- Embedding Model: Voyage Code 2 (voyageai SDK)
- LLM: OpenAI GPT-4o (openai SDK >= 1.0), configurable fallback to GPT-4o-mini
- Web Framework: Next.js 14 (App Router) for frontend + FastAPI for backend API
- CLI Framework: Click + Rich for terminal interface
- Tokenizer: tiktoken (cl100k_base encoding)
- Encoding Detection: chardet
- Re-ranking: Cohere Rerank API
- Testing: pytest + evaluation script
- Deployment: Render (API) + Vercel (frontend) + Qdrant Cloud (vector DB)
- Styling: Tailwind CSS v4 for web interface
```

### tdd.mdc — Enforces test-driven development

```
Description: Test-Driven Development methodology
Always: true
```

Before implementing any feature:

1. Write the test file first (pytest for unit and integration)
2. Confirm the test fails as expected
3. Implement the minimum code to pass the test
4. Refactor only after tests pass

For RAG pipeline features:

- Test chunking output against known paragraph/subroutine boundaries per language
- Test preprocessing by comparing column-stripped output to expected clean text
- Test retrieval by running ground truth queries and asserting relevant chunk IDs in top-5
- Test ingestion by verifying vector count in Qdrant after indexing each codebase
- Test all 8 features via dedicated endpoint tests with expected output patterns
- Test CLI commands produce same results as web API endpoints

For multi-codebase features:

- Test that language detection correctly identifies COBOL vs Fortran files
- Test that language-specific preprocessors are dispatched correctly
- Test cross-codebase queries return results from the correct codebase
- Test codebase filtering via metadata works in retrieval

### code-patterns.mdc — Enforces architectural consistency

```
Description: Code patterns and conventions
Always: true
```

- All ingestion logic goes in `src/ingestion/`
- All retrieval logic goes in `src/retrieval/`
- All generation logic goes in `src/generation/`
- All API routes go in `src/api/`
- All CLI commands go in `src/cli/`
- All types go in `src/types/`
- All feature-specific logic goes in `src/features/`
- Every function must have Python type hints and return types
- No `any` types — use explicit typing everywhere
- Error handling: always use try/except with typed exceptions
- Environment variables via python-dotenv, never hardcoded
- All embedding API calls must use batch mode (128 texts per call)
- LLM model must be configurable via `LEGACYLENS_LLM_MODEL` env var
- Chunk metadata must include: `file_path, line_start, line_end, paragraph_name, division, chunk_type, language, codebase`
- Every feature must be accessible via both CLI and API

### rag-pipeline.mdc — Enforces RAG-specific patterns

```
Description: RAG pipeline architecture rules
Always: true
```

- Custom pipeline — NO LangChain, NO LlamaIndex
- Multi-language support: COBOL preprocessor + Fortran preprocessor, dispatched by file extension
- Chunking must respect language-specific boundaries (COBOL paragraphs, Fortran subroutines)
- Chunk size: adaptive 64–768 tokens on structural boundaries
- Embeddings: batch mode via Voyage Code 2 (128 texts per API call)
- Vector storage: Qdrant with payload indexes on `paragraph_name`, `division`, `file_path`, `language`, `codebase`
- Retrieval: hybrid search (dense + sparse/BM25) via Qdrant native support
- Re-ranking: metadata-based first (free), then Cohere cross-encoder second
- Context assembly: dynamic token budget with hierarchical expansion for top-1 result
- Generation: structured language-aware system prompt with confidence output
- All answers must include file:line citations
- All 8 features must be implemented as composable prompt + retrieval strategies

### multi-codebase.mdc — Enforces multi-codebase patterns

```
Description: Multi-codebase handling rules
Always: true
```

- Each codebase gets its own Qdrant collection OR shared collection with `codebase` metadata field
- Language detection via file extension: `.cob`, `.cbl`, `.cpy` → COBOL; `.f`, `.f90`, `.f77` → Fortran
- Preprocessing dispatches to language-specific handler based on detection
- Chunking strategy adapts per language: paragraph-based for COBOL, subroutine-based for Fortran
- Users can query across all codebases or filter to a specific one
- Ingestion supports selective re-indexing of individual codebases
- Metadata always includes `codebase` and `language` fields for filtering

## 0.3 — .cursorignore

```
.env
.env.local
node_modules/
__pycache__/
.pytest_cache/
data/raw/          # Raw source files (large)
*.pyc
*.log
dist/
.next/
coverage/
.ruff_cache/
```

## 0.4 — Skills Installation

```bash
# Python best practices
npx skills-cli install python-fastapi --project --symlink

# React/Next.js patterns
npx skills-cli install react-nextjs --project --symlink

# RAG pipeline patterns (if available)
npx skills-cli install rag-pipeline --project --symlink
```

## 0.5 — Claude Code Configuration

If supplementing Cursor with Claude Code (CLI):

- Run `/init` in the project root to generate `CLAUDE.md`
- Add to CLAUDE.md:
  ```
  Build command: pip install -r requirements.txt && cd frontend && npm install
  Test command: python -m pytest tests/ -v
  Lint command: ruff check . --fix
  Dev server (API): uvicorn src.api.app:app --reload --port 8000
  Dev server (Web): cd frontend && npm run dev
  CLI: python -m src.cli.main
  ```
- Use Claude Code as a **reviewer**: generate code in Cursor, then run `claude review` in terminal for a second opinion on pipeline logic and retrieval quality

## 0.6 — Source Control Methodology

### Branching Strategy: Trunk-Based Development

For a solo sprint with a 24-hour MVP gate, trunk-based development is the correct choice. No team to coordinate with, and merge conflicts against yourself waste time.

### Branch Structure

```
main                    ← production (auto-deploys to Render/Vercel)
├── feat/ingestion      ← short-lived feature branches (merge same day)
├── feat/retrieval
├── feat/generation
├── feat/cli
├── feat/web-ui
├── feat/multi-codebase
├── feat/all-features
└── fix/chunking        ← hotfix branches
```

### Commit Discipline

- Commit after every working feature increment — not at end of day
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- Every commit on `main` should be deployable
- Never push broken code to `main`
- Use `git stash` liberally when context-switching between pipeline components
- Tag milestones: `git tag mvp-complete`, `git tag g4-final`, `git tag gfa-final`

### Cursor + Git Workflow

- Before starting a new Cursor Agent chat session, always `git commit` current working state
- If the agent produces bad output, `git diff` to review, then `git checkout .` to revert
- Use `git log --oneline -10` as a quick sanity check before any major agent prompt

### .gitignore

```
.env
.env.local
__pycache__/
.pytest_cache/
data/raw/
*.pyc
*.log
dist/
.next/
node_modules/
coverage/
.ruff_cache/
.vercel/
```

## 0.7 — System Design Methodology

Before prompting the coding agent to scaffold anything, establish the system design on paper. The agent writes better code when it has a complete architectural picture in context.

### Step 1: Data Flow Diagram

```
[COBOL Sources] ──┐
[Fortran Sources] ─┤
                   ▼
        ┌─────────────────────┐
        │  Language Detection  │
        │  (.cob → COBOL,     │
        │   .f → Fortran)     │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Preprocessing      │
        │  COBOL: col strip,  │
        │    encoding, comments│
        │  Fortran: free/fixed│
        │    form, comments   │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Chunking           │
        │  COBOL: paragraph   │
        │  Fortran: subroutine│
        │  Adaptive 64-768 tok│
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Metadata Extraction│
        │  file, lines, name, │
        │  division, language, │
        │  codebase, deps     │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Batch Embedding    │
        │  Voyage Code 2      │
        │  128 texts/call     │
        │  1536 dimensions    │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Qdrant Storage     │
        │  Hybrid index       │
        │  Payload metadata   │
        └─────────────────────┘

[User Query via CLI or Web]
        │
        ▼
   ┌──────────┐    ┌──────────────┐    ┌─────────────┐
   │  Embed   │───▶│ Hybrid Search│───▶│  Re-rank    │
   │  Query   │    │ Dense+BM25   │    │ Meta+Cohere │
   └──────────┘    └──────────────┘    └──────┬──────┘
                                              ▼
                                    ┌─────────────────┐
                                    │ Context Assembly │
                                    │ Dynamic budget + │
                                    │ hierarchical exp │
                                    └────────┬────────┘
                                             ▼
                                    ┌─────────────────┐
                                    │ Feature Router   │
                                    │ 8 feature prompts│
                                    │ + GPT-4o stream  │
                                    └────────┬────────┘
                                             ▼
                                    ┌─────────────────┐
                                    │ Cited Answer +   │
                                    │ Confidence Score │
                                    │ → CLI or Web UI  │
                                    └─────────────────┘
```

### Step 2: Component Ownership Map

| Component | Owner Module | External Dependency | Failure Mode |
|---|---|---|---|
| Language Detection | `src/ingestion/detector.py` | None (file extension) | Unknown extension → skip with warning |
| COBOL Preprocessor | `src/ingestion/cobol_parser.py` | chardet | Encoding corruption → log + skip |
| Fortran Preprocessor | `src/ingestion/fortran_parser.py` | chardet | Fixed/free form misdetection → fallback |
| COBOL Chunker | `src/ingestion/cobol_chunker.py` | tiktoken | Wrong paragraph boundaries → validation tests |
| Fortran Chunker | `src/ingestion/fortran_chunker.py` | tiktoken | Wrong subroutine boundaries → validation tests |
| Batch Embedder | `src/ingestion/embedder.py` | Voyage API | Timeout → retry with backoff, cache |
| Qdrant Indexer | `src/ingestion/indexer.py` | Qdrant Cloud | Connection failure → graceful error |
| Hybrid Search | `src/retrieval/search.py` | Qdrant Cloud | Latency spike → timeout + error |
| Re-ranking | `src/retrieval/reranker.py` | Cohere API | Fallback to metadata-only ranking |
| Context Assembly | `src/retrieval/context.py` | tiktoken | Token overflow → truncation logic |
| Feature Router | `src/features/router.py` | None | Unknown feature → default to Code Explanation |
| LLM Generation | `src/generation/llm.py` | OpenAI API | Timeout → fallback to GPT-4o-mini |
| FastAPI Backend | `src/api/app.py` | FastAPI/Uvicorn | Crash → auto-restart via Render |
| CLI Interface | `src/cli/main.py` | Click/Rich | N/A (local) |
| Next.js Frontend | `frontend/` | Vercel | Cold start → cron keepalive |

### Step 3: Feed the Design to the Agent

Once the data flow and component ownership exist as markdown files in the project root, reference them in every Cursor prompt:

- "Based on @system-design.md, implement the COBOL preprocessor module"
- "Following the component map in @system-design.md, build the Fortran chunker"
- "Using the feature router pattern in @system-design.md, implement Pattern Detection"

This eliminates the most common failure mode: the agent inventing its own architecture that conflicts with the pipeline design.

## 0.8 — agents.md (Project-Level Context)

Create `agents.md` in root with high-level non-negotiables:

```markdown
# LegacyLens — Agent Context

## What We're Building
A RAG system that makes ALL legacy codebases (COBOL + Fortran) queryable
through natural language. Five codebases, eight features, two interfaces.
Ingest → Embed → Store → Retrieve → Re-rank → Generate.

## Architecture Priorities (in order)
1. Chunking quality — foundation of everything downstream
2. Retrieval precision — >85% in top-5, measured by eval script
3. Answer accuracy — correct file:line citations, no hallucination
4. Multi-codebase support — all 5 codebases indexed with language-aware processing
5. All 8 features — every code understanding feature implemented
6. Dual interface — both CLI and web must work
7. Deployment — publicly accessible on Render + Vercel + Qdrant Cloud

## Critical Constraints
- Custom pipeline: NO LangChain, NO LlamaIndex
- Language-aware processing: COBOL paragraphs, Fortran subroutines
- Adaptive chunking on structural boundaries (64-768 tokens)
- Batch embedding via Voyage Code 2 (128 texts/call)
- Hybrid search (dense + BM25) via Qdrant native
- Layered re-ranking: metadata-first + Cohere cross-encoder
- Structured language-aware prompt for generation
- All answers cite file:line references
- All 8 features: Explain, Dependencies, Patterns, Impact, Docs, Translation, Bugs, BusinessLogic

## DO NOT
- Use LangChain or LlamaIndex
- Use fixed-size chunking
- Skip column stripping for COBOL preprocessing
- Skip fixed/free form detection for Fortran preprocessing
- Hardcode API keys
- Skip type hints on any function
- Implement fewer than 8 features
- Ship only CLI or only Web — both are required
```

---

# Phase 1: Define Your Constraints

## 1. Scale & Load Profile

**Users at launch:** 1–2 (solo developer + grader evaluation). The evaluation tests the deployed app with specific queries across all codebases.

**Users at 6 months (projected):** 10–100 if this becomes a showcase project. Cost analysis covers up to 100K users.

**Traffic pattern:** Burst during grading windows, then idle. The backend must handle sudden query bursts but doesn't need sustained throughput.

**Total codebase size:** ~850K+ LOC across all 5 codebases:

| Codebase | Language | Approx LOC | Files | Description |
|---|---|---|---|---|
| GnuCOBOL | COBOL | ~200K+ | 50+ | Open source COBOL compiler |
| GNU Fortran (gfortran) | Fortran | ~300K+ | 100+ | Fortran compiler in GCC |
| LAPACK | Fortran | ~600K+ | 1000+ | Linear algebra library |
| BLAS | Fortran | ~20K+ | 50+ | Basic linear algebra subprograms |
| OpenCOBOL Contrib | COBOL | ~15K+ | 30+ | Sample COBOL programs and utilities |

**Ingestion strategy:** Batch ingestion per codebase. Each codebase gets indexed with its own metadata tags. Users can query across all or filter to one.

## 2. Budget & Cost Ceiling

| Item | Estimated Cost | Priority |
|---|---|---|
| Cursor Pro/Max | $20–$200/mo | Critical — primary IDE |
| Claude Max or Pro | $20–$100/mo | Critical — code review + chat |
| Voyage Code 2 API | $2–$10 total | One-time ingestion (all 5 codebases) |
| OpenAI GPT-4o API | $10–$40 | Pay-per-use for generation |
| OpenAI GPT-4o-mini API | $2–$8 | Fallback model |
| Qdrant Cloud | $0 (free tier) | 1GB storage — sufficient for all 5 codebases |
| Render | $0 (free tier) | API server hosting |
| Vercel | $0 (free tier) | Next.js frontend hosting |
| Cohere Rerank | $0–$5 | Re-ranking API |
| Domain (optional) | $0–$12 | Nice-to-have for showcase |

**Total estimated sprint spend:** $35–$75.

**Cost analysis deliverable:** Will include real measured dev spend + projections at 100, 1K, 10K, and 100K user tiers with explicit assumptions for queries/user/day, average tokens/query, embedding refresh costs, and vector DB storage at scale.

## 3. Time to Ship

**MVP timeline:** 24 hours (hard gate — pass/fail). Must have at least one codebase working with basic query → retrieval → answer pipeline deployed.

**G4 Final (Day 3):** All 5 codebases ingested, all 8 features working, evaluation metrics, architecture doc, cost analysis.

**GFA Final (Day 5):** Polished dual interface (CLI + Web), demo video, social media post.

**Priority order:**
1. Get one codebase (GnuCOBOL) working end-to-end for MVP
2. Add remaining 4 codebases (Days 2-3)
3. Implement all 8 features (Days 2-3)
4. Build Next.js frontend + CLI (Days 3-4)
5. Polish, demo, documentation (Days 4-5)

**Iteration cadence:** Day 1 is MVP. Days 2–3 are G4 Final. Days 4–5 are GFA Final.

## 4. Compliance & Regulatory

**HIPAA:** Not applicable. No health data.
**GDPR:** Not applicable. No user data collected.
**Data residency:** Not applicable. All codebases are open source.
**Decision:** No compliance overhead. Focus entirely on retrieval quality and feature completeness.

## 5. Team & Skill Constraints

**Solo or team:** Solo developer with AI coding agents.

**Languages/frameworks known well:** Python, FastAPI, React/Next.js. Moderate familiarity with embeddings and vector databases.

**Honest gaps:**
- Never built a production RAG pipeline before
- Limited experience with COBOL and Fortran syntax/structure
- No prior work with Qdrant or Voyage Code 2
- First time implementing hybrid search (dense + sparse)
- Managing 5 codebases simultaneously adds complexity

**Mitigation:** Lean heavily on Cursor with indexed docs. Pre-research COBOL structure (divisions, sections, paragraphs, COPY statements) and Fortran structure (subroutines, functions, modules, fixed vs free form) before writing parsers. Use Claude Code as a reviewer. Start with GnuCOBOL (most familiar from interviews), then add Fortran codebases.

---

# Phase 2: Architecture Discovery

## 6. Optimal Tech Stack

Every technology choice is grounded in the 30-question interview analysis and pre-search research. The guiding principle: choose the tool that maximizes retrieval quality across multiple languages with minimum integration risk.

| Layer | Technology | Rationale |
|---|---|---|
| Target Codebases | GnuCOBOL + GNU Fortran + LAPACK + BLAS + OpenCOBOL Contrib | All 5 to max out the assignment. COBOL + Fortran = full legacy coverage |
| Language | Python 3.11+ | Ecosystem dominance for ML/RAG. Type hints for reliability |
| Vector Database | Qdrant (Cloud) | Native hybrid search. Free tier 1GB. Rust-based, sub-10ms queries. Payload filtering per codebase |
| Embedding Model | Voyage Code 2 | Code-optimized, 1536 dims. Best-in-class code search benchmarks |
| LLM (Generation) | GPT-4o | Best code understanding. 128K context. Configurable fallback to GPT-4o-mini |
| LLM (Features) | GPT-4o | All 8 features use same model with different prompt strategies |
| Re-ranking | Metadata-first + Cohere Rerank | Zero-cost metadata layer + cross-encoder for precision |
| Backend API | FastAPI | Async, fast, OpenAPI docs auto-generated |
| Frontend (Web) | Next.js 14 (App Router) | React-based, SSR for SEO, Tailwind for styling |
| CLI | Click + Rich | Professional terminal interface with syntax highlighting |
| Tokenizer | tiktoken (cl100k_base) | Precise token counting for context budget |
| Encoding Detection | chardet | Handles EBCDIC and legacy encodings |
| Deployment (API) | Render | Free tier, Docker support, no function timeouts |
| Deployment (Web) | Vercel | Free tier, Next.js native, auto-deploy from git |
| Deployment (VectorDB) | Qdrant Cloud | Managed, 1GB free, independent scaling |
| RAG Framework | Custom Pipeline | No LangChain/LlamaIndex. Full control, interview credibility |

## 7. All 8 Code Understanding Features

Unlike the minimum spec (4 of 8), we implement ALL features. Each feature is a composable combination of retrieval strategy + prompt template + output format.

| # | Feature | Description | Retrieval Strategy | Prompt Strategy |
|---|---|---|---|---|
| 1 | **Code Explanation** | Explain what a function/section does in plain English | Standard hybrid search for relevant chunks | "Explain this code in plain English. Cite file:line." |
| 2 | **Dependency Mapping** | Show what calls what, data flow between modules | Metadata-filtered search for PERFORM/CALL references + BM25 keyword match | "Trace the call chain. Show which modules depend on which." |
| 3 | **Pattern Detection** | Find similar code patterns across the codebase | Embedding similarity search across ALL chunks (not just top-k) + clustering | "Identify recurring patterns. Group similar code." |
| 4 | **Impact Analysis** | What would be affected if this code changes? | Dependency graph traversal + reverse-lookup of PERFORM/CALL targets | "If this code changes, what else breaks? Trace all dependents." |
| 5 | **Documentation Gen** | Generate documentation for undocumented code | Target chunk + surrounding context (hierarchical expansion) | "Generate professional documentation. Include purpose, inputs, outputs, side effects." |
| 6 | **Translation Hints** | Suggest modern language equivalents | Target chunk + language-specific prompt with modern equivalents | "Suggest Python/Java equivalent. Preserve business logic. Note caveats." |
| 7 | **Bug Pattern Search** | Find potential issues based on known patterns | Curated bug pattern knowledge base + BM25 keyword search for anti-patterns | "Check for: uninitialized variables, unchecked I/O, dead code, missing error handling." |
| 8 | **Business Logic Extract** | Identify and explain business rules in code | PROCEDURE DIVISION focus + conditional logic detection | "Extract all business rules. State each rule in plain English with conditions." |

### Feature Implementation Architecture

```
src/features/
├── router.py              # Dispatches to correct feature handler
├── code_explanation.py    # Feature 1
├── dependency_mapping.py  # Feature 2
├── pattern_detection.py   # Feature 3
├── impact_analysis.py     # Feature 4
├── documentation_gen.py   # Feature 5
├── translation_hints.py   # Feature 6
├── bug_pattern_search.py  # Feature 7
├── business_logic.py      # Feature 8
└── base.py                # Shared feature interface/ABC
```

Each feature implements a common interface:
```python
class BaseFeature(ABC):
    @abstractmethod
    async def retrieve(self, query: str, codebase: str | None) -> list[Chunk]: ...
    @abstractmethod
    def build_prompt(self, query: str, chunks: list[Chunk]) -> str: ...
    @abstractmethod
    async def generate(self, query: str, codebase: str | None) -> FeatureResponse: ...
```

## 8. Dual Interface Architecture

### CLI Interface (Click + Rich)

```
legacylens query "What does CALCULATE-INTEREST do?"
legacylens query "Show all subroutines in LAPACK" --codebase lapack
legacylens query "Find bug patterns" --feature bug-patterns --codebase gnucobol
legacylens explain src/calc-interest.cob:45-89
legacylens deps CALCULATE-INTEREST --codebase gnucobol
legacylens ingest --codebase gnucobol --path data/raw/gnucobol/
legacylens ingest --all
legacylens evaluate --dataset evaluation/ground_truth.json
legacylens status  # Show ingestion status per codebase
```

CLI features:
- Syntax-highlighted code output via Rich
- Confidence score badges (colored HIGH/MEDIUM/LOW)
- File:line clickable references (terminal hyperlinks)
- Progress bars for ingestion
- Table output for dependency maps
- JSON output mode (`--json`) for scripting
- Codebase filter (`--codebase`) and feature selection (`--feature`)

### Web Interface (Next.js 14 + Tailwind)

Pages:
- `/` — Dashboard: codebase overview, ingestion status, recent queries
- `/query` — Main query interface with codebase selector and feature picker
- `/explore/:codebase` — Browse indexed files, click to drill down
- `/results/:id` — Full result view with syntax-highlighted code, citations, confidence

Web features:
- Real-time streaming responses via SSE
- Syntax highlighting via Prism.js or Shiki
- Codebase selector dropdown (All / GnuCOBOL / GNU Fortran / LAPACK / BLAS / OpenCOBOL)
- Feature picker (all 8 features as tabs or dropdown)
- Confidence badges with color coding
- Clickable file:line references that expand inline
- Dark mode
- Mobile responsive

### Shared API Layer

Both CLI and Web consume the same FastAPI backend:

```
POST /api/query          # Main query endpoint
POST /api/query/stream   # SSE streaming endpoint
GET  /api/codebases      # List all codebases with status
POST /api/ingest         # Trigger ingestion for a codebase
GET  /api/health         # Health check
GET  /api/metrics        # Precision, latency, query count
GET  /api/features       # List available features
```

## 9. Multi-Codebase Ingestion Architecture

### Codebase Registry

```python
CODEBASES = {
    "gnucobol": {
        "language": "cobol",
        "source_url": "https://sourceforge.net/projects/gnucobol/",
        "extensions": [".cob", ".cbl", ".cpy"],
        "preprocessor": "cobol",
        "chunker": "cobol_paragraph",
        "description": "Open source COBOL compiler written in COBOL",
    },
    "gfortran": {
        "language": "fortran",
        "source_url": "https://gcc.gnu.org/wiki/GFortran",
        "extensions": [".f", ".f90", ".f77", ".f95"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Fortran compiler in GCC",
    },
    "lapack": {
        "language": "fortran",
        "source_url": "https://github.com/Reference-LAPACK/lapack",
        "extensions": [".f", ".f90"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Linear algebra library",
    },
    "blas": {
        "language": "fortran",
        "source_url": "https://www.netlib.org/blas/",
        "extensions": [".f"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Basic linear algebra subprograms",
    },
    "opencobol-contrib": {
        "language": "cobol",
        "source_url": "https://sourceforge.net/projects/open-cobol/",
        "extensions": [".cob", ".cbl", ".cpy"],
        "preprocessor": "cobol",
        "chunker": "cobol_paragraph",
        "description": "Sample COBOL programs and utilities",
    },
}
```

### Ingestion Pipeline (Per Codebase)

1. **File Discovery:** Walk source tree, filter by codebase-specific extensions
2. **Language Detection:** Dispatch to COBOL or Fortran preprocessor
3. **Preprocessing:**
   - COBOL: Column stripping (1-6, 73-80), encoding detection (chardet), comment separation (col 7 = *)
   - Fortran: Fixed-form vs free-form detection, comment extraction (C/c in col 1 for fixed, ! for free), continuation handling
4. **Chunking:**
   - COBOL: Adaptive paragraph-based (64-768 tokens), merge small paragraphs, split large at sentence boundaries
   - Fortran: Subroutine/function-based, respect PROGRAM/SUBROUTINE/FUNCTION boundaries, merge small routines
5. **Metadata Extraction:** file_path, line_start, line_end, name (paragraph/subroutine), division/module, chunk_type, language, codebase, dependencies
6. **Batch Embedding:** Voyage Code 2, 128 texts per API call, 1536 dimensions
7. **Vector Storage:** Upsert to Qdrant with full payload metadata + concurrent upserts

### Repository Structure (Expanded)

```
legacylens/
├── README.md
├── agents.md
├── system-design.md
├── .cursor/
│   └── rules/
│       ├── tech-stack.mdc
│       ├── tdd.mdc
│       ├── code-patterns.mdc
│       ├── rag-pipeline.mdc
│       └── multi-codebase.mdc
├── docs/
│   ├── architecture.md
│   ├── cost-analysis.md
│   └── pre-search.md
├── src/
│   ├── __init__.py
│   ├── config.py              # Environment variables, constants
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── detector.py        # Language detection
│   │   ├── cobol_parser.py    # COBOL preprocessing
│   │   ├── fortran_parser.py  # Fortran preprocessing
│   │   ├── cobol_chunker.py   # COBOL paragraph chunking
│   │   ├── fortran_chunker.py # Fortran subroutine chunking
│   │   ├── embedder.py        # Batch embedding (Voyage Code 2)
│   │   └── indexer.py         # Qdrant storage
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── search.py          # Hybrid search (dense + BM25)
│   │   ├── reranker.py        # Metadata + Cohere re-ranking
│   │   └── context.py         # Dynamic context assembly
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── prompts.py         # Language-aware prompt templates
│   │   └── llm.py             # OpenAI integration + streaming
│   ├── features/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract feature interface
│   │   ├── router.py          # Feature dispatcher
│   │   ├── code_explanation.py
│   │   ├── dependency_mapping.py
│   │   ├── pattern_detection.py
│   │   ├── impact_analysis.py
│   │   ├── documentation_gen.py
│   │   ├── translation_hints.py
│   │   ├── bug_pattern_search.py
│   │   └── business_logic.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py             # FastAPI application
│   │   ├── routes.py          # API endpoints
│   │   └── schemas.py         # Pydantic models
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py            # Click CLI with Rich output
│   └── types/
│       ├── __init__.py
│       ├── chunks.py
│       ├── features.py
│       └── responses.py
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           # Dashboard
│   │   ├── query/
│   │   │   └── page.tsx       # Query interface
│   │   ├── explore/
│   │   │   └── [codebase]/
│   │   │       └── page.tsx   # Codebase explorer
│   │   └── results/
│   │       └── [id]/
│   │           └── page.tsx   # Result detail view
│   └── components/
│       ├── CodeBlock.tsx       # Syntax highlighted code
│       ├── ConfidenceBadge.tsx # HIGH/MED/LOW badge
│       ├── CodebaseSelector.tsx
│       ├── FeaturePicker.tsx
│       ├── StreamingResponse.tsx
│       └── QueryInput.tsx
├── evaluation/
│   ├── ground_truth.json      # 50+ query/answer pairs across all codebases
│   ├── evaluate.py            # Precision@5 computation
│   └── results/               # Evaluation run outputs
├── tests/
│   ├── test_detector.py
│   ├── test_cobol_parser.py
│   ├── test_fortran_parser.py
│   ├── test_cobol_chunker.py
│   ├── test_fortran_chunker.py
│   ├── test_embedder.py
│   ├── test_retrieval.py
│   ├── test_generation.py
│   ├── test_features.py
│   ├── test_api.py
│   └── test_cli.py
├── data/
│   └── raw/                   # Downloaded codebase sources
│       ├── gnucobol/
│       ├── gfortran/
│       ├── lapack/
│       ├── blas/
│       └── opencobol-contrib/
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── render.yaml
└── vercel.json
```

## 10. Failure Modes & Mitigations

| Failure Mode | Detection | Mitigation |
|---|---|---|
| Zero relevant results | Top similarity score < threshold | Four-tier degradation: normal → partial match → keyword fallback → suggestions with related paragraph names |
| Hallucinated file references | Citation validation against indexed files | Structured prompt: answer ONLY from context. Post-process to verify citations exist in index |
| Embedding API timeout | Request timeout > 5s | Retry with exponential backoff (3 attempts). LRU cache for repeated queries |
| Qdrant connection failure | Connection error on search | Graceful error page/message. Health check endpoint. Auto-reconnect logic |
| LLM rate limiting | 429 response from OpenAI | Automatic fallback to GPT-4o-mini. Queue with rate limiter |
| Encoding corruption (COBOL) | chardet confidence < 0.7 | Log warning, attempt UTF-8 with replace, skip unreadable files with warning |
| Fortran fixed/free form misdetection | Parsing errors in known-good files | Heuristic: check for col-6 continuation, col-1 comments. User-configurable override |
| Chunks split mid-paragraph/subroutine | Validation against known boundaries | Assertion in chunker tests. Test suite with known COBOL/Fortran files |
| Cross-codebase query noise | Low precision when querying "all" | Boost same-codebase results in re-ranking. Metadata filter available |
| Translation Hints inaccuracy | Manual review of generated translations | Caveat in output: "These are suggestions, not guaranteed equivalents." |
| Pattern Detection false positives | Similar embeddings ≠ similar patterns | Cluster filtering + minimum similarity threshold + human-readable grouping |
| Impact Analysis incomplete graph | Missing PERFORM/CALL resolution | Document as known limitation. Parse static references only |

---

# Phase 3: Project Implementation Phases

The implementation follows a strict time-boxed sprint schedule with three checkpoints. The cardinal rule: if you're at hour 18 without a deployed app, drop everything and deploy what you have.

## Phase 3.1 — MVP Sprint (Day 1, 24 Hours)

**Goal:** Deployed, publicly accessible app with GnuCOBOL (primary codebase) working end-to-end with basic query → retrieval → answer pipeline. CLI or web interface.

| Time Block | Task | Deliverable | Success Criteria |
|---|---|---|---|
| Hours 1–2 | Project setup, repo structure, GnuCOBOL source download | Clean repo + raw data | Structure matches spec, `data/raw/gnucobol/` populated |
| Hours 2–4 | COBOL preprocessor: column stripping, encoding, comment separation | `cobol_parser.py` + tests | COBOL files parsed correctly, tests pass |
| Hours 4–7 | COBOL chunker: adaptive paragraph-based (64-768 tokens) | `cobol_chunker.py` + tests | Paragraphs extracted, merge/split logic works |
| Hours 7–9 | Batch embedding module + Qdrant indexer | `embedder.py`, `indexer.py` | All GnuCOBOL chunks embedded and stored in Qdrant |
| Hours 9–11 | Hybrid search + basic re-ranking (metadata-based) | `search.py`, `reranker.py` | Queries return relevant chunks with confidence scores |
| Hours 11–13 | Language-aware prompt template + LLM generation | `prompts.py`, `llm.py` | GPT-4o generates cited answers from retrieved chunks |
| Hours 13–16 | FastAPI backend + basic query endpoint + streaming | `app.py`, `routes.py` | API accepts queries, returns streaming answers |
| Hours 16–18 | CLI interface (basic) OR Jinja2 web template | `cli/main.py` or templates | At least one working interface |
| Hours 18–21 | Deployment: Render (API) + Qdrant Cloud + basic health checks | Deployed app | Public URL works, queries return answers |
| Hours 21–24 | Smoke testing (10 manual queries) + bug fixes + buffer | Stable MVP | All 9 MVP hard gate requirements met |

### MVP Hard Gate Checklist

- [ ] Ingest at least one legacy codebase (GnuCOBOL) — COBOL
- [ ] Chunk code files with syntax-aware splitting (paragraph-based)
- [ ] Generate embeddings for all chunks (Voyage Code 2)
- [ ] Store embeddings in a vector database (Qdrant)
- [ ] Implement semantic search across the codebase (hybrid dense + BM25)
- [ ] Natural language query interface (CLI or web)
- [ ] Return relevant code snippets with file/line references
- [ ] Basic answer generation using retrieved context (GPT-4o)
- [ ] Deployed and publicly accessible

## Phase 3.2 — G4 Final (Days 2–3)

**Goal:** All 5 codebases ingested, all 8 features working, evaluation metrics exceeding targets, architecture doc, cost analysis.

| Time Block | Task | Deliverable | Success Criteria |
|---|---|---|---|
| Day 2 AM (4h) | Fortran preprocessor + chunker (subroutine-based) | `fortran_parser.py`, `fortran_chunker.py` + tests | Fortran files parsed and chunked correctly |
| Day 2 PM (4h) | Ingest remaining 4 codebases (GNU Fortran, LAPACK, BLAS, OpenCOBOL) | All 5 codebases in Qdrant | `legacylens status` shows all 5 indexed |
| Day 2 EVE (3h) | Build evaluation dataset: 15 manual + 35 LLM-generated (across all codebases) | `ground_truth.json`, `evaluate.py` | 50+ query/answer pairs, precision measurable |
| Day 3 AM (4h) | Implement all 8 features (feature router + 8 feature modules) | `src/features/*` | Each feature produces accurate, cited output |
| Day 3 PM (2h) | Cohere re-ranking integration + chunking refinement | Updated `reranker.py`, refined chunkers | Precision@5 > 85% on evaluation set |
| Day 3 PM (2h) | Architecture document + cost analysis document | `docs/architecture.md`, `docs/cost-analysis.md` | Comprehensive with diagrams, real spend, all 4 user tiers |
| Day 3 EVE (2h) | Run full evaluation, measure all metrics, fix regressions | Evaluation results | All performance targets met or documented |

### G4 Final Checklist

- [ ] All 5 codebases ingested and queryable
- [ ] All 8 code understanding features implemented
- [ ] Retrieval precision > 85% in top-5 (measured by eval script)
- [ ] Architecture documentation with decision rationale, diagrams, metrics
- [ ] Cost analysis with real measured spend + projections for 100/1K/10K/100K users
- [ ] 100% codebase file coverage across all 5 codebases
- [ ] Hybrid search (dense + BM25) active
- [ ] Layered re-ranking (metadata + Cohere) active

## Phase 3.3 — GFA Final (Days 4–5)

**Goal:** Polished dual interface (CLI + Web), demo video, social media post, all deliverables maxed.

| Time Block | Task | Deliverable | Success Criteria |
|---|---|---|---|
| Day 4 AM (4h) | Next.js frontend: dashboard + query page + codebase selector + feature picker | `frontend/` complete | Web UI with all features accessible |
| Day 4 PM (4h) | Web UI polish: syntax highlighting, streaming, confidence badges, dark mode | Polished web interface | Professional-grade UI |
| Day 4 EVE (3h) | CLI polish: Rich formatting, all features, JSON output, progress bars | Polished CLI | Professional-grade terminal experience |
| Day 5 AM (4h) | Demo video recording (3-5 min): narrative hook → architecture → live queries across codebases → all 8 features → metrics | `demo-video.mp4` | Compelling demo showing full scope |
| Day 5 PM (2h) | Social media post (X/LinkedIn): description, features, screenshots, demo, tag @GauntletAI | Social post published | Engaging post with visuals |
| Day 5 PM (2h) | Final documentation pass: README polish, architecture doc, submission checklist | All docs finalized | Everything submission-ready |
| Day 5 EVE (2h) | Final regression testing + submission | Submitted | All deliverables submitted before deadline |

### GFA Final Checklist

- [ ] Next.js web interface deployed on Vercel — all features accessible
- [ ] CLI interface fully functional with Rich formatting
- [ ] Demo video (3-5 minutes) — narrative + architecture + live queries + metrics
- [ ] Social media post published on X or LinkedIn
- [ ] Syntax highlighting in both CLI and web
- [ ] Streaming responses in web interface
- [ ] Codebase selector working (query all or filter)
- [ ] Feature picker working (all 8 features selectable)
- [ ] Comprehensive README with setup guide, architecture overview, deployed links
- [ ] All performance targets met or exceeded

---

# Phase 4: Implementation Tickets

## Sprint 1: MVP Tickets (Day 1)

| Ticket | Title | Description | Estimate | Dependencies |
|---|---|---|---|---|
| MVP-001 | Project scaffolding + repo structure | Create full directory structure per expanded spec | 1h | None |
| MVP-002 | Download GnuCOBOL source | Clone/download GnuCOBOL source to `data/raw/gnucobol/` | 0.5h | MVP-001 |
| MVP-003 | Language detector module | File extension-based detection dispatching to COBOL/Fortran handlers | 0.5h | MVP-001 |
| MVP-004 | COBOL preprocessor | Column stripping (1-6, 73-80), encoding detection, comment separation | 2h | MVP-002 |
| MVP-005 | COBOL paragraph chunker | Adaptive paragraph-based chunking (64-768 tokens) with merge/split | 2.5h | MVP-004 |
| MVP-006 | Metadata extraction | Extract file_path, lines, paragraph_name, division, chunk_type, language, codebase | 1h | MVP-005 |
| MVP-007 | Batch embedding module | Voyage Code 2 integration, 128 texts/call, 1536 dims, with retry + caching | 1.5h | MVP-006 |
| MVP-008 | Qdrant indexer | Collection creation, payload schema, batch upsert with metadata | 1.5h | MVP-007 |
| MVP-009 | Hybrid search module | Dense vector similarity + BM25 sparse via Qdrant native | 1.5h | MVP-008 |
| MVP-010 | Metadata-based re-ranker | Paragraph name boost, division routing, confidence scores | 1h | MVP-009 |
| MVP-011 | COBOL-aware prompt template | Structured system prompt with citation instructions and confidence | 1h | None |
| MVP-012 | LLM generation module | GPT-4o integration with streaming support + GPT-4o-mini fallback | 1.5h | MVP-011 |
| MVP-013 | FastAPI backend + query endpoint | API with `/api/query`, `/api/query/stream`, `/api/health` | 2h | MVP-009, MVP-012 |
| MVP-014 | Basic CLI interface | Click + Rich: `legacylens query "..."` with formatted output | 1.5h | MVP-013 |
| MVP-015 | Render deployment | Dockerfile, render.yaml, env vars, Qdrant Cloud setup | 2h | MVP-013 |
| MVP-016 | End-to-end smoke test | 10 manual queries on deployed app across different query types | 1h | MVP-015 |

## Sprint 2: G4 Final Tickets (Days 2–3)

| Ticket | Title | Description | Estimate | Dependencies |
|---|---|---|---|---|
| G4-001 | Fortran preprocessor | Fixed/free form detection, comment extraction, continuation handling | 2.5h | MVP-016 |
| G4-002 | Fortran subroutine chunker | SUBROUTINE/FUNCTION boundary detection, adaptive sizing | 2.5h | G4-001 |
| G4-003 | Ingest GNU Fortran | Download + preprocess + chunk + embed + store | 1.5h | G4-002 |
| G4-004 | Ingest LAPACK | Download + preprocess + chunk + embed + store | 1.5h | G4-002 |
| G4-005 | Ingest BLAS | Download + preprocess + chunk + embed + store | 1h | G4-002 |
| G4-006 | Ingest OpenCOBOL Contrib | Download + preprocess + chunk + embed + store | 1h | MVP-016 |
| G4-007 | Multi-codebase query support | Add `codebase` filter to search, default to "all" | 1.5h | G4-006 |
| G4-008 | Ground truth evaluation dataset | 15 manual + 35 LLM-generated across all 5 codebases (50+ pairs) | 2.5h | G4-007 |
| G4-009 | Evaluation script | Run queries, compute precision@5, per-codebase and overall | 1.5h | G4-008 |
| G4-010 | Feature: Code Explanation | Dedicated prompt + endpoint + CLI command | 1h | G4-007 |
| G4-011 | Feature: Dependency Mapping | PERFORM/CALL chain extraction + visualization | 1.5h | G4-010 |
| G4-012 | Feature: Pattern Detection | Embedding similarity clustering + grouping output | 2h | G4-010 |
| G4-013 | Feature: Impact Analysis | Reverse dependency lookup + affected module tracing | 2h | G4-011 |
| G4-014 | Feature: Documentation Gen | Hierarchical context + doc template prompt | 1h | G4-010 |
| G4-015 | Feature: Translation Hints | Language-specific prompt with Python/Java equivalents | 1.5h | G4-010 |
| G4-016 | Feature: Bug Pattern Search | Anti-pattern knowledge base + BM25 keyword search | 1.5h | G4-010 |
| G4-017 | Feature: Business Logic Extract | PROCEDURE DIVISION focus + conditional logic detection | 1.5h | G4-010 |
| G4-018 | Feature router + unified API | `/api/query` accepts `feature` param, routes to correct handler | 1h | G4-010 through G4-017 |
| G4-019 | Cohere re-ranking integration | Cross-encoder re-ranking on top of metadata layer | 1.5h | G4-009 |
| G4-020 | Architecture document | System design, decisions, diagrams, metrics, failure modes | 2h | G4-009 |
| G4-021 | Cost analysis document | Real API spend + projections for 100/1K/10K/100K users | 2h | G4-020 |
| G4-022 | Full evaluation run + regression fix | Run eval script, fix any precision regressions, document results | 1.5h | G4-019 |

## Sprint 3: GFA Final Tickets (Days 4–5)

| Ticket | Title | Description | Estimate | Dependencies |
|---|---|---|---|---|
| GFA-001 | Next.js project setup | Create `frontend/` with Next.js 14 + Tailwind + app router | 1.5h | G4-022 |
| GFA-002 | Dashboard page | Codebase overview cards, ingestion status, recent queries | 2h | GFA-001 |
| GFA-003 | Query page | Query input, codebase selector, feature picker, streaming results | 3h | GFA-001 |
| GFA-004 | CodeBlock component | Syntax-highlighted code with line numbers, file path, copy button | 1.5h | GFA-001 |
| GFA-005 | Result detail page | Full result view with all citations, confidence, expandable context | 2h | GFA-003 |
| GFA-006 | Codebase explorer page | Browse files per codebase, click to view chunks | 2h | GFA-001 |
| GFA-007 | UI polish: dark mode, responsive, streaming animation | Visual polish pass | 2h | GFA-002 through GFA-006 |
| GFA-008 | CLI polish | Rich formatting for all 8 features, JSON mode, progress bars, status command | 2h | G4-018 |
| GFA-009 | Vercel deployment | Deploy frontend, configure API proxy, test end-to-end | 1.5h | GFA-007 |
| GFA-010 | Cron keepalive | UptimeRobot or GitHub Action pinging Render every 14 min to prevent spin-down | 0.5h | GFA-009 |
| GFA-011 | Confidence score calibration | Calibrate HIGH/MED/LOW thresholds using ground truth results | 1h | G4-022 |
| GFA-012 | Embedding cache | LRU cache for repeated query embeddings | 0.5h | G4-019 |
| GFA-013 | Demo video recording | 3.5 min: narrative hook → architecture → live queries (all codebases, all features) → metrics | 2h | GFA-009 |
| GFA-014 | Social media post | LinkedIn/X post: description, features, screenshots, tag @GauntletAI | 1h | GFA-013 |
| GFA-015 | Final documentation pass | README, architecture doc polish, submission checklist verification | 2h | GFA-014 |
| GFA-016 | Final regression testing + submission | Full eval run + manual testing + submit | 1.5h | GFA-015 |

---

# Phase 5: Test-Driven Development Strategy

## Testing Philosophy

The RAG pipeline has a unique testing challenge: the LLM output is non-deterministic, but the intermediate steps (chunking, retrieval, re-ranking) are deterministic and measurable. TDD applies to deterministic components; evaluation testing covers the full pipeline. With 5 codebases and 8 features, test coverage is critical.

## Unit Tests (pytest)

### test_detector.py — Language Detection
- Test `.cob` → COBOL, `.cbl` → COBOL, `.cpy` → COBOL
- Test `.f` → Fortran, `.f90` → Fortran, `.f77` → Fortran
- Test unknown extension → raises `UnsupportedLanguageError`

### test_cobol_parser.py — COBOL Preprocessing
- Test column stripping removes columns 1-6 and 73-80
- Test encoding detection correctly identifies EBCDIC vs UTF-8
- Test comment separation extracts comment lines (col 7 = *) into metadata
- Test processed output contains only columns 8-72 content
- Test continuation lines (col 7 = -) are handled correctly

### test_fortran_parser.py — Fortran Preprocessing
- Test fixed-form detection (statements start at col 7+)
- Test free-form detection (no column restrictions)
- Test comment extraction: `C`/`c`/`*` in col 1 (fixed), `!` anywhere (free)
- Test continuation handling: col 6 non-blank (fixed), `&` at end (free)
- Test encoding detection for legacy Fortran files

### test_cobol_chunker.py — COBOL Chunking
- Test paragraph detection finds COBOL paragraph headers
- Test chunk boundaries never split mid-paragraph
- Test chunks under 64 tokens are merged with predecessors
- Test chunks over 768 tokens are split at COBOL sentence boundaries (periods)
- Test metadata: paragraph_name, division, line numbers correct
- Test hierarchical context: file → division → section → paragraph

### test_fortran_chunker.py — Fortran Chunking
- Test SUBROUTINE boundary detection
- Test FUNCTION boundary detection
- Test PROGRAM boundary detection
- Test MODULE boundary detection (Fortran 90+)
- Test chunks respect subroutine start/end
- Test merge logic for small helper routines
- Test metadata: subroutine_name, module, line numbers correct

### test_retrieval.py — Search & Re-ranking
- Test indexing N chunks results in N vectors in Qdrant
- Test basic similarity search returns results for known queries
- Test hybrid search (dense + BM25) returns better results than dense-only
- Test metadata filtering by codebase works
- Test metadata filtering by language works
- Test metadata filtering by division (PROCEDURE vs DATA) works
- Test confidence score normalization maps to HIGH/MEDIUM/LOW correctly
- Test Cohere re-ranking improves precision over metadata-only

### test_features.py — All 8 Features
- Test Code Explanation returns plain English + citations
- Test Dependency Mapping returns call chain
- Test Pattern Detection returns grouped similar code
- Test Impact Analysis returns affected modules
- Test Documentation Gen returns formatted documentation
- Test Translation Hints returns modern language suggestions with caveats
- Test Bug Pattern Search returns potential issues with severity
- Test Business Logic Extract returns business rules in plain English

### test_api.py — FastAPI Endpoints
- Test `POST /api/query` returns valid response with citations
- Test `POST /api/query` with `codebase` filter returns filtered results
- Test `POST /api/query` with `feature` param routes to correct handler
- Test `POST /api/query/stream` returns SSE stream
- Test `GET /api/codebases` returns all 5 codebases with status
- Test `GET /api/health` returns 200

### test_cli.py — CLI Interface
- Test `legacylens query "..."` returns formatted output
- Test `legacylens query --codebase gnucobol` filters correctly
- Test `legacylens query --feature business-logic` routes correctly
- Test `legacylens query --json` returns valid JSON
- Test `legacylens status` shows all codebase statuses
- Test `legacylens evaluate` runs evaluation script

## Evaluation Testing (evaluate.py)

### Ground Truth Dataset Structure

```json
{
  "queries": [
    {
      "query": "What does CALCULATE-INTEREST do?",
      "expected_chunks": ["gnucobol/src/calc-interest.cob:45-89"],
      "codebase": "gnucobol",
      "category": "code_explanation",
      "language": "cobol"
    },
    {
      "query": "Show me the DGEMM subroutine",
      "expected_chunks": ["blas/src/dgemm.f:1-200"],
      "codebase": "blas",
      "category": "code_explanation",
      "language": "fortran"
    }
  ]
}
```

### 15 Manual Queries (across all codebases and features)

1. "What is the main entry point of the GnuCOBOL program?" (Code Explanation, COBOL)
2. "Explain what the CALCULATE-INTEREST paragraph does" (Code Explanation, COBOL)
3. "What functions modify CUSTOMER-RECORD?" (Dependency Mapping, COBOL)
4. "Show me all error handling routines in GnuCOBOL" (Pattern Detection, COBOL)
5. "What data structures are defined in the DATA DIVISION?" (Code Explanation, COBOL)
6. "What does the DGEMM subroutine compute?" (Code Explanation, Fortran/BLAS)
7. "Show me all matrix decomposition routines in LAPACK" (Pattern Detection, Fortran)
8. "What are the dependencies of ZHEEV?" (Dependency Mapping, Fortran/LAPACK)
9. "Find all file I/O operations in GnuCOBOL" (Business Logic, COBOL)
10. "What would break if I changed the CUSTOMER-RECORD layout?" (Impact Analysis, COBOL)
11. "Generate documentation for the DGESV subroutine" (Documentation Gen, Fortran/LAPACK)
12. "Suggest Python equivalents for CALCULATE-INTEREST" (Translation Hints, COBOL)
13. "Find potential bugs in the OpenCOBOL sample programs" (Bug Pattern Search, COBOL)
14. "What are the business rules for loan eligibility?" (Business Logic, COBOL)
15. "What does a nonexistent function XYZZY do?" (Zero-result Edge Case)

### Evaluation Metrics

```
python evaluate.py --dataset evaluation/ground_truth.json

Output:
  Overall Precision@5: 87.3% (44/50 queries with majority relevant chunks)

  Per Codebase:
    gnucobol:          89.2% (33/37)
    lapack:            83.3% (5/6)
    blas:              100%  (3/3)
    gfortran:          80.0% (2/3)
    opencobol-contrib: 100%  (1/1)

  Per Feature:
    Code Explanation:     91.7%
    Dependency Mapping:   83.3%
    Pattern Detection:    80.0%
    Impact Analysis:      75.0%
    Documentation Gen:    100%
    Translation Hints:    83.3%
    Bug Pattern Search:   80.0%
    Business Logic:       91.7%

  Latency:
    P50: 1.2s
    P95: 2.8s
    P99: 3.5s
```

## Testing Schedule

| Phase | Test Type | When | Pass Criteria |
|---|---|---|---|
| MVP | Unit tests for COBOL parser + chunker | Hours 2-7 | All assertions pass |
| MVP | Smoke test: 10 manual queries | Hours 21-24 | Answers returned with citations |
| G4 | Unit tests for Fortran parser + chunker | Day 2 AM | All assertions pass |
| G4 | Full evaluation script (all codebases) | Day 2 EVE | Precision@5 > 70% (baseline) |
| G4 | Feature tests for all 8 features | Day 3 AM | All features produce valid output |
| G4 | Post-refinement evaluation | Day 3 PM | Precision@5 > 85% (target) |
| GFA | API endpoint tests | Day 4 AM | All endpoints return valid responses |
| GFA | CLI tests | Day 4 EVE | All CLI commands work |
| GFA | Final evaluation + regression | Day 5 AM | Precision@5 maintained or improved |

---

# Phase 6: Language-Specific Technical Reference

## COBOL Source Structure

| Columns | Name | Purpose |
|---|---|---|
| 1–6 | Sequence Number | Line numbering (strip during preprocessing) |
| 7 | Indicator | `*` = comment, `-` = continuation, `D` = debug |
| 8–72 | Code Area | Actual COBOL code (Area A: 8-11, Area B: 12-72) |
| 73–80 | Identification | Program ID (strip during preprocessing) |

### COBOL Division Hierarchy
- **IDENTIFICATION DIVISION** — Program metadata (name, author, date)
- **ENVIRONMENT DIVISION** — System configuration (files, I/O)
- **DATA DIVISION** — Variable and record definitions (WORKING-STORAGE, FILE SECTION)
- **PROCEDURE DIVISION** — Business logic (paragraphs, sections, PERFORM statements)

### COBOL Chunking Strategy
- Primary unit: paragraph (the closest equivalent to a "function")
- Adaptive sizing: 64-768 tokens
- Merge paragraphs under 64 tokens with predecessor
- Split paragraphs over 768 tokens at COBOL sentence boundaries (periods)
- Preserve paragraph name as primary metadata for keyword search
- Track PERFORM targets as dependency metadata

### COPY Statement Handling
- **MVP:** Index copybooks (.cpy files) as separate chunks. Rely on retrieval to connect them.
- **Final:** Parse COPY statements during preprocessing, store references as metadata. Expand context with linked copybook chunks at query time.

## Fortran Source Structure

### Fixed-Form (Fortran 77)
| Columns | Purpose |
|---|---|
| 1 | `C`, `c`, `*` = comment line |
| 1-5 | Statement label |
| 6 | Non-blank = continuation |
| 7-72 | Code |

### Free-Form (Fortran 90+)
- No column restrictions
- `!` starts a comment
- `&` at end of line = continuation
- Statements can start anywhere

### Fortran Chunking Strategy
- Primary unit: SUBROUTINE / FUNCTION / PROGRAM / MODULE block
- Detect boundaries via `SUBROUTINE name(...)` and `END SUBROUTINE` patterns
- Adaptive sizing: 64-768 tokens
- Fortran subroutines tend to be self-contained → natural chunk boundaries
- Track CALL targets as dependency metadata
- For LAPACK: mathematical subroutine names (DGEMM, ZHEEV) need keyword-searchable metadata since embeddings struggle with opaque identifiers

## Language-Aware Prompt Template

```
SYSTEM: You are a legacy code analysis expert helping developers understand
enterprise codebases written in {language}.

{language_specific_context}

Always cite specific file paths and line numbers. If the retrieved context
doesn't contain enough information to answer, say so explicitly.

CONTEXT FORMAT:
Each chunk includes: file path, line range, structural hierarchy, the code.

{retrieved_chunks_with_metadata}

FEATURE: {feature_name}
USER QUERY: {query}

INSTRUCTIONS:
1. Answer based ONLY on the provided code context
2. Cite specific file:line references for every claim
3. If context is insufficient, state what's missing
4. Explain language-specific constructs in plain English
5. Structure: Summary → Detail → References
6. Include confidence level: HIGH / MEDIUM / LOW
```

**COBOL-specific context insert:**
```
You understand COBOL's structure: IDENTIFICATION, ENVIRONMENT, DATA, and
PROCEDURE divisions. Paragraphs are execution units. PERFORM transfers
control. 88-level items are condition names. COPY statements pull in
shared definitions from copybooks.
```

**Fortran-specific context insert:**
```
You understand Fortran's structure: PROGRAM, MODULE, SUBROUTINE, and
FUNCTION blocks. CALL transfers control to subroutines. COMMON blocks
share data between routines. IMPLICIT NONE enforces explicit typing.
You recognize both fixed-form (F77) and free-form (F90+) syntax.
```

---

# Phase 7: Cost Analysis Framework

## Development & Testing Costs (Real Measured)

Track actual spend during development via API dashboards:

| Cost Category | API | Metric to Track | Estimated Sprint Cost |
|---|---|---|---|
| Embedding (ingestion) | Voyage Code 2 | Total tokens embedded across all 5 codebases | $5–$10 |
| Embedding (queries) | Voyage Code 2 | Tokens per query × development queries | $1–$3 |
| LLM generation | OpenAI GPT-4o | Input + output tokens for answer generation | $10–$30 |
| LLM fallback | OpenAI GPT-4o-mini | Tokens for budget-mode queries | $1–$5 |
| Re-ranking | Cohere Rerank | Documents re-ranked per query | $0–$3 |
| Vector DB | Qdrant Cloud | Storage used (free tier 1GB) | $0 |
| Hosting (API) | Render | Free tier hours used | $0 |
| Hosting (Web) | Vercel | Free tier bandwidth | $0 |
| **Total Sprint** | | | **$17–$51** |

## Production Cost Projections

### Assumptions
- Queries per user per day: 10
- Average input tokens per query: 2,000 (chunks) + 500 (prompt) = 2,500
- Average output tokens per query: 500
- Embedding per query: 1 × 100 tokens = negligible
- Re-ranking per query: 10 documents = 1 API call
- Vector DB: grows with codebases, not users

### Monthly Cost at Scale

| Component | 100 Users | 1,000 Users | 10,000 Users | 100,000 Users |
|---|---|---|---|---|
| LLM (GPT-4o) | $75/mo | $750/mo | $7,500/mo | $37,500/mo* |
| LLM (GPT-4o-mini fallback) | $5/mo | $50/mo | $500/mo | $2,500/mo* |
| Embedding (queries) | $0.50/mo | $5/mo | $50/mo | $500/mo |
| Re-ranking (Cohere) | $3/mo | $30/mo | $300/mo | $3,000/mo |
| Vector DB (Qdrant) | $0 (free) | $25/mo | $100/mo | $500/mo |
| Hosting (API) | $7/mo | $25/mo | $150/mo | $800/mo |
| Hosting (Web) | $0 (free) | $20/mo | $100/mo | $500/mo |
| **Total** | **$90/mo** | **$905/mo** | **$8,700/mo** | **$45,300/mo** |

*At 100K users, route 80% of queries to GPT-4o-mini to reduce costs to ~$12,500/mo for LLM.

### Cost Optimization Strategies
- Route simple queries (Code Explanation, Documentation Gen) to GPT-4o-mini
- Cache frequent queries + responses (Redis/LRU)
- Reduce re-ranking to metadata-only for cost-sensitive tiers
- Batch embedding cache eliminates repeat embedding costs
- Consider self-hosted Qdrant at 10K+ users ($100/mo vs $500/mo managed)

---

# Phase 8: Interview Preparation

This week includes behavioral and technical interviews required for Austin admission.

## Technical Topics — Mapped to Build Decisions

| Interview Topic | Your Story (from this build) |
|---|---|
| Why you chose your vector database | "Qdrant for native hybrid search. Dense embeddings miss exact COBOL identifiers like CALCULATE-INTEREST. BM25 catches those. The precision improvement was 15+ percentage points." |
| Chunking strategy tradeoffs | "Started with paragraph-based for COBOL, subroutine-based for Fortran. Had to handle edge cases: tiny paragraphs (merge), huge subroutines (split). The adaptive 64-768 token range respects structural boundaries while keeping embeddings discriminative." |
| Embedding model selection rationale | "Voyage Code 2 because it's trained on code. General-purpose models treat COBOL as text and miss structural cues. The 1536 dimensions are a sweet spot for our ~850K LOC corpus." |
| How you handle retrieval failures | "Four-tier degradation: HIGH results → show normally, MEDIUM → partial match indicator, LOW → keyword fallback, NONE → helpful suggestions with indexed paragraph names." |
| Performance optimization decisions | "Streaming transforms 3-second waits into 500ms first-token. Embedding cache eliminates redundant API calls. Batch ingestion (128 texts/call) cut indexing from 5 minutes to 30 seconds." |
| Multi-codebase architecture | "Unified Qdrant collection with `codebase` and `language` metadata fields. Language-specific preprocessors and chunkers dispatched by file extension. Users can query all or filter." |

## Behavioral Topics — Decision Log

Keep a decision log during the build. Every non-obvious choice, wall hit, or direction change gets a one-line note:

| Behavioral Topic | Example Story |
|---|---|
| Handling ambiguity | "Choosing between Qdrant and Pinecone when I hadn't used either. Ran a 30-minute spike comparing APIs. Qdrant's native hybrid search was the deciding factor." |
| Pivoting on failure | "My first chunking strategy (fixed-size) produced 45% precision. Rebuilt with paragraph-based chunking in 3 hours. Precision jumped to 78%." |
| Self-learning | "Had to learn COBOL structure from scratch — divisions, sections, paragraphs, COPY statements. Built a mental model in 2 hours from GnuCOBOL source, then coded the parser." |
| Pressure management | "At hour 18 without a deployed app. Dropped the re-ranking feature, deployed basic search, then added re-ranking after MVP was live." |
| Scope management | "Chose to implement all 8 features because the synergy meant each additional feature was ~1 hour, not ~4 hours. The shared retrieval pipeline made it efficient." |

## Demo Video Script (3.5 minutes)

1. **Narrative hook (15s):** "Imagine joining a bank that runs on 40-year-old COBOL and 30-year-old Fortran. Millions of lines, zero documentation. LegacyLens makes it queryable."
2. **Architecture diagram (30s):** Show the pipeline: 5 codebases → preprocessing → chunking → embedding → Qdrant → hybrid search → re-rank → GPT-4o → answer.
3. **Live query — Code Explanation (45s):** "What does CALCULATE-INTEREST do?" → Show streaming answer with citations, confidence badge.
4. **Live query — Cross-codebase (30s):** "Show me all matrix operations" → Results from LAPACK + BLAS.
5. **Live query — Business Logic (30s):** "What are the business rules for customer validation?" → Business rules in plain English.
6. **Feature showcase (30s):** Quick cuts of Dependency Mapping, Bug Pattern Search, Translation Hints.
7. **CLI demo (15s):** Show same query in terminal with Rich formatting.
8. **Metrics (15s):** "87% precision@5, 1.2s median latency, 5 codebases, 8 features, 850K+ lines of code."

---

# Appendix A: Master Decision Reference (30 Recommendations)

Complete reference from the 3-round architecture interview. Updated for maximalist scope.

## Round 1 — Foundation

| # | Decision | Recommendation | Maximalist Update |
|---|---|---|---|
| 1 | Target Codebase | GnuCOBOL | All 5 codebases (GnuCOBOL + Fortran + LAPACK + BLAS + OpenCOBOL) |
| 2 | Vector Database | Qdrant (hybrid search) | Same — payload filtering for multi-codebase support |
| 3 | Embedding Model | Voyage Code 2 | Same — works for both COBOL and Fortran |
| 4 | Chunking Strategy | Hierarchical (phased) | Language-specific: paragraph (COBOL) + subroutine (Fortran) |
| 5 | RAG Framework | Custom pipeline | Same — full control across both languages |
| 6 | LLM for Generation | GPT-4o + mini fallback | Same — language-aware prompts per codebase |
| 7 | Query Processing | Hybrid + keyword extraction | Same — critical for opaque Fortran identifiers (DGEMM) |
| 8 | Deployment | Render + Qdrant Cloud | Render (API) + Vercel (Next.js frontend) + Qdrant Cloud |
| 9 | Code Features | 4 features | ALL 8 features |
| 10 | Re-ranking | Metadata → cross-encoder | Same — metadata boost per language + Cohere |

## Round 2 — Implementation

| # | Decision | Recommendation | Maximalist Update |
|---|---|---|---|
| 11 | Prompt Template | Structured COBOL-aware | Language-aware: switchable COBOL/Fortran context inserts |
| 12 | Preprocessing | Column strip + comments + encoding | COBOL + Fortran preprocessors with fixed/free form detection |
| 13 | Context Window | Dynamic budget + expand top-1 | Same — works across all codebases |
| 14 | Evaluation Dataset | Hybrid: 10 manual + 20 LLM | Expanded: 15 manual + 35 LLM = 50+ across all codebases |
| 15 | Metadata | File+lines+paragraph+division | Add `language` + `codebase` fields for filtering |
| 16 | Chunk Size | Adaptive 64-768 tokens | Same — applied per-language with structural boundaries |
| 17 | Confidence Scores | Normalized thresholds | Same |
| 18 | Ingestion Pipeline | Batch embed + concurrent upsert | Same — run per codebase with progress tracking |
| 19 | Query Interface | FastAPI+Jinja2 → Next.js | Both CLI (Click+Rich) AND Web (Next.js) from the start |
| 20 | Cost Analysis | Detailed with real spend | All 4 tiers: 100/1K/10K/100K users |

## Round 3 — Production & Meta

| # | Decision | Recommendation | Maximalist Update |
|---|---|---|---|
| 21 | Zero-result Handling | Tiered degradation | Same |
| 22 | Cross-file Queries | Top-k → metadata-filtered | Extends to cross-codebase queries with `codebase` filter |
| 23 | COPY Statements | Index separately → metadata linking | Same for COBOL; Fortran INCLUDE handled similarly |
| 24 | Testing Strategy | Eval script + manual testing | Expanded test suite covering all 5 codebases + all 8 features |
| 25 | Latency Optimization | Streaming + embedding cache | Same |
| 26 | Repo Structure | Clean modular | Expanded with `features/`, `cli/`, `frontend/` |
| 27 | Interview Prep | Decision log → STAR stories | Same — more stories from multi-codebase challenges |
| 28 | Time Allocation | Structured sprint + retros | Adjusted for expanded scope (see Phase 3) |
| 29 | Demo Video | Narrative + arch + live + metrics | Demo spans all codebases + all features + both interfaces |
| 30 | Most Important Thing | Chunking quality | Same — foundation of everything, now for two languages |

---

# Appendix B: Complete Submission Checklist

## Deliverables (All Required)

| Deliverable | Requirements | Status |
|---|---|---|
| GitHub Repository | Setup guide, architecture overview, deployed link | [ ] |
| Demo Video (3-5 min) | Show queries, retrieval results, answer generation across codebases | [ ] |
| Pre-Search Document | Completed checklist from Phase 1-3 | [ ] |
| RAG Architecture Doc | 1-2 page breakdown: VectorDB, Embedding, Chunking, Retrieval, Failure Modes, Performance | [ ] |
| AI Cost Analysis | Dev spend + projections for 100/1K/10K/100K users | [ ] |
| Deployed Application | Publicly accessible query interface (Web + CLI documented) | [ ] |
| Social Post | Share on X or LinkedIn: description, features, demo/screenshots, tag @GauntletAI | [ ] |

## MVP Hard Gate (Day 1) — All Required to Pass

- [ ] Ingest at least one legacy codebase (GnuCOBOL)
- [ ] Chunk code files with syntax-aware splitting
- [ ] Generate embeddings for all chunks
- [ ] Store embeddings in vector database
- [ ] Implement semantic search across codebase
- [ ] Natural language query interface (CLI or Web)
- [ ] Return relevant code snippets with file/line references
- [ ] Basic answer generation using retrieved context
- [ ] Deployed and publicly accessible

## Maximalist Targets (Beyond Minimum)

- [ ] All 5 codebases ingested and queryable
- [ ] All 8 code understanding features implemented
- [ ] Both CLI and Web interfaces fully functional
- [ ] Retrieval precision > 85% in top-5
- [ ] Streaming responses for perceived <1.5s latency
- [ ] Hybrid search (dense + BM25) active
- [ ] Layered re-ranking (metadata + Cohere) active
- [ ] Cost analysis covering all 4 user tiers (100/1K/10K/100K)
- [ ] Comprehensive architecture doc with diagrams and metrics
- [ ] Narrative-driven demo video showcasing full scope
- [ ] Next.js frontend with syntax highlighting, dark mode, codebase selector
- [ ] CLI with Rich formatting, JSON mode, all features accessible
- [ ] Confidence score calibration using ground truth
- [ ] Embedding cache for query optimization
- [ ] Cron keepalive preventing Render spin-down
- [ ] Decision log maintained throughout sprint for interview prep

---

*"A simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results — but a comprehensive RAG pipeline with accurate retrieval across five codebases and eight features? That's how you max out the assignment."*
