# LegacyLens (Maximalist) — Senior Full-Stack Engineer Interview Guide

## 30 Questions · 90 Evaluated Answers · 30 Final Recommendations

### RAG Systems for Legacy Enterprise Codebases — All 5 Codebases, All 8 Features, Dual Interface

---

> **The Meta-Principle:** Every recommendation follows one rule — **ship the most complete, highest-quality system possible within the time constraint.** "Maximalist" doesn't mean "reckless" — it means making every hour count across all 5 codebases, all 8 features, and both interfaces without sacrificing retrieval quality.

---

# ROUND 1 OF 3: Foundation & Multi-Codebase Architecture

---

## Q1: Multi-codebase ingestion — should you use one shared Qdrant collection with metadata filtering, or separate collections per codebase?

This is the foundational architectural decision for the maximalist approach. It affects every downstream component: search, filtering, re-ranking, context assembly, and storage costs.

### Answer A: Single shared collection with `codebase` and `language` metadata fields

**Pros:** One collection means one search call regardless of whether the user queries "all" or a specific codebase — just add a metadata filter for codebase-specific queries. Simplifies the indexer (one upsert target), the search module (one search function), and deployment (one Qdrant collection to manage). Cross-codebase queries ("show me all error handling patterns") work natively because all vectors live in the same space. Storage is unified — Qdrant's free tier 1GB covers everything. Re-ranking works identically regardless of codebase count. Adding a 6th codebase later is just another ingestion run with a new `codebase` tag.

**Cons:** The embedding space gets crowded — 850K+ LOC means ~50K+ chunks sharing one vector space. COBOL and Fortran have fundamentally different syntax, so their embeddings may cluster separately, potentially causing cross-language noise in "query all" mode. Payload filtering adds ~5-10ms per query. If the collection gets corrupted, you lose everything. No per-codebase index optimization.

### Answer B: Separate collection per codebase (5 collections)

**Pros:** Complete isolation — a bug in LAPACK ingestion never affects GnuCOBOL. Per-collection optimization: COBOL collections can have different HNSW parameters than Fortran collections. Easier to re-index a single codebase without touching others. Cleaner mental model: `qdrant.search(collection="gnucobol", ...)`.

**Cons:** "Query all codebases" requires 5 separate search calls + result merging + re-ranking across collections. This adds 200-500ms latency and significant code complexity (fan-out search, score normalization across collections, merged re-ranking). 5 collections consume more overhead than 1 on Qdrant's free tier. The search module becomes 3x more complex. Every new codebase requires creating a new collection, updating the fan-out logic, and testing the merge behavior. This is the kind of complexity that creates bugs at 2am on Day 1.

### Answer C: Hybrid — shared collection with per-language namespaces

**Pros:** Qdrant doesn't natively support namespaces, but you can simulate them with a compound payload: `{codebase: "gnucobol", language: "cobol"}` and use Qdrant's indexed payload fields for fast filtering. This gets you the simplicity of a single collection with logical separation via indexed metadata. You can create payload indexes on `codebase` and `language` for O(1) filter lookups. Cross-codebase queries just skip the filter. Single-codebase queries use the filter. Best of both worlds.

**Cons:** Technically identical to Answer A — the "namespace" is just a metadata field with an index. The distinction is cosmetic. You're adding conceptual overhead for no real architectural benefit.

### ✅ RECOMMENDATION: Answer A — Single shared collection with indexed metadata fields

Answer C is Answer A with extra naming. The real decision is A vs B, and it's not close. The fan-out complexity of 5 separate collections will cost you 4-6 hours of engineering time (search merging, score normalization, collection management) with zero retrieval quality benefit. A single collection with payload indexes on `codebase` and `language` gives you O(1) filtering with one search call. The embedding space "crowding" concern is theoretical — at 50K chunks with 1536 dimensions, the space is astronomically sparse. Cross-codebase queries just work. Ship the simpler architecture.

---

## Q2: Language-specific preprocessing — how do you architect the preprocessor to handle both COBOL and Fortran without creating a maintenance nightmare?

You need two fundamentally different preprocessors (COBOL's column-based format vs Fortran's fixed/free form), but they share common patterns (encoding detection, comment extraction, output normalization). Getting this abstraction right determines whether adding the 4 non-COBOL codebases takes 4 hours or 12.

### Answer A: Monolithic preprocessor with language-specific branches

```python
def preprocess(file_path: str) -> ProcessedFile:
    lang = detect_language(file_path)
    if lang == "cobol":
        # strip cols 1-6 and 73-80, handle COPY...
    elif lang == "fortran":
        # detect fixed vs free form, handle continuations...
```

**Pros:** Fastest to implement. No abstraction overhead. One file to read, one function to debug. For a 5-day sprint, "works" beats "elegant."

**Cons:** The function becomes 200+ lines with deeply nested branches. Adding a third language (e.g., PL/I) means more branches in an already complex function. Testing is messy — you can't test COBOL logic in isolation from the dispatch logic. If the Fortran branch has a bug, it could theoretically affect COBOL processing through shared state.

### Answer B: Strategy pattern — abstract base preprocessor with language-specific implementations

```python
class BasePreprocessor(ABC):
    def preprocess(self, content: str) -> ProcessedFile:
        content = self.detect_encoding(content)    # shared
        comments = self.extract_comments(content)   # shared interface
        code = self.strip_formatting(content)        # language-specific
        return ProcessedFile(code=code, comments=comments, metadata={})

    @abstractmethod
    def strip_formatting(self, content: str) -> str: ...
    @abstractmethod
    def extract_comments(self, content: str) -> list[str]: ...

class COBOLPreprocessor(BasePreprocessor): ...
class FortranPreprocessor(BasePreprocessor): ...
```

**Pros:** Clean separation. Each language preprocessor is testable in isolation. The shared base handles encoding detection (chardet), which is identical across languages. Adding a new language is "create a new class, implement 2 methods." The strategy pattern is the textbook solution here, and in an interview, saying "I used the strategy pattern for language dispatch" signals engineering maturity. Code stays under 80 lines per file.

**Cons:** 3 files instead of 1 (base + cobol + fortran). The abstraction has a learning curve for the AI agent — Cursor might fight the pattern. Slight over-engineering for 2 languages.

### Answer C: Functional approach — language-specific functions with a dispatcher

```python
def preprocess(file_path: str) -> ProcessedFile:
    lang = detect_language(file_path)
    preprocessors = {"cobol": preprocess_cobol, "fortran": preprocess_fortran}
    return preprocessors[lang](file_path)
```

**Pros:** No classes, no inheritance, no abstract methods. Just functions. Each `preprocess_cobol` and `preprocess_fortran` is a standalone function. Dead simple dispatch via dictionary lookup. Pythonic. Easy for the AI agent to generate. Each function is independently testable.

**Cons:** Shared logic (encoding detection) gets duplicated or requires a separate utility module. No enforced contract — nothing prevents `preprocess_fortran` from returning a different shape than `preprocess_cobol`. Less interview-impressive than the strategy pattern.

### ✅ RECOMMENDATION: Answer C — Functional approach with a shared utilities module

For a 5-day sprint, the functional approach wins on velocity. Create three files: `cobol_parser.py`, `fortran_parser.py`, and `parser_utils.py` (shared encoding detection, output normalization). The dictionary dispatch is a one-liner. Each parser function is independently testable. The "no enforced contract" concern is solved by a shared `ProcessedFile` dataclass that both functions return. In the interview, frame it as "I chose composition over inheritance because the two languages share encoding detection but nothing else — inheritance would force artificial commonality." That's a more sophisticated answer than "I used the strategy pattern."

---

## Q3: Fortran has fixed-form (F77) and free-form (F90+) syntax, and your 4 Fortran codebases mix both. How do you handle this dual-format problem?

LAPACK is primarily fixed-form F77. gfortran source mixes both. BLAS is fixed-form. This isn't a minor edge case — it affects how you detect comments, continuations, and statement boundaries for chunking.

### Answer A: Auto-detect per file based on heuristics

**Pros:** Check column 1 for `C`/`c`/`*` comments (fixed-form indicator), check for `!` comments and `&` continuations (free-form indicators), look at file extension (`.f` usually fixed, `.f90` usually free). A scoring heuristic that checks the first 50 lines can detect format with >95% accuracy. This handles the mixed-format reality of gfortran's source tree gracefully.

**Cons:** Edge cases: some files use free-form with `.f` extension. The heuristic can be wrong on short files. Requires 30-50 lines of detection logic. If detection is wrong, the entire file's preprocessing is corrupted.

### Answer B: Assume fixed-form for `.f`/`.f77`, free-form for `.f90`/`.f95`/`.f03`

**Pros:** Zero detection logic. File extension is a strong signal — the convention exists for a reason. LAPACK and BLAS exclusively use `.f` (all fixed-form). gfortran uses `.f90` for modern code. Covers 95%+ of files correctly with zero code.

**Cons:** The 5% it gets wrong will produce corrupted chunks. gfortran has some `.f` files that are actually free-form. No recovery path — you either preprocess a file correctly or you don't.

### Answer C: Auto-detect with extension-based default and override

**Pros:** Start with extension-based assumption (Answer B). Then validate by checking for fixed-form indicators (column 6 continuation, column 1 comment characters). If the file contradicts its extension, switch formats. Log a warning when override happens. This catches the edge cases while keeping the common path fast. Total implementation: ~60 lines.

**Cons:** Slightly more complex than pure extension-based. The validation logic needs its own test cases. Edge case: files that mix both formats (rare but possible in legacy code).

### ✅ RECOMMENDATION: Answer C — Auto-detect with extension-based default and override

The extension-based default handles 95% of files instantly. The validation override catches the remaining 5% that would otherwise produce corrupted chunks. The logging on override creates a paper trail for debugging. Critical implementation detail: the validation should check the first 20 non-blank lines for fixed-form indicators (character in column 6, `C`/`c`/`*` in column 1). If ≥3 indicators found, treat as fixed-form regardless of extension. This is defensive programming that costs 60 lines but prevents silent data corruption across your 4 Fortran codebases.

---

## Q4: With 850K+ LOC across 5 codebases, your Voyage Code 2 embedding costs and ingestion time matter. How do you architect the batch ingestion pipeline for maximum throughput and minimum cost?

The spec requires 10K+ LOC in <5 minutes. You have ~850K LOC. At sequential embedding, that's ~45 minutes. At batch embedding, it could be ~5 minutes. The difference is architecture.

### Answer A: Sequential per-codebase ingestion with batch embedding

```python
for codebase in CODEBASES:
    files = discover_files(codebase)
    for file in files:
        chunks = preprocess_and_chunk(file)
        all_chunks.extend(chunks)
    embeddings = batch_embed(all_chunks, batch_size=128)  # Voyage batch
    batch_upsert(embeddings, qdrant_client)
```

**Pros:** Simple mental model. Each codebase is fully ingested before the next starts. Easy to track progress. If one codebase fails, previous ones are already stored. Batch embedding within a codebase amortizes API latency.

**Cons:** No parallelism between codebases. The embedding step is a blocking waterfall. Total wall-clock time: ~15-20 minutes for all 5 codebases. Memory scales with the largest codebase (LAPACK at 600K+ LOC could mean 30K+ chunks in memory).

### Answer B: Fully parallel pipeline with async embedding and concurrent upserts

```python
async def ingest_codebase(codebase: str):
    files = discover_files(codebase)
    chunks = []
    for file in files:
        chunks.extend(preprocess_and_chunk(file))
    embeddings = await async_batch_embed(chunks, batch_size=128)
    await async_batch_upsert(embeddings)

await asyncio.gather(*[ingest_codebase(cb) for cb in CODEBASES])
```

**Pros:** All 5 codebases ingest concurrently. Embedding API calls overlap. Total time drops to ~3-5 minutes (bounded by the largest codebase, not the sum). Concurrent upserts keep Qdrant busy while embedding calls are in flight.

**Cons:** Voyage API has rate limits — 5 concurrent codebases hitting the API simultaneously may trigger 429s. Memory usage is 5x higher (all codebases in memory simultaneously). Error handling for concurrent failures is significantly harder. Debugging race conditions at 3am is not fun.

### Answer C: Streaming pipeline with bounded concurrency

```python
async def ingest_all():
    semaphore = asyncio.Semaphore(2)  # Max 2 concurrent codebases
    async def ingest_with_limit(codebase):
        async with semaphore:
            await ingest_codebase(codebase)
    await asyncio.gather(*[ingest_with_limit(cb) for cb in CODEBASES])
```

**Pros:** Bounded concurrency (2 at a time) avoids rate limiting while still providing parallelism. Memory is controlled — only 2 codebases in memory at once. If one codebase fails, the other continues. Wall-clock time: ~7-10 minutes (2x parallel processing). The semaphore pattern is production-grade and interview-impressive.

**Cons:** Not maximally parallel. More complex than sequential. The semaphore value (2) needs tuning based on Voyage's actual rate limits.

### ✅ RECOMMENDATION: Answer C — Streaming pipeline with bounded concurrency (semaphore=2)

Answer B will hit Voyage's rate limits and create debugging nightmares. Answer A wastes 10+ minutes of wall-clock time. Answer C gives you 2x parallelism (sufficient to ingest all 5 codebases in ~8 minutes) while respecting API rate limits and keeping memory bounded. The implementation adds ~20 lines over Answer A. Critical addition: add a progress bar per codebase (`tqdm` or `Rich.Progress`) so you can monitor ingestion in both CLI and logs. Also add checkpoint logic — if LAPACK fails mid-ingestion, you shouldn't need to re-embed GnuCOBOL.

---

## Q5: You're implementing ALL 8 code understanding features. How do you architect the feature system to avoid 8x code duplication while allowing each feature to have distinct retrieval and prompting strategies?

This is the make-or-break architectural decision for the maximalist approach. 8 features done wrong = 8 × 200 lines of duplicated code. 8 features done right = a shared pipeline with 8 × 30-line feature-specific modules.

### Answer A: Each feature as a fully independent module

```python
# features/code_explanation.py
async def code_explanation(query: str, codebase: str | None) -> Response:
    chunks = await hybrid_search(query, codebase)
    chunks = await rerank(chunks)
    context = assemble_context(chunks)
    prompt = build_code_explanation_prompt(query, context)
    return await generate(prompt)
```

**Pros:** Maximum flexibility — each feature can have a completely different retrieval strategy, re-ranking logic, and prompt template. No abstraction to fight. Each module is self-contained and independently testable. If one feature needs a fundamentally different approach (e.g., Pattern Detection needs embedding clustering, not standard retrieval), it's free to diverge.

**Cons:** Massive duplication. The retrieve → rerank → assemble → prompt → generate pipeline is 80% identical across features. Bug fixes need to be applied 8 times. Consistent behavior (like citation formatting) requires manual synchronization. 8 × 200 lines = 1600 lines of feature code.

### Answer B: Abstract base feature class with template method pattern

```python
class BaseFeature(ABC):
    async def execute(self, query: str, codebase: str | None) -> Response:
        chunks = await self.retrieve(query, codebase)       # overridable
        chunks = await self.rerank(chunks, query)            # overridable
        context = self.assemble_context(chunks)              # shared
        prompt = self.build_prompt(query, context)           # abstract
        return await self.generate(prompt)                    # shared

    async def retrieve(self, query, codebase):               # default impl
        return await hybrid_search(query, codebase, top_k=self.top_k)

    async def rerank(self, chunks, query):                   # default impl
        return await layered_rerank(chunks, query)

    @abstractmethod
    def build_prompt(self, query: str, context: str) -> str: ...
```

**Pros:** The template method pattern gives you a shared pipeline with override points. Most features only need to implement `build_prompt()` (~15 lines). Features that need different retrieval (Pattern Detection, Impact Analysis) override `retrieve()`. The base class handles all shared behavior: context assembly, generation, citation formatting, confidence scoring. Total code: ~100 lines base + 8 × 30 lines = ~340 lines. Bug fixes in the pipeline propagate to all features automatically.

**Cons:** The abstraction can fight you when a feature needs to fundamentally change the pipeline order (e.g., Pattern Detection might need multiple queries). Override points must be designed up front — adding a new hook later is harder. The AI agent might struggle with the abstraction.

### Answer C: Composable pipeline with feature-specific configuration

```python
@dataclass
class FeatureConfig:
    name: str
    system_prompt: str
    top_k: int = 10
    retrieval_strategy: str = "hybrid"  # or "keyword", "clustering"
    rerank: bool = True
    metadata_filters: dict = field(default_factory=dict)

FEATURES = {
    "code_explanation": FeatureConfig(
        name="Code Explanation",
        system_prompt="Explain this code in plain English...",
        top_k=10,
    ),
    "bug_pattern_search": FeatureConfig(
        name="Bug Pattern Search",
        system_prompt="Check for: uninitialized vars, unchecked I/O...",
        retrieval_strategy="keyword",
        metadata_filters={"division": "PROCEDURE"},
    ),
}

async def execute_feature(feature: str, query: str, codebase: str | None):
    config = FEATURES[feature]
    chunks = await retrieve(query, codebase, config)
    if config.rerank:
        chunks = await rerank(chunks, query)
    context = assemble_context(chunks)
    prompt = format_prompt(config.system_prompt, query, context)
    return await generate(prompt)
```

**Pros:** No inheritance, no abstract methods. Each feature is defined as data (a config object), not code. The pipeline is a single function that reads the config. Adding a new feature is adding a dictionary entry. The configuration is self-documenting. The AI agent can generate feature configs trivially. Total code: ~80 lines pipeline + 8 × 10 lines config = ~160 lines.

**Cons:** Less flexible than Answer B — features that need truly custom logic (Pattern Detection with clustering) must either shoehorn into the config or break out of the pattern. The `retrieval_strategy` string dispatch is a code smell if it grows beyond 3 strategies.

### ✅ RECOMMENDATION: Answer C for 6 standard features + Answer A for Pattern Detection and Impact Analysis

Here's the truth: 6 of the 8 features (Code Explanation, Dependency Mapping, Documentation Gen, Translation Hints, Bug Pattern Search, Business Logic Extract) follow the identical pattern of retrieve → rerank → prompt → generate with different prompts and minor config tweaks. These should use Answer C's data-driven config approach. But Pattern Detection needs embedding clustering (fundamentally different from standard retrieval), and Impact Analysis needs reverse dependency graph traversal. These 2 features should be independent modules (Answer A) because forcing them into the config pattern adds more complexity than it saves. This hybrid approach gives you ~200 lines total: 80 for the shared pipeline, 60 for 6 feature configs, and 60 for the 2 custom features.

---

## Q6: The PRD targets >85% precision@5. With 5 codebases spanning 2 languages, how do you calibrate your hybrid search weights — specifically, what ratio of dense (vector) vs sparse (BM25) scoring should you use?

Qdrant's native hybrid search lets you specify the fusion method and relative weights. Getting this wrong means your >85% target is dead on arrival.

### Answer A: Equal weighting (0.5 dense + 0.5 sparse)

**Pros:** No tuning needed. Fair baseline. Works reasonably well when you don't know the optimal ratio. This is the default most tutorials recommend.

**Cons:** For legacy code, this is almost certainly suboptimal. COBOL identifiers like `CALCULATE-INTEREST` and Fortran identifiers like `DGEMM` are better matched by keyword (BM25) than by embedding similarity. Equal weighting means you're under-leveraging BM25's strength on exact identifier matches. Conversely, semantic queries like "show me error handling" are better matched by dense vectors. Equal weighting is a compromise that optimizes neither case.

### Answer B: Dense-heavy weighting (0.7 dense + 0.3 sparse)

**Pros:** Most user queries are semantic ("what does this do?", "show me error handling"). Dense embeddings handle these better. The 0.3 BM25 weight still catches exact identifier matches as a supplement. This matches the general RAG literature recommendation.

**Cons:** Fortran function names (DGEMM, ZHEEV, DGESV) are opaque to embedding models. COBOL paragraph names are more descriptive but still benefit from exact matching. At 0.3, BM25 doesn't have enough weight to override a bad dense match. You'll see this in evaluation: queries for specific identifiers will return semantically similar but wrong code.

### Answer C: Query-adaptive weighting based on query classification

**Pros:** Classify each query: if it contains a specific identifier (regex for COBOL paragraph patterns like `\b[A-Z][A-Z0-9-]+\b` or Fortran subroutine patterns), weight BM25 higher (0.6 sparse). If it's a natural language question, weight dense higher (0.7 dense). The classifier is 10 lines of regex, but it handles the bimodal distribution of user queries perfectly. This is the approach that actually hits >85% because it optimizes for each query type.

**Cons:** The regex classifier could misclassify — "CALCULATE INTEREST" (without hyphen) looks like natural language but is a COBOL reference. False positives in the identifier detector reduce BM25 benefit. Adds branching logic to the search path.

### ✅ RECOMMENDATION: Answer C — Query-adaptive weighting

The bimodal nature of code queries (semantic vs. identifier-based) means no single weight is optimal. The regex classifier doesn't need to be perfect — even 80% accurate classification outperforms static weights because the 20% misclassified queries still get reasonable results from the minority weight. Implementation: if the query matches `[A-Z][A-Z0-9_-]{3,}` (likely an identifier), use 0.4 dense + 0.6 sparse. Otherwise, use 0.7 dense + 0.3 sparse. Calibrate the exact weights using your ground truth evaluation set — run the eval with 3 different weight combinations and pick the one with highest precision@5. This takes 15 minutes and could be the difference between 78% and 87% precision.

---

## Q7: Your deployment architecture splits API (Render) and frontend (Vercel). How do you handle the cross-origin communication, and should the CLI hit the deployed API or run the pipeline locally?

This decision affects latency, offline capability, deployment complexity, and the demo experience.

### Answer A: CLI runs pipeline locally, Web hits deployed API

**Pros:** CLI has zero network latency for everything except embedding API and Qdrant Cloud calls. Developers using the CLI get the fastest possible experience. The CLI works with a local Qdrant instance for development. The web interface hits the Render API, which is the deployed production path. Clear separation: CLI is for developers, web is for the deployed demo.

**Cons:** Two code paths for the same pipeline. If you fix a bug in the API, the CLI doesn't get the fix until you update the local code. The grader testing the CLI needs the codebase cloned and dependencies installed. You're maintaining two different execution environments.

### Answer B: Both CLI and Web hit the deployed Render API

**Pros:** One source of truth. The CLI is just an HTTP client wrapping the API with Rich formatting. Bug fixes in the API automatically fix both interfaces. The grader can test the CLI against the deployed API without local setup. `legacylens query "..."` just calls `POST /api/query` under the hood. Ensures the deployed system is always what's being tested.

**Cons:** CLI has network latency (~100-500ms round trip to Render). Render's free tier spins down after 15 min of inactivity — first CLI query after idle has a cold start (~10-30s). Can't use CLI offline. The CLI becomes useless if Render has an outage.

### Answer C: CLI supports both modes — local and remote

```
legacylens query "..." --mode local   # Direct pipeline execution
legacylens query "..." --mode remote  # Hit deployed API
legacylens query "..."                # Default: remote
```

**Pros:** Maximum flexibility. Remote mode for demos and grading. Local mode for development and offline use. The default is remote (matches deployed behavior). The local mode is useful for rapid iteration during development. Both modes use the same output formatting.

**Cons:** Two code paths to maintain. The `--mode` flag adds cognitive overhead. Local mode still needs Qdrant Cloud access (unless you also run local Qdrant). Over-engineering for a 5-day sprint.

### ✅ RECOMMENDATION: Answer B — Both CLI and Web hit the deployed Render API

The entire point of the deployment requirement is "publicly accessible." If the CLI runs locally, you're not demonstrating a deployed system — you're demonstrating a local script. Answer B ensures that when the grader runs `legacylens query "..."`, they're hitting the exact same deployed infrastructure as the web interface. The cold start problem is solved by the cron keepalive (UptimeRobot every 14 min). The network latency (~200ms) is negligible compared to the LLM generation time (~1-2s). One truth, one pipeline, one thing to debug. The CLI becomes a ~100-line `click` + `httpx` + `rich` wrapper around the API — trivially simple to build and test.

---

## Q8: For Translation Hints (Feature 6), you're suggesting modern language equivalents for legacy code. Which target language(s) should you translate to, and how do you prevent catastrophically wrong suggestions?

Translation Hints is the riskiest feature — a bad translation is worse than no translation because it creates false confidence. But done well, it's a showstopper demo feature.

### Answer A: Translate to Python only

**Pros:** Python is the universal "readable" language. Your graders almost certainly know Python. The LLM (GPT-4o) has the strongest Python generation of any language. COBOL-to-Python and Fortran-to-Python translations are the most commonly requested in industry. One target language simplifies the prompt and reduces hallucination risk.

**Cons:** Some COBOL constructs (fixed-point decimal arithmetic, file I/O with record definitions) map more naturally to Java or C#. Fortran numerical routines map better to NumPy than raw Python. Single-language limits the feature's utility.

### Answer B: Multi-language — Python, Java, and TypeScript

**Pros:** Broader applicability. Java is common in enterprise COBOL modernization. TypeScript for web developers. Shows the feature is genuinely useful, not just a demo gimmick. The LLM can generate all three with different prompt instructions.

**Cons:** 3x the hallucination surface. Maintaining translation quality across 3 target languages requires 3 different evaluation criteria. Java enterprise patterns vs Python simplicity vs TypeScript async — the "right" translation depends on the target language. You're spread thin on quality assurance.

### Answer C: Python as default, with user-selectable target language

**Pros:** Default to Python (safest, most readable). Let users specify `--target java` or `--target typescript` if they want. The LLM handles the switching via prompt parameter: `Suggest a {target_language} equivalent`. This gives you the breadth of Answer B with the default safety of Answer A. In the demo, use Python. In the interview, mention it's configurable.

**Cons:** The user-selectable option needs testing for each supported language. Java/TypeScript translations may be lower quality since you've spent less time validating them.

### ✅ RECOMMENDATION: Answer C — Python default, user-selectable target

Default to Python for demos, grading, and evaluation. The `target_language` parameter is a one-line prompt change: `"Suggest a {target_language} equivalent"`. Test primarily with Python. Include a mandatory caveat in every translation output: **"These are structural suggestions to aid understanding, not production-ready translations. Verify all business logic equivalence before use."** This caveat is critical — it sets appropriate expectations and demonstrates professional awareness that machine translation of legacy code is inherently approximate. In the interview, say: "I chose to include the caveat because a misleading translation in a financial system is worse than no translation at all."

---

## Q9: The PRD calls for a Next.js 14 frontend with App Router. Given the 5-day timeline, should you use Server Components (RSC), Client Components, or a hybrid approach?

This affects build complexity, streaming support, bundle size, and how fast you can ship the frontend on Days 4-5.

### Answer A: Full Client Components (use client everywhere)

**Pros:** Familiar React mental model. No hydration issues. State management (useState, useReducer) works everywhere. SSE streaming integration is straightforward with client-side `EventSource`. Fastest to build because there are no RSC gotchas. Every React developer knows how to write client components.

**Cons:** Larger bundle size. No server-side rendering benefits. Search engines can't crawl query results (irrelevant for this project, but worth noting). You're shipping Next.js without using its primary differentiating feature.

### Answer B: Full Server Components with Server Actions

**Pros:** Smallest bundle size. Server Components stream HTML progressively. Server Actions for form submissions (query input → server action → stream results). True SSR. Leverages Next.js 14's primary feature. Data fetching happens on the server, closer to your Render API.

**Cons:** Server Components can't use useState, useEffect, or browser APIs. Streaming a full LLM response through Server Components requires the experimental `useFormStatus` or Suspense boundaries — not well-documented. Every interactive element (query input, codebase selector, feature picker, dark mode toggle) needs to be a Client Component anyway. You'll spend hours fighting RSC limitations for minimal benefit.

### Answer C: Hybrid — Server Components for layout/static, Client Components for interactive parts

**Pros:** The natural Next.js 14 pattern: `layout.tsx` and page shells are Server Components (fast initial load), while `QueryInput`, `StreamingResponse`, `CodebaseSelector`, and `FeaturePicker` are Client Components with `'use client'`. You get the fast initial load of RSC with full interactivity where needed. The dashboard page can be a Server Component that fetches codebase status server-side.

**Cons:** You need to understand the RSC mental model to draw the boundary correctly. Some prop-drilling complications when Server Components need to pass data to Client Components.

### ✅ RECOMMENDATION: Answer A — Full Client Components

Controversial take, but hear me out: you're building this frontend in ~8 hours on Days 4-5. RSC gotchas will cost you 2-4 hours of debugging for zero user-visible benefit. Your grader won't inspect your bundle size. They'll interact with the query interface, see streaming results, select codebases and features, and judge the experience. Client Components give you 100% of that experience with zero RSC friction. Use `'use client'` at the top of every page, and ship a beautiful, interactive app in 8 hours instead of a partially-working RSC app in 12. The pragmatic answer is: Next.js is your deployment vehicle (Vercel's free tier is great), not your architectural showcase. React Client Components are the showcase.

---

## Q10: Your evaluation dataset needs 50+ queries across 5 codebases and 8 features. How do you generate a high-quality ground truth dataset in ~2.5 hours when you barely know the codebases?

This is the hardest practical challenge of the maximalist approach. You need ground truth for codebases you've never read, in languages you don't fully understand, covering features you just built.

### Answer A: Manually curate all 50 queries by reading codebase source

**Pros:** Highest quality ground truth. Forces deep understanding. Each query-answer pair is verified.

**Cons:** Reading 850K LOC across 5 codebases to generate 50 queries would take 20+ hours, not 2.5. Physically impossible in the timeline.

### Answer B: LLM-generated ground truth — feed the LLM code chunks and ask it to generate query-answer pairs

**Pros:** Fast — 50+ pairs in 30 minutes. Diverse question types. Covers all codebases automatically. The LLM can generate queries for each of the 8 feature types. Process: for each codebase, randomly sample 10 chunks, ask GPT-4o to generate 2 queries per chunk with expected answers, manually verify 30% of them.

**Cons:** Circular reasoning risk: the same LLM generates the ground truth and the answers. Some generated queries may be unanswerable (LLM hallucinates a function that doesn't exist). Quality varies — some generated pairs will be trivial ("what is the file name?" → metadata only).

### Answer C: Stratified hybrid — 15 manual (3 per codebase) + 35 LLM-generated, verify 20

**Pros:** Your 15 manual queries are surgically targeted: 3 per codebase, chosen to cover the spec's testing scenarios and the hardest edge cases. These are your high-confidence evaluation anchors. The 35 LLM-generated queries fill coverage gaps across features and codebases. Verifying 20 of the 35 (57%) gives you a total of 35 high-confidence pairs + 15 unverified but likely-correct pairs. The verification step takes ~1 hour and breaks the circularity concern for the majority of your dataset. Total time: ~2.5 hours.

**Cons:** The 15 unverified LLM pairs may contain errors. 15 manual queries means reading some source code (30-60 min). The manual queries require you to actually find specific paragraphs/subroutines in the codebases.

### ✅ RECOMMENDATION: Answer C — Stratified hybrid with targeted manual queries

The 15 manual queries should be structured as follows: for each of the 5 codebases, create 3 queries mapped to different feature types. Example for GnuCOBOL: (1) Code Explanation: "What does the MAIN-LOGIC paragraph do?", (2) Business Logic: "What are the business rules for customer validation?", (3) Bug Pattern: "Are there any unhandled error conditions?" For each manual query, verify the expected chunks by `grep`-ing the actual source files — takes 2-3 minutes per query. The LLM-generated queries use this process: sample 7 chunks per codebase (35 total), ask GPT-4o to generate one query per chunk with the expected file:line reference, then manually verify 20 of the 35 by checking the source. This gives you a rigorous, multi-codebase, multi-feature evaluation dataset in 2.5 hours.

---

## Round 1 Summary

| # | Decision | Recommendation | Core Principle |
|---|---|---|---|
| 1 | Collection Architecture | Single shared collection with indexed metadata | Simplicity scales; fan-out multiplies bugs |
| 2 | Preprocessor Architecture | Functional (separate files + shared utils) | Composition > inheritance for 2 languages |
| 3 | Fortran Format Detection | Extension-based default + heuristic override | Defensive programming prevents silent corruption |
| 4 | Batch Ingestion | Bounded concurrency (semaphore=2) + progress bars | 2x parallelism without rate limit pain |
| 5 | Feature Architecture | Config-driven for 6 features + custom for 2 | Data-driven where possible, custom where necessary |
| 6 | Hybrid Search Weights | Query-adaptive (identifier vs semantic detection) | Match the weight to the query type |
| 7 | CLI Architecture | CLI hits deployed API (not local pipeline) | One truth, one pipeline, one thing to debug |
| 8 | Translation Target | Python default, user-selectable + mandatory caveat | Safety > breadth for the riskiest feature |
| 9 | Next.js Strategy | Full Client Components (pragmatic) | Ship in 8 hours, not 12 |
| 10 | Ground Truth | Stratified hybrid: 15 manual + 35 LLM, verify 20 | Targeted manual anchors + LLM breadth |

---
---

# ROUND 2 OF 3: Implementation Deep Dive & Feature Engineering

---

## Q11: You need language-aware prompts for both COBOL and Fortran. Should you maintain separate prompt templates per language, or use a single parameterized template with language-specific inserts?

The prompt template drives answer quality. Getting the language context right is the difference between the LLM misinterpreting COBOL columns as indentation and correctly understanding PROCEDURE DIVISION paragraphs.

### Answer A: Separate prompt templates per language (cobol_prompts.py, fortran_prompts.py)

**Pros:** Each template is optimized for its language. The COBOL template can reference divisions, paragraphs, COPY statements, 88-level items. The Fortran template can reference subroutines, COMMON blocks, IMPLICIT NONE, DO loops. No template logic — just string formatting. Each template is independently testable and modifiable.

**Cons:** The 8 features × 2 languages = 16 prompt templates. Changes to the shared structure (output format, citation instructions, confidence scoring) must be replicated across all 16. High maintenance burden. Most of the prompt (80%) is identical across languages.

### Answer B: Single parameterized template with language insert block

```python
SYSTEM_TEMPLATE = """
You are a legacy code analysis expert helping developers understand
enterprise codebases written in {language}.

{language_context}

Always cite specific file paths and line numbers...
"""

LANGUAGE_CONTEXTS = {
    "cobol": "You understand COBOL's structure: IDENTIFICATION, ENVIRONMENT, DATA, and PROCEDURE divisions. Paragraphs are execution units...",
    "fortran": "You understand Fortran's structure: PROGRAM, MODULE, SUBROUTINE, and FUNCTION blocks. CALL transfers control..."
}
```

**Pros:** One template with 2 language inserts. The shared structure (citation instructions, confidence output, output format) lives in one place. 8 feature variations are just different instruction blocks within the same template. Total prompt code: ~80 lines instead of ~400 lines. Changes to the output format propagate to all language/feature combinations automatically.

**Cons:** The template becomes complex with multiple insertion points (`{language}`, `{language_context}`, `{feature_instructions}`, `{chunks}`, `{query}`). Testing is slightly harder — you need to test the combinations. Risk of a language insert conflicting with the shared template wording.

### Answer C: Template hierarchy — base template → language overlay → feature overlay

```python
base = load_template("base.txt")           # Shared instructions
lang = load_template(f"{language}.txt")     # Language-specific
feat = load_template(f"{feature}.txt")      # Feature-specific
prompt = base + lang + feat + chunks + query
```

**Pros:** Clean separation of concerns. Each layer is independently modifiable. The base handles citations and output format. The language layer handles syntax understanding. The feature layer handles the specific task. Composable — any combination of language × feature is automatically supported.

**Cons:** Three files to load per prompt. The composition order matters (base must come before language, which must come before feature). Debugging a bad prompt requires tracing through 3 layers. Over-engineered for 2 languages × 8 features.

### ✅ RECOMMENDATION: Answer B — Single parameterized template with language inserts

Answer B gives you 90% of Answer C's composability with 30% of the complexity. The template has 4 insertion points: `{language}`, `{language_context}`, `{feature_instructions}`, `{retrieved_chunks}`, and `{query}`. The feature instructions are a dictionary mapping feature names to instruction strings (same pattern as the feature config from Q5). Total: one `prompts.py` file, ~100 lines, handling all 2 × 8 = 16 combinations. Test by asserting that every language × feature combination produces a non-empty prompt with all required sections (citations instruction, confidence instruction, language context).

---

## Q12: For Dependency Mapping (Feature 2), how do you trace PERFORM/CALL chains in COBOL and Fortran when the code has been chunked into separate vectors?

Dependency Mapping requires understanding that paragraph A PERFORMs paragraph B, which PERFORMs paragraph C. But paragraphs A, B, and C are separate chunks in Qdrant. The dependency graph exists in the code, not in the vectors.

### Answer A: Static analysis during preprocessing — extract PERFORM/CALL targets as metadata

**Pros:** During preprocessing, regex-extract all `PERFORM <paragraph-name>` (COBOL) and `CALL <subroutine-name>` (Fortran) statements. Store as metadata: `{"dependencies": ["CALCULATE-INTEREST", "VALIDATE-CUSTOMER"]}`. At query time, retrieve the requested chunk, then use metadata filtering to find all chunks whose `name` matches any dependency. This builds the dependency tree without any LLM involvement. Fast (metadata filtering is O(1) in Qdrant), accurate (regex on PERFORM/CALL is reliable), and deterministic.

**Cons:** Static analysis misses dynamic dispatches (COBOL `PERFORM VARYING` with computed names, Fortran function pointers). The regex extraction adds ~30 lines to each preprocessor. Circular dependencies (A calls B calls A) need cycle detection. Only captures direct dependencies, not transitive chains (A → B → C requires recursive resolution).

### Answer B: LLM-based dependency extraction — ask GPT-4o to identify dependencies from retrieved chunks

**Pros:** The LLM can identify dependencies that regex misses: indirect calls, conditional dispatches, data flow dependencies ("CUSTOMER-RECORD is modified by these paragraphs"). No preprocessing changes needed — the dependencies are extracted at query time. More comprehensive than static analysis.

**Cons:** Adds an LLM call before the main generation — 1-2 seconds extra latency. The LLM may hallucinate dependencies that don't exist. Non-deterministic — same query may return different dependency trees. More expensive ($$ per query). Can't build a complete graph without processing all chunks.

### Answer C: Hybrid — static metadata for direct calls + LLM for transitive and data-flow dependencies

**Pros:** Direct PERFORM/CALL dependencies are extracted statically during preprocessing (reliable, fast). At query time, use the static metadata to resolve the immediate dependency tree. Then pass the resolved tree to the LLM with the instruction: "Given this call chain, identify any data-flow dependencies or indirect references I might have missed." The static analysis handles 90% of cases; the LLM adds value on the remaining 10%.

**Cons:** Two-step process adds complexity. The static metadata needs to be maintained when chunks are re-indexed. The LLM step may not add much value if the static analysis is comprehensive.

### ✅ RECOMMENDATION: Answer A for MVP/G4, add Answer C's LLM enhancement for GFA

Static analysis via regex is the right foundation because dependency mapping must be deterministic and fast. Extract `PERFORM <name>` and `CALL <name>` targets during preprocessing, store as `dependencies` metadata. At query time: (1) Retrieve the target chunk, (2) Find all chunks with matching `name` in `dependencies`, (3) Recursively resolve up to depth=3, (4) Present the tree. For GFA polish, add the LLM pass to identify data-flow dependencies. The regex patterns: COBOL → `PERFORM\s+([A-Z][A-Z0-9-]+)`, Fortran → `CALL\s+([A-Za-z][A-Za-z0-9_]+)`. This handles 90%+ of dependencies in both languages with ~30 lines of regex.

---

## Q13: Pattern Detection (Feature 3) requires finding similar code patterns across the entire codebase. Standard top-k retrieval won't work because you need to cluster, not rank. How do you implement this?

This is the most architecturally distinct feature — it needs a fundamentally different retrieval strategy.

### Answer A: Embedding-based clustering — embed the target chunk, find all chunks within a similarity threshold

**Pros:** Use the query chunk's embedding as the seed. Search Qdrant with a high `limit` (100) and a `score_threshold` (e.g., 0.8). Group the results by file/function name. This finds structurally similar code across the entire codebase. Works across languages — a Fortran matrix multiplication routine might cluster with COBOL arithmetic paragraphs that do similar operations. Zero additional infrastructure — Qdrant already supports threshold-based search.

**Cons:** Similarity threshold is hard to calibrate. Too high (0.9) = only near-exact duplicates. Too low (0.7) = noisy results. Embedding similarity doesn't always mean "same pattern" — two functions that do different things might have similar embeddings because they use similar syntax. No semantic understanding of what makes a "pattern."

### Answer B: LLM-guided pattern identification — ask the LLM to describe the pattern, then search for that description

**Pros:** The user says "find error handling patterns." The LLM generates a pattern description: "Functions that check return codes and branch to error labels." Then search for that description across the codebase. This captures the semantic meaning of "pattern," not just syntactic similarity. More intuitive results.

**Cons:** Two LLM calls per query (describe + generate). The LLM-generated description may not match how the code is actually embedded. Slow — 3-5 seconds just for the description step. The description is a noisy proxy for the actual pattern.

### Answer C: Hybrid — extract pattern signature from query, then threshold search + LLM grouping

**Pros:** Step 1: Retrieve top-50 chunks by hybrid search (wide net). Step 2: Ask the LLM to group these 50 chunks into pattern categories based on structural similarity. Step 3: Present the groups with labels. The retrieval casts a wide net, the LLM does the intelligent grouping. Results are semantically meaningful ("Group 1: Error handling routines (12 instances)", "Group 2: Data validation patterns (8 instances)").

**Cons:** Passing 50 chunks to the LLM may exceed context limits. The grouping step takes 2-4 seconds. Cost: ~50K tokens per pattern detection query. The LLM may group inconsistently.

### ✅ RECOMMENDATION: Answer A for the retrieval, Answer C's LLM grouping for presentation

Step 1: Use the user's query to retrieve top-30 chunks via standard hybrid search (not threshold-based — the user query "find error handling patterns" should match error-handling code semantically). Step 2: Pass the 30 chunks to GPT-4o with the instruction: "Group these code chunks by structural pattern. Name each group. For each group, explain the common pattern and list the chunks." Step 3: Present as grouped results. This gives you the wide-net retrieval of standard search + the intelligent grouping of LLM analysis. Keep top-30 (not 50) to stay within token budget. The LLM grouping adds ~2 seconds but transforms a list of raw results into a meaningful pattern analysis. This is the feature that will impress in the demo.

---

## Q14: For Impact Analysis (Feature 4), you need to answer "what would break if this code changes?" This requires reverse dependency resolution. How do you build this efficiently?

Impact Analysis is the reverse of Dependency Mapping — instead of "what does A call?", it's "what calls A?" This requires knowing every chunk that references the target.

### Answer A: Pre-computed reverse dependency index

**Pros:** During ingestion, build a reverse map: for every dependency target, list all callers. Store as: `reverse_deps = {"CALCULATE-INTEREST": ["MAIN-LOGIC", "PROCESS-LOAN", "BATCH-UPDATE"]}`. At query time, look up the target name in the reverse map. Instant results, no additional search needed. Deterministic and complete (captures every static reference).

**Cons:** The reverse map must be rebuilt on re-ingestion. Requires an additional data store (file or database) alongside Qdrant. Only captures static PERFORM/CALL references.

### Answer B: Query-time reverse lookup via Qdrant metadata filtering

**Pros:** At query time, search Qdrant for all chunks whose `dependencies` metadata field contains the target name: `qdrant.scroll(filter={"dependencies": {"match": "CALCULATE-INTEREST"}})`. No additional data store needed — uses existing metadata from Q12. Always up-to-date because it queries the live index.

**Cons:** Qdrant's `scroll` with metadata filtering is slower than a direct lookup (~50-100ms). The `dependencies` field must be indexed for payload filtering. Only works if dependency extraction from Q12 is comprehensive.

### Answer C: LLM-based impact analysis on retrieved context

**Pros:** Retrieve the target chunk + surrounding context. Ask GPT-4o: "If this code changes, what else in the codebase would be affected? Consider both direct callers and data structures that depend on this code's output." The LLM can reason about indirect impacts (e.g., "if CALCULATE-INTEREST changes, all reports that reference INTEREST-TOTAL would need updating").

**Cons:** The LLM can't see the whole codebase — only retrieved chunks. Hallucination risk is high for impact analysis because the LLM may invent dependencies. Slow (2-3 seconds). Non-deterministic.

### ✅ RECOMMENDATION: Answer B for direct impacts + Answer C for indirect impacts

Answer B is the primary mechanism: use Qdrant's payload filtering to find all chunks whose `dependencies` field contains the target. This gives you the complete, deterministic list of direct callers. Then pass these direct callers + the target chunk to GPT-4o with the instruction: "These modules directly depend on [target]. What indirect impacts should a developer be aware of? Consider data structures, downstream outputs, and side effects." The LLM adds value here because indirect impact analysis genuinely requires reasoning, not just graph traversal. Present the output in two sections: "Direct Dependencies (verified)" and "Potential Indirect Impacts (LLM-assessed, verify before changing)."

---

## Q15: Your context assembly uses a dynamic token budget. With 5 codebases, chunks vary wildly in size (COBOL paragraphs: 20-200 lines, Fortran subroutines: 5-500 lines). How do you set the budget and handle the variance?

The context window is your most precious resource. Too few tokens → insufficient context → bad answers. Too many tokens → LLM gets lost in irrelevant code → bad answers.

### Answer A: Fixed budget — always 4,000 tokens for context, regardless of query

**Pros:** Predictable. Easy to implement. Guarantees room for the prompt (~500 tokens) and generation (~1,000 tokens) within GPT-4o's 128K context. Consistent cost per query.

**Cons:** 4,000 tokens may be too small for complex cross-file queries that need 10+ chunks. May be too large for simple "what does this paragraph do?" queries where 1 chunk suffices. Doesn't adapt to the actual information density of retrieved chunks.

### Answer B: Query-type adaptive budget

**Pros:** Simple queries (Code Explanation) get 3,000 tokens. Cross-file queries (Dependency Mapping, Impact Analysis, Pattern Detection) get 6,000 tokens. The budget adapts to the expected complexity. Implementation: the feature config (from Q5) includes a `max_context_tokens` parameter. Each feature sets its own budget based on expected needs.

**Cons:** The optimal budget per feature type requires experimentation. Some queries within a feature type may need more or less. The budget is per-feature, not per-query.

### Answer C: Dynamic budget based on chunk relevance scores

**Pros:** Add chunks in order of relevance score until budget is exhausted. For the top-1 chunk, include hierarchical context (surrounding paragraphs/subroutines). For chunks 2-N, include only the chunk itself. Budget: `total_budget = 5000`, allocate up to 2000 for the top-1 expanded context, fill remaining with additional chunks. This maximizes information density: the most relevant chunk gets full context, the supporting chunks provide breadth.

**Cons:** The hierarchical expansion of top-1 requires chunk adjacency metadata (which paragraph comes before/after). The budget split (2000 + 3000) needs tuning. Variable output makes testing harder.

### ✅ RECOMMENDATION: Answer C — Dynamic budget with hierarchical expansion for top-1

This is the approach that actually maximizes answer quality. The top-1 chunk is almost always the most important — giving it hierarchical context (parent section + adjacent paragraphs) means the LLM understands where the code sits structurally. The remaining budget fills with diverse supporting chunks from other files/functions. Implementation: use `tiktoken` to count tokens precisely. Budget = 5,000 tokens total. Top-1 gets up to 2,000 tokens (expand upward to section header, expand downward to next paragraph). Chunks 2-10 fill the remaining 3,000 tokens in relevance order. If a chunk would exceed the remaining budget, skip to the next smaller one (knapsack-style packing). This produces the most information-dense context window possible.

---

## Q16: Bug Pattern Search (Feature 7) requires a knowledge base of known anti-patterns for COBOL and Fortran. Where does this knowledge come from, and how do you prevent false positives?

Unlike the other 7 features, Bug Pattern Search requires domain-specific knowledge about what constitutes a "bug pattern" in legacy languages. This isn't something the embedding model or standard retrieval can provide.

### Answer A: Hardcoded pattern list in the prompt template

**Pros:** Curate a list of 10-15 common legacy code anti-patterns: uninitialized variables, unchecked I/O status, dead code paths, missing STOP RUN, GOTO into paragraphs from outside, unclosed files, Fortran COMMON block misalignment, EQUIVALENCE abuse, missing IMPLICIT NONE. Embed the list directly in the system prompt. The LLM uses these patterns as a checklist when analyzing retrieved code. Implementation: ~20 lines added to the prompt. Zero additional infrastructure.

**Cons:** Limited to patterns you know about. The list may not cover language-specific edge cases. The LLM may "find" patterns that don't exist (false positives from the checklist priming effect). Not extensible without code changes.

### Answer B: LLM-inferred patterns — ask GPT-4o to identify potential issues based on general code quality principles

**Pros:** No domain knowledge needed upfront. The LLM has been trained on code quality literature and can identify issues from first principles. Can find novel patterns you didn't anticipate. More comprehensive than a static checklist.

**Cons:** The LLM may not understand language-specific idioms (what looks like a "bug" in Python may be standard COBOL practice). High false positive rate — the LLM may flag legitimate patterns as bugs. No calibration mechanism. Inconsistent results across queries.

### Answer C: Curated checklist + LLM analysis with severity classification

**Pros:** Combine a curated anti-pattern checklist (Answer A) with LLM analysis (Answer B). The checklist provides the detection framework; the LLM provides the analysis. Instruct the LLM: "Check the retrieved code for these known patterns: [checklist]. Also identify any additional code quality concerns. For each finding, classify severity as CRITICAL / WARNING / INFO and explain why." The severity classification reduces false positive noise — INFOs can be filtered in the UI if needed. The checklist anchors the analysis, while the LLM adds breadth.

**Cons:** The prompt becomes longer (~300 tokens for the checklist). The LLM may over-report LOW severity issues. Needs calibration via manual review.

### ✅ RECOMMENDATION: Answer C — Curated checklist + LLM severity classification

The checklist should include these patterns per language:

**COBOL:** (1) Unchecked FILE STATUS after I/O, (2) GOTO without matching paragraph, (3) Missing STOP RUN, (4) Uninitialized WORKING-STORAGE variables, (5) Dead paragraphs (never PERFORMed), (6) Implicit data truncation on MOVE, (7) Missing COPY member references.

**Fortran:** (1) Missing IMPLICIT NONE, (2) Uninitialized variables, (3) COMMON block misalignment, (4) Array bounds not checked, (5) EQUIVALENCE aliasing bugs, (6) Missing DEALLOCATE for allocated memory, (7) FORMAT statement type mismatches.

The severity classification is critical for usability — nobody wants 50 INFOs drowning 3 CRITICALs. Display CRITICAL and WARNING by default; let users expand to see INFO. This is a small UX decision with huge impact on perceived quality.

---

## Q17: Streaming responses via SSE — how do you implement end-to-end streaming from the OpenAI API through your FastAPI backend to both the web UI and CLI?

Streaming is the single highest-impact UX feature. It transforms a 3-second blank wait into a 500ms-first-token experience.

### Answer A: FastAPI StreamingResponse with OpenAI's stream=True

```python
@app.post("/api/query/stream")
async def stream_query(request: QueryRequest):
    async def event_generator():
        async for chunk in openai_client.chat.completions.create(
            model="gpt-4o", messages=messages, stream=True
        ):
            if chunk.choices[0].delta.content:
                yield f"data: {json.dumps({'text': chunk.choices[0].delta.content})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Pros:** End-to-end streaming with no buffering. First token reaches the client in ~500ms. FastAPI's `StreamingResponse` handles backpressure. The OpenAI SDK's async streaming is production-grade. The web UI consumes via `EventSource` or `fetch` with ReadableStream. Total implementation: ~30 lines backend + ~20 lines frontend.

**Cons:** Error handling mid-stream is tricky — if the LLM errors after 50 tokens, the client has already rendered partial output. SSE is HTTP-based, so no bidirectional communication. Some reverse proxies (Render free tier) may buffer SSE events, adding latency.

### Answer B: WebSocket streaming for full-duplex communication

**Pros:** True bidirectional — client can cancel mid-stream. Lower latency than SSE because WebSocket has no HTTP overhead per message. Can multiplex multiple message types (progress, tokens, metadata, done) on one connection.

**Cons:** WebSocket support on Render's free tier is limited. FastAPI WebSocket requires different deployment config. More complex client-side code. The CLI would need a WebSocket client library instead of simple HTTP. Overkill for a unidirectional streaming use case.

### Answer C: Non-streaming with loading indicator

**Pros:** Zero implementation complexity. The API returns the complete response in one shot. Show a loading spinner while waiting. Guaranteed consistent output formatting.

**Cons:** 2-3 second blank wait with a spinner. Feels slow and unresponsive. Modern users expect streaming. Missed opportunity to showcase technical sophistication.

### ✅ RECOMMENDATION: Answer A — SSE streaming via FastAPI StreamingResponse

SSE is the right tool: it's unidirectional (server → client), works over standard HTTP (no WebSocket deployment issues), and is trivial to consume in both the browser (`EventSource`) and the CLI (`httpx` streaming). Add a non-streaming fallback endpoint (`POST /api/query` returns complete JSON) for the CLI's `--json` mode and for evaluation scripting. The Render buffering concern is mitigated by adding `X-Accel-Buffering: no` header and `Cache-Control: no-cache`. Implementation priority: get non-streaming working first (MVP), add SSE streaming on Day 3 (G4), polish streaming UX on Day 4 (GFA).

---

## Q18: You need to handle cross-codebase queries like "show me all error handling patterns across all codebases." How do you handle score normalization when COBOL and Fortran chunks have different embedding distributions?

When you search a shared collection without a codebase filter, chunks from COBOL and Fortran codebases compete. But their embedding distributions may differ — COBOL code may systematically score higher or lower on similarity for a given query.

### Answer A: Don't normalize — let raw scores determine ranking

**Pros:** Simplest. If COBOL chunks genuinely match the query better, they should rank higher. The user asked about "all codebases," so the best results should surface regardless of language. Qdrant's scoring is already calibrated within the same embedding model.

**Cons:** If COBOL embeddings have systematically higher cosine similarity (because Voyage Code 2 was trained on more COBOL-like code than Fortran-like code), COBOL chunks will dominate cross-codebase results even when Fortran chunks are equally relevant. The user gets a biased view.

### Answer B: Per-codebase normalization — z-score normalize within each codebase, then merge

**Pros:** Compute mean/stddev of similarity scores per codebase from historical queries. Normalize each chunk's score to z-score within its codebase. Then merge and rank by normalized score. This ensures COBOL and Fortran chunks compete fairly regardless of baseline score distributions.

**Cons:** Requires pre-computed score statistics per codebase. The statistics change as you add/remove chunks. Over-engineering for the likely scenario that score distributions are similar (same embedding model, similar code density).

### Answer C: Codebase-aware re-ranking — boost underrepresented codebases in results

**Pros:** After retrieval, ensure at least 1-2 results from each relevant codebase appear in the top-10. Implementation: retrieve top-20, group by codebase, take top-2 from each codebase, then fill remaining slots by raw score. This guarantees cross-codebase diversity in results without complex normalization. Simple and effective.

**Cons:** May surface lower-relevance results from a codebase just to meet the diversity requirement. The "2 per codebase" threshold is arbitrary.

### ✅ RECOMMENDATION: Answer A for default, Answer C for explicitly cross-codebase queries

Most queries are about a specific concept ("error handling", "data validation") where the best results should win regardless of codebase. Answer A (raw scores) is correct here because Voyage Code 2 produces comparable score distributions across languages — it's the same model embedding both. BUT when the user explicitly queries across codebases (no codebase filter + the query implies comparison, e.g., "how does error handling differ between COBOL and Fortran"), trigger Answer C's diversity-aware re-ranking to ensure representation from each codebase. Detection: if the query mentions multiple languages or explicitly says "all codebases" or "compare," activate diversity re-ranking. This is 15 lines of conditional logic in the re-ranker.

---

## Q19: The PRD specifies Click + Rich for the CLI. How do you structure the CLI commands to mirror the web API without duplicating all the HTTP client logic?

The CLI needs to support: query (with codebase filter, feature selection, json output), ingest, evaluate, and status. All hitting the deployed API.

### Answer A: One file, one `click.group` with subcommands

```python
@click.group()
def cli(): pass

@cli.command()
@click.argument("query")
@click.option("--codebase", default=None)
@click.option("--feature", default="code_explanation")
@click.option("--json-output", is_flag=True)
def query(query, codebase, feature, json_output):
    response = httpx.post(f"{API_URL}/api/query", json={...})
    if json_output:
        click.echo(json.dumps(response.json(), indent=2))
    else:
        render_rich(response.json())
```

**Pros:** One file. Dead simple. Each subcommand is a function. The `httpx` calls are inline. `--json-output` flag for scripting. Rich rendering for human-readable output. Total: ~150 lines.

**Cons:** Rich rendering logic bloats the file. No separation between HTTP client and presentation. Hard to test the rendering independently from the API calls.

### Answer B: Separated architecture — client module + rendering module + CLI module

```python
# cli/client.py — HTTP client
# cli/render.py — Rich formatting
# cli/main.py — Click commands (thin wrappers)
```

**Pros:** The client module is reusable (evaluation script can import it). The rendering module can be tested with mock data. The CLI module is just glue. Clean separation of concerns. Each module is < 80 lines.

**Cons:** 3 files for what could be 1. Over-architecture for a CLI that's essentially 5 HTTP calls with formatting.

### Answer C: Single file with inline rendering, but extract the API client as a shared module

**Pros:** Keep the CLI as one file (Answer A) but extract the HTTP client into `src/api/client.py` that both the CLI and the evaluation script share. This avoids duplicating the API URL management, authentication, and error handling. The Rich rendering stays inline in the CLI because it's presentation-only and doesn't need reuse.

**Cons:** The shared client module adds one extra file. Minor structural overhead.

### ✅ RECOMMENDATION: Answer C — Single CLI file + shared API client

The evaluation script and CLI both need to call the API. Extract the shared HTTP client (`src/api/client.py`: ~40 lines handling base URL, headers, error mapping, streaming). The CLI file imports the client and adds Click commands + Rich rendering (~120 lines). The evaluation script imports the same client for automated querying. This is the minimum separation that avoids duplication without over-architecture. The Rich rendering in the CLI should include: syntax-highlighted code blocks (`Rich.Syntax`), colored confidence badges, file:line clickable hyperlinks (Rich supports terminal hyperlinks), and a progress spinner for streaming.

---

## Q20: Your cost analysis needs projections for 100/1K/10K/100K users. How do you calculate the LLM cost when query complexity varies wildly (a simple Code Explanation vs a complex Pattern Detection)?

The cost analysis is a graded deliverable. "Approximately $750/month for 1K users" is not specific enough. The grader wants to see your methodology.

### Answer A: Single average — estimate an average query cost and multiply

**Pros:** Simple. Assume average 2,500 input tokens + 500 output tokens per query. GPT-4o: $2.50/1M input, $10/1M output. Average cost: $0.00625 + $0.005 = $0.01125 per query. At 10 queries/user/day × 30 days = 300 queries/user/month. 1K users = 300K queries = $3,375/month. Done in 5 minutes.

**Cons:** Ignores query complexity variance. Pattern Detection queries use ~50K input tokens (30 chunks + grouping prompt). Code Explanation uses ~3K tokens. Averaging them is misleading. The cost analysis looks superficial.

### Answer B: Per-feature cost modeling with usage distribution

**Pros:** Model cost per feature type. Assume a usage distribution: Code Explanation 40%, Business Logic 15%, Dependency Mapping 12%, Documentation Gen 10%, Pattern Detection 8%, Bug Pattern Search 7%, Impact Analysis 5%, Translation Hints 3%. Calculate per-feature token costs:

| Feature | Avg Input Tokens | Avg Output Tokens | Cost/Query |
|---|---|---|---|
| Code Explanation | 3,000 | 500 | $0.0125 |
| Pattern Detection | 15,000 | 1,000 | $0.0475 |
| Impact Analysis | 8,000 | 800 | $0.028 |
| ... | ... | ... | ... |

Then compute: weighted average cost = Σ(usage% × cost_per_query). This is rigorous, auditable, and impressive.

**Cons:** The usage distribution is guesswork. Per-feature token estimates require actual measurement (which you'll have from development). Takes 30-60 minutes to build properly.

### Answer C: Measured costs from development + projected scaling

**Pros:** During development, you have real API dashboard data from Voyage, OpenAI, and Cohere. Use actual token counts from your 50+ evaluation queries as the empirical basis. Calculate: actual_cost_per_query = total_api_spend / total_eval_queries. Then project: monthly_cost = actual_cost_per_query × queries_per_user × users × days. Include the real measured numbers alongside the projections. "Our 50 evaluation queries cost $0.73 total ($0.0146/query average). At 1K users with 10 queries/day, projected monthly cost: $4,380."

**Cons:** Development queries may not represent production query distribution. Sample size (50 queries) is small. But real numbers always beat estimates.

### ✅ RECOMMENDATION: Answer C, enriched with Answer B's per-feature breakdown

Present BOTH measured and modeled costs. The measured costs prove you actually tracked your spend (most students won't). The per-feature model shows you understand cost drivers. Format:

1. **Actual Development Spend** — real numbers from API dashboards
2. **Per-Feature Cost Model** — Answer B's table with measured token counts from evaluation
3. **Projections** — 100/1K/10K/100K users using the weighted average from #2
4. **Optimization Strategies** — "Route 60% of queries to GPT-4o-mini (3x cheaper), cache frequent queries (30% hit rate estimated), reduce re-ranking for non-critical features"

This deliverable takes ~2 hours but will be the most thorough cost analysis any grader sees.

---

## Round 2 Summary

| # | Decision | Recommendation | Core Principle |
|---|---|---|---|
| 11 | Prompt Architecture | Single parameterized template + language inserts | One template, 2 inserts, 16 combinations |
| 12 | Dependency Mapping | Static PERFORM/CALL regex + metadata filtering | Deterministic graph traversal, LLM for enrichment |
| 13 | Pattern Detection | Hybrid search + LLM grouping/labeling | Wide-net retrieval + intelligent clustering |
| 14 | Impact Analysis | Qdrant reverse metadata lookup + LLM indirect analysis | Verified direct deps + assessed indirect deps |
| 15 | Context Budget | Dynamic 5,000 tokens: 2,000 for expanded top-1 + 3,000 for breadth | Maximize depth on top result, breadth on rest |
| 16 | Bug Pattern Search | Curated checklist + LLM severity classification | Anchored analysis with actionable severity levels |
| 17 | Streaming | SSE via FastAPI StreamingResponse | Works everywhere, 500ms first-token |
| 18 | Cross-Codebase Scoring | Raw scores default + diversity re-ranking for explicit cross-queries | Let best results win, intervene only when diversity matters |
| 19 | CLI Architecture | Single CLI file + shared API client module | Minimum separation to avoid duplication |
| 20 | Cost Analysis | Measured costs + per-feature model + 4-tier projections + optimizations | Real numbers + rigorous methodology |

---
---

# ROUND 3 OF 3: Production Hardening, Scale & Meta-Strategy

---

## Q21: With 5 codebases and 850K+ LOC in Qdrant, how do you handle re-indexing when you improve the chunking algorithm? Re-embedding 850K LOC costs ~$10 and takes ~8 minutes.

Chunking quality is the #1 priority. You'll iterate on the chunker multiple times during the sprint. Each iteration potentially requires re-embedding everything.

### Answer A: Full re-index every time — delete collection, re-ingest everything

**Pros:** Guaranteed consistency. No stale vectors from old chunking logic. Simple to implement: `qdrant.delete_collection()` then `ingest_all()`. You know exactly what's in the index.

**Cons:** $10 and 8 minutes per iteration. During a 5-day sprint with 5-10 chunking iterations, that's $50-100 and 80 minutes of waiting. The waiting time is worse than the cost — 8 minutes of idle time per iteration breaks your flow state.

### Answer B: Selective re-indexing per codebase — only re-ingest the codebase whose chunker changed

**Pros:** When you improve the COBOL chunker, only re-ingest GnuCOBOL and OpenCOBOL (~215K LOC, ~2 minutes, ~$2.50). Leave LAPACK/BLAS/gfortran untouched. The `codebase` metadata field makes selective deletion trivial: `qdrant.delete(filter={"codebase": "gnucobol"})`. 75% faster and cheaper than full re-index.

**Cons:** Risk of inconsistency if you also change the shared embedding logic. Requires tracking which codebases were last indexed with which chunker version.

### Answer C: Versioned indexing — new collection per chunker version, switch atomically

**Pros:** Create `legacylens_v1`, `legacylens_v2`, etc. Ingest into the new collection while the old one serves queries. Switch the search config to the new collection once ingestion completes. Instant rollback by switching back. Zero downtime during re-indexing.

**Cons:** Doubles storage temporarily (two collections active). More complex deployment config. Qdrant free tier may not have enough storage for two full collections. Over-engineering for a sprint project.

### ✅ RECOMMENDATION: Answer B — Selective re-indexing per codebase

The most common iteration pattern is: improve COBOL chunker → test on GnuCOBOL → improve Fortran chunker → test on BLAS (smallest). Selective re-indexing by codebase is the 80/20 solution: add a `delete_codebase(name)` function that removes all vectors with matching `codebase` metadata, then re-ingest only that codebase. Cost: ~$2.50 and 2 minutes per codebase-specific iteration vs. $10 and 8 minutes for a full re-index. Add a `legacylens ingest --codebase gnucobol --force` CLI command that handles the delete + re-ingest flow. Track the current chunker version in a metadata field for debugging.

---

## Q22: How do you handle the case where a user queries with a COBOL paragraph name in a Fortran-filtered search (or vice versa)?

Edge case, but graders will test cross-language queries to see how the system handles mismatches.

### Answer A: Return zero results with a helpful message

**Pros:** Honest and transparent. If the user filters by `--codebase lapack` and queries "what does CALCULATE-INTEREST do?", the system should return: "No relevant results found in LAPACK. CALCULATE-INTEREST appears to be a COBOL identifier. Try querying without the codebase filter or with --codebase gnucobol." The suggestion shows the system understands the mismatch.

**Cons:** Requires detecting the mismatch, which means the system needs to know the naming conventions of each language. The suggestion adds complexity.

### Answer B: Silently broaden the search to all codebases

**Pros:** The user's intent is to find CALCULATE-INTEREST. Silently dropping the codebase filter finds it in GnuCOBOL and returns the correct result. The user gets what they wanted.

**Cons:** Violates the principle of least surprise — the user explicitly asked for LAPACK results. Silently ignoring user input is a UX anti-pattern. If the user specifically wants to know if LAPACK has something similar to CALCULATE-INTEREST, broadening defeats their intent.

### Answer C: Return zero results from the filtered codebase, then suggest results from other codebases as a secondary section

**Pros:** Respects the user's filter (shows "0 results in LAPACK") but adds value by showing "Related results from other codebases:" below. This is the Google pattern — "no results for X, did you mean Y?" The user sees both the answer to their literal query and the answer to their likely intent.

**Cons:** Requires a secondary search call. Adds ~200ms latency. The secondary results section adds UI complexity.

### ✅ RECOMMENDATION: Answer C — Respect the filter + suggest alternatives

This is the only answer that doesn't silently violate user intent. Implementation: (1) Run the filtered search, (2) If results are empty or all below threshold, (3) Run an unfiltered search, (4) If unfiltered results exist, show them under "Also found in other codebases:" with the codebase tagged. The secondary search adds ~100ms (Qdrant is fast) and the UI/CLI rendering is 5 lines. This demonstrates thoughtful error handling that graders will notice and appreciate.

---

## Q23: Your demo video needs to showcase all 5 codebases and all 8 features in 3-5 minutes. How do you script this to be compelling without rushing?

The demo is a deliverable and a first impression. Graders watch dozens of these.

### Answer A: Feature-by-feature walkthrough (8 features × 30 seconds each)

**Pros:** Comprehensive coverage. Every feature gets screen time. Easy to script: "Feature 1: Code Explanation. Let me ask..."

**Cons:** Boring. Repetitive structure. Feels like a checklist, not a demo. No narrative. By feature 5, the grader is skimming. 4 minutes of the same pattern = monotony.

### Answer B: Narrative-driven — tell a story of a developer joining a legacy team

**Pros:** "Imagine you're a developer who just joined a financial institution. They have 850,000 lines of COBOL and Fortran. Nobody understands the interest calculation system. Let's use LegacyLens to figure it out." Each feature is introduced as a natural step in the developer's journey: explain the code → map dependencies → find similar patterns → assess impact of a change → generate docs → get translation hints → search for bugs → extract business rules. The narrative makes each feature feel like the natural next question, not a checkbox.

**Cons:** Requires more preparation. The narrative must flow logically. If a live query returns bad results mid-story, the narrative breaks.

### Answer C: Split-screen — web + CLI side by side, show the same query in both interfaces

**Pros:** Demonstrates both interfaces simultaneously. Impressive visual: query in the web UI with streaming results on the left, same query in the CLI with Rich formatting on the right. Shows the system is real infrastructure, not a UI hack.

**Cons:** Split-screen is harder to record. Small text. The grader may not be able to read both sides. Doubles the demo complexity.

### ✅ RECOMMENDATION: Answer B's narrative with Answer C's split-screen for the finale

Script: (1) **Hook — 15s:** "850,000 lines of COBOL and Fortran. Zero documentation. Let's fix that." (2) **Architecture — 30s:** Quick slide showing the 5 codebases → pipeline → answer. (3) **Story: Understanding the code — 45s:** Code Explanation in the web UI. "What does CALCULATE-INTEREST do?" → streaming answer with citations. (4) **Story: Mapping the system — 30s:** Dependency Mapping. "What calls CALCULATE-INTEREST?" → dependency tree. (5) **Story: Cross-language — 30s:** "Show me matrix operations in LAPACK" → results from Fortran codebase. (6) **Story: Finding problems — 30s:** Bug Pattern Search → findings with severity. (7) **Story: Modernization — 20s:** Translation Hints → Python equivalent. (8) **Quick hits — 20s:** Fast cuts of Impact Analysis, Documentation Gen, Business Logic Extract, Pattern Detection. (9) **Split-screen finale — 20s:** Same query, web + CLI side by side. (10) **Metrics — 15s:** "87% precision, 1.2s median latency, 5 codebases, 8 features." Total: ~3.5 minutes. Record on the deployed version, not localhost.

---

## Q24: How do you prevent Render's free tier from spinning down during the grading window?

Render's free tier spins down the web service after 15 minutes of inactivity. The first request after spin-down takes 10-30 seconds to cold start. If the grader hits your URL and waits 30 seconds, they'll assume it's broken.

### Answer A: UptimeRobot — free external ping every 5 minutes

**Pros:** UptimeRobot sends an HTTP request to your health endpoint every 5 minutes, keeping Render alive. Free tier allows up to 50 monitors. Setup takes 2 minutes. Also gives you uptime monitoring and alerts if the service actually goes down.

**Cons:** UptimeRobot itself could have outages. If your health endpoint has a bug, the pings may not prevent spin-down. The health endpoint must actually warm up the application (not just return 200 from a lightweight handler).

### Answer B: GitHub Actions cron job — scheduled workflow every 14 minutes

```yaml
on:
  schedule:
    - cron: '*/14 * * * *'
jobs:
  keepalive:
    runs-on: ubuntu-latest
    steps:
      - run: curl -f https://legacylens.onrender.com/api/health
```

**Pros:** No third-party dependency. Runs in your existing GitHub infrastructure. The cron expression is explicit. The `curl -f` fails on non-200, so you'll see failures in GitHub Actions logs.

**Cons:** GitHub Actions cron is not precise — it may drift by 5-15 minutes. Free tier has limited minutes. You're using CI/CD minutes for a ping.

### Answer C: Both — UptimeRobot as primary, GitHub Actions as backup

**Pros:** Belt and suspenders. If UptimeRobot misses a ping, GitHub Actions catches it. The grading window is non-negotiable — you cannot afford a cold start.

**Cons:** Marginally over-engineered. If UptimeRobot works (and it does, reliably), the backup is unnecessary.

### ✅ RECOMMENDATION: Answer A — UptimeRobot, with the health endpoint warming the full stack

UptimeRobot is battle-tested, free, and takes 2 minutes to set up. The critical detail: your `/api/health` endpoint must actually exercise the stack — not just return 200, but verify Qdrant connectivity and optionally run a lightweight test query. This ensures the entire application stays warm, not just the web process. If you're paranoid, add Answer B as a backup (5 minutes of work), but UptimeRobot alone has worked for thousands of Render deployments.

---

## Q25: For the interview, how do you explain the decision to build ALL 8 features when the spec only requires 4?

The interviewer may challenge this: "The spec says 4. Why did you build 8? Was that the best use of your time?"

### Answer A: "The marginal cost of each additional feature was low because of the shared pipeline"

**Pros:** True — with the config-driven feature architecture (Q5), each additional feature was ~1 hour of prompt writing, not 4 hours of pipeline engineering. 6 features use the same retrieve → rerank → assemble → prompt → generate pipeline with different config objects. Only Pattern Detection and Impact Analysis required custom logic. So the total cost of the additional 4 features was ~6 hours, not 16.

**Cons:** The interviewer may counter: "But those 6 hours could have been spent improving retrieval precision."

### Answer B: "Each feature reinforced the others and improved the demo narrative"

**Pros:** Also true — the 8 features tell a cohesive story: understand → map → detect → assess → document → translate → debug → extract. This narrative makes the demo compelling and shows the system handles the full lifecycle of legacy code understanding. 4 features would make it feel like a checklist. 8 features make it feel like a product.

**Cons:** Narrative value is subjective. The interviewer might prefer depth over breadth.

### Answer C: "I used the time savings from the shared architecture to deliver maximum scope"

**Pros:** This reframes the question: "I didn't sacrifice depth for breadth. The shared pipeline (Q5) meant 6 features were essentially free. The 2 custom features (Pattern Detection, Impact Analysis) were the real engineering challenges, and I allocated proportional time to them. My retrieval precision is >85% — the breadth didn't come at the cost of quality."

**Cons:** Must be backed up by the actual precision numbers.

### ✅ RECOMMENDATION: Answer C, supported by Answer A's specifics and Answer B's narrative

The complete answer structure: "The spec says 4, but my architecture made 8 efficient. [Answer A's specifics]: The config-driven pipeline meant 6 features were ~1 hour each — just prompt templates. Pattern Detection and Impact Analysis were the real engineering work. [Answer C's proof]: My precision is >85%, so the breadth didn't sacrifice quality. [Answer B's narrative]: And the demo tells a complete story — from understanding legacy code to modernizing it. That narrative makes LegacyLens feel like a real product, not a homework assignment." This answer demonstrates: (1) architectural thinking, (2) time management, (3) quality consciousness, and (4) product sense.

---

## Q26: How do you structure your time on Day 1 differently from the original PRD, given you're now targeting all 5 codebases from Day 2?

The MVP still needs to pass all 9 hard gate requirements. But your Day 1 architecture must support the Day 2-3 expansion to 5 codebases without refactoring.

### Answer A: Build for one codebase on Day 1, refactor for multi-codebase on Day 2

**Pros:** Maximum MVP velocity. No unnecessary abstraction on Day 1. Build the simplest pipeline for GnuCOBOL: parse → chunk → embed → store → search → generate. Refactor on Day 2 to add language detection, Fortran support, and multi-codebase metadata.

**Cons:** The refactor costs 2-4 hours on Day 2. If the Day 1 architecture hardcodes COBOL assumptions (paragraph-only chunking, COBOL-specific prompt), the refactor is painful. You're consciously building technical debt.

### Answer B: Build multi-codebase architecture on Day 1, but only ingest GnuCOBOL

**Pros:** The pipeline supports multiple codebases from the start: language detection dispatcher, `codebase` metadata field, configurable preprocessor, generic chunker interface. But you only ingest GnuCOBOL because that's all you need for MVP. On Day 2, adding Fortran codebases is just "implement `fortran_parser.py` and run `ingest --codebase lapack`." Zero refactoring.

**Cons:** The multi-codebase abstraction adds ~2 hours to Day 1. If you don't finish MVP in 24 hours, those 2 hours of abstraction were wasted on a failed gate.

### Answer C: Build for one codebase on Day 1, but with clean interfaces that make Day 2 expansion trivial

**Pros:** Don't build the Fortran parser on Day 1, but DO build the pipeline with these interfaces: `detect_language(file) → str`, `preprocess(file, language) → ProcessedFile`, `chunk(processed, language) → list[Chunk]`. On Day 1, `detect_language` always returns "cobol", `preprocess` only has the COBOL path, `chunk` only does paragraph-based. But the interfaces are already correct for multi-language. On Day 2, filling in the Fortran implementations is trivial because the interfaces exist.

**Cons:** Slightly more upfront design (~30 min) but no wasted implementation effort.

### ✅ RECOMMENDATION: Answer C — Clean interfaces on Day 1, fill implementations on Day 2

This is the professional approach: you don't build features you don't need (no Fortran parser on Day 1), but you design interfaces that accommodate future features. The key decisions to get right on Day 1: (1) Metadata schema includes `codebase` and `language` fields from the start (adds 2 lines to the upsert). (2) The preprocessor takes a `language` parameter (even though it's always "cobol" on Day 1). (3) The search takes an optional `codebase` filter (even though it's never used on Day 1). Total overhead: ~30 minutes of interface design. Savings on Day 2: ~3-4 hours of refactoring. This is the difference between a senior and junior engineer's approach to time-boxed work.

---

## Q27: The social media post is a deliverable. How do you maximize its impact?

This isn't a vanity metric — the spec explicitly requires it. The post reaches the Gauntlet community and potentially recruiters.

### Answer A: Standard project showcase — screenshots + description

**Pros:** Safe. Professional. Shows the working product. "Built LegacyLens — a RAG system for legacy codebases. 5 codebases, 8 features, 850K+ LOC queryable through natural language. @GauntletAI #G4Week3"

**Cons:** Looks like every other project post. No emotional hook. Doesn't stand out in a feed of similar project showcases.

### Answer B: Problem-first narrative — lead with the pain, then reveal the solution

**Pros:** "Imagine joining a company where the critical financial system runs on 850,000 lines of COBOL and Fortran. Nobody understands it. Nobody documented it. And you need to make changes by next quarter. That's the reality for thousands of developers. So I built LegacyLens." This framing makes the reader care before they see the product. Attach a 30-second clip from the demo video showing a query and streaming answer.

**Cons:** Longer post. May feel dramatic. The narrative must be concise for Twitter/X.

### Answer C: Metrics-first — lead with the impressive numbers

**Pros:** "87% retrieval precision. 1.2s median latency. 5 legacy codebases. 8 code understanding features. 850,000+ lines of COBOL and Fortran, now queryable through natural language. Built in 5 days." Numbers are shareable and impressive. Engineers love quantified results. The scope (5 codebases, 8 features) is your differentiator.

**Cons:** Numbers without context feel cold. Not everyone will understand why 87% precision matters.

### ✅ RECOMMENDATION: Answer B for LinkedIn, Answer C for X/Twitter

LinkedIn's algorithm rewards longer, narrative posts. Use Answer B's problem-first structure + a carousel of screenshots + the demo video clip. X/Twitter's format rewards punchy, metric-heavy posts. Use Answer C's numbers-first approach + a 30-second GIF of a live query. Both posts should: (1) tag @GauntletAI, (2) include the deployed URL, (3) include the GitHub repo link, (4) mention the maximalist scope (5 codebases, 8 features, both CLI and web). Post on both platforms for maximum visibility.

---

## Q28: What's the single highest-risk failure mode for the maximalist approach, and how do you mitigate it?

This is the meta-question. The maximalist scope introduces risks that the minimum spec doesn't have.

### Answer A: Risk: Spreading too thin and failing the MVP hard gate

**Pros (as mitigation):** The MVP hard gate requires only 1 codebase, 1 interface, basic search, and deployment. The maximalist scope is all Days 2-5 work. Day 1 is identical whether you're building minimum or maximum — you build GnuCOBOL end-to-end. The risk is that Day 1 work bleeds into Day 2 because you're thinking about multi-codebase architecture instead of shipping MVP. Mitigation: **strict time-boxing on Day 1.** At hour 18, if you don't have a deployed app, drop everything and deploy. The MVP is pass/fail.

**Cons:** Even with mitigation, the cognitive overhead of knowing you'll need multi-codebase support later may cause over-design on Day 1.

### Answer B: Risk: Fortran preprocessing bugs consuming Days 2-3

**Pros (as mitigation):** Fortran has fixed-form vs free-form, continuation lines, COMMON blocks, and implicit typing. The 4 Fortran codebases (gfortran, LAPACK, BLAS, and their variations) may each have preprocessing quirks. Debugging Fortran preprocessing could eat all of Days 2-3, leaving no time for the 8 features. Mitigation: **start with BLAS (smallest, ~20K LOC, pure fixed-form F77).** If BLAS works, LAPACK will work (same format). gfortran is the riskiest (mixed format) — do it last.

**Cons:** Even with BLAS-first, a fundamental Fortran preprocessing bug could block all 4 codebases.

### Answer C: Risk: Retrieval precision drops when mixing 5 codebases in one collection

**Pros (as mitigation):** Adding 4 more codebases dilutes the vector space. The same query that returned 78% precision with GnuCOBOL alone might return 65% when competing with 800K LOC of Fortran. Mitigation: **measure precision after each codebase addition.** Run the evaluation script after adding BLAS (smallest impact), then LAPACK (largest), then gfortran. If precision drops below 75% at any point, stop adding codebases and fix the retrieval before continuing.

**Cons:** The precision measurement takes 10 minutes per run, and you may need multiple tuning iterations.

### ✅ RECOMMENDATION: All three risks are real — mitigate with Answer A's time-boxing + Answer B's ordering + Answer C's incremental measurement

The maximalist approach has a compound risk: any one failure compounds into all others. The mitigation strategy is a checklist:

1. **Day 1:** MVP with GnuCOBOL only. Strict hour-18 deployment deadline. No multi-codebase work.
2. **Day 2 AM:** Add Fortran support starting with BLAS (smallest, simplest). Run eval. Verify precision holds.
3. **Day 2 PM:** Add LAPACK. Run eval. If precision drops, tune hybrid search weights before continuing.
4. **Day 2 EVE:** Add gfortran + OpenCOBOL Contrib. Run eval. This is the riskiest step — if precision tanks, keep the working 3 codebases and document gfortran as "in progress."
5. **Day 3:** Features + docs. Only if all 5 codebases are stable.

The key insight: **the order of codebase addition matters.** Small → large, simple → complex, same-language-as-existing → new-language. Each step is an incremental validation, not a big-bang.

---

## Q29: How do you handle the behavioral interview question "What would you do differently if you had 2 more weeks?"

This question tests self-awareness, product thinking, and engineering maturity. It's almost always asked.

### Answer A: "I'd add more languages — PL/I, Ada, assembly"

**Pros:** Shows ambition. Demonstrates the architecture is extensible. More languages = more value.

**Cons:** Sounds like "I'd do more of the same." Doesn't show deep thinking about what the system currently lacks. Adding languages is incremental, not transformative.

### Answer B: "I'd build a feedback loop — let users rate answers and use that to improve retrieval"

**Pros:** This is the correct production engineering answer. A RAG system without user feedback is flying blind. The feedback loop: user rates answer as helpful/not helpful → log the query, chunks, and rating → use poor ratings to identify chunking failures → use good ratings to expand the ground truth dataset → A/B test retrieval strategies. This shows you understand the production lifecycle beyond "build and deploy."

**Cons:** Feedback loops are complex to build. The answer is forward-looking but not specific enough to this project.

### Answer C: "I'd focus on three things: fine-tuning the embedding model on legacy code, building incremental indexing for codebase updates, and adding a semantic caching layer"

**Pros:** Three specific, high-impact improvements: (1) Fine-tuning Voyage Code 2 on COBOL/Fortran-specific data would measurably improve embedding quality. (2) Incremental indexing (only re-embed changed files) would make the system practical for evolving codebases. (3) Semantic caching (cache similar queries → instant responses) would cut costs 30-50% and reduce latency to near-zero for repeated patterns. Each improvement has clear ROI and demonstrates advanced RAG knowledge.

**Cons:** All three are technically deep — the interviewer might ask follow-up questions you can't answer in depth.

### ✅ RECOMMENDATION: Answer B's production thinking + Answer C's specifics

The optimal answer structure: "Three things. First, **user feedback integration** — right now the system has no way to learn from its mistakes. I'd add a thumbs up/down on each answer, log the query-chunk-rating triples, and use poor ratings to identify chunking and retrieval failures. Second, **incremental indexing** — currently, changing one file requires re-embedding the whole codebase. I'd build a hash-based change detection system that only re-embeds modified files. Third, **semantic caching** — many developers ask similar questions. I'd add an embedding-similarity cache that returns cached answers for queries within 0.95 similarity of a previous query. This cuts latency to near-zero and reduces LLM costs by 30-40%." This answer demonstrates: production thinking (feedback), practical engineering (incremental indexing), and cost optimization (caching). It's the answer a senior engineer gives.

---

## Q30: What's the single most important thing to get right for the maximalist approach specifically?

The original interview said "chunking quality." Does that change when you're building for 5 codebases and 8 features?

### Answer A: Chunking quality — same answer, same reason

**Pros:** The causal chain hasn't changed: chunking → embedding quality → retrieval precision → answer accuracy. With 5 codebases, bad chunking is now a 5x problem instead of a 1x problem. Every codebase that's poorly chunked drags down the entire system's precision. Chunking quality is even MORE important in the maximalist approach because you're running 5 chunkers instead of 1 — each one is a potential failure point.

**Cons:** The maximalist approach introduces new failure modes (multi-codebase mixing, cross-language noise) that chunking alone doesn't address.

### Answer B: The Day 1 architecture decisions — clean interfaces that support Day 2-5 expansion

**Pros:** The maximalist approach lives or dies based on Day 1 architectural choices. If Day 1's code is tightly coupled to COBOL, Days 2-5 are a refactoring nightmare. If Day 1's interfaces are clean and parameterized, Days 2-5 are smooth expansions. The architecture IS the product when you're building at this scope.

**Cons:** Architecture without quality chunking is a well-organized system that produces bad results.

### Answer C: Time management — the discipline to time-box and not let any single component consume the sprint

**Pros:** The maximalist scope has more ways to fail than the minimum scope. You can spend 8 hours perfecting the Fortran preprocessor and not have time for features. You can spend 6 hours on the Next.js UI and not finish the cost analysis. The discipline to say "this is good enough for now, move on" is the meta-skill that determines whether you finish all deliverables or only 60%.

**Cons:** Time management without technical quality produces a complete but mediocre system.

### ✅ RECOMMENDATION: Answer A is the foundation, but Answer C is the meta-answer

Here's the synthesis: **Chunking quality (Answer A) is still the single most important technical decision** — the causal chain is unbroken. But the single most important META-decision for the maximalist approach is **disciplined time-boxing (Answer C)**. Build the best chunker you can in hours 2-7 of Day 1. Then STOP perfecting it and move on. Validate with 5 manual queries. If precision is >60%, it's good enough for MVP — you'll refine on Day 2. The maximalist approach requires you to be simultaneously quality-obsessed (on chunking) and scope-disciplined (on everything else). The chunker gets your best 5 hours. Everything else gets time-boxed. The combination of Answer A's quality focus with Answer C's time discipline is how you ship 5 codebases, 8 features, and 2 interfaces in 5 days without burning out or failing the MVP gate.

---

## Round 3 Summary

| # | Decision | Recommendation | Core Principle |
|---|---|---|---|
| 21 | Re-indexing | Selective per-codebase with metadata delete | Iterate fast on individual chunkers |
| 22 | Cross-language Mismatch | Respect filter + suggest alternatives | Don't silently override user intent |
| 23 | Demo Video | Narrative-driven + split-screen finale | Tell a story, not a feature list |
| 24 | Render Keepalive | UptimeRobot + warm health endpoint | The grader's first impression is non-negotiable |
| 25 | Interview: "Why 8 features?" | Shared architecture + quality proof + product narrative | Architecture enabled breadth without sacrificing depth |
| 26 | Day 1 Architecture | Clean interfaces now, fill implementations later | 30 min of design saves 4 hours of refactoring |
| 27 | Social Media Post | Problem-first (LinkedIn) + metrics-first (X) | Platform-native formats maximize reach |
| 28 | Highest Risk | Compound failure — mitigate with ordering + measurement | Small → large, simple → complex, measure at each step |
| 29 | "What would you change?" | Feedback loop + incremental indexing + semantic cache | Production thinking > feature addition |
| 30 | Most Important Thing | Chunking quality (technical) + time discipline (meta) | Quality-obsessed on the foundation, time-boxed on everything else |

---
---

# MASTER REFERENCE: All 30 Maximalist Recommendations

## Round 1 — Foundation & Multi-Codebase Architecture

| # | Decision | Recommendation |
|---|---|---|
| 1 | Collection Architecture | Single shared collection, `codebase` + `language` indexed metadata |
| 2 | Preprocessor Architecture | Functional: `cobol_parser.py` + `fortran_parser.py` + `parser_utils.py` |
| 3 | Fortran Format Detection | Extension default + heuristic override (check first 20 lines) |
| 4 | Batch Ingestion | Bounded concurrency (`semaphore=2`) + per-codebase progress bars |
| 5 | Feature Architecture | Config-driven for 6 standard features + custom modules for Pattern Detection & Impact Analysis |
| 6 | Hybrid Search Weights | Query-adaptive: identifier queries → 0.6 BM25, semantic queries → 0.7 dense |
| 7 | CLI Architecture | CLI hits deployed API via shared `client.py` module |
| 8 | Translation Hints | Python default, user-selectable target, mandatory accuracy caveat |
| 9 | Next.js Strategy | Full Client Components — ship in 8 hours, not 12 |
| 10 | Ground Truth | Stratified: 15 manual (3/codebase) + 35 LLM-generated, verify 20 |

## Round 2 — Implementation Deep Dive & Feature Engineering

| # | Decision | Recommendation |
|---|---|---|
| 11 | Prompt Architecture | Single parameterized template with language + feature inserts |
| 12 | Dependency Mapping | Static PERFORM/CALL regex during preprocessing → metadata filtering at query time |
| 13 | Pattern Detection | Top-30 hybrid search → LLM-based grouping and labeling |
| 14 | Impact Analysis | Qdrant reverse metadata lookup (direct deps) + LLM indirect impact assessment |
| 15 | Context Budget | Dynamic 5,000 tokens: 2,000 expanded top-1 + 3,000 breadth |
| 16 | Bug Pattern Search | 14-pattern checklist (7 COBOL + 7 Fortran) + LLM severity classification |
| 17 | Streaming | SSE via FastAPI StreamingResponse + `X-Accel-Buffering: no` |
| 18 | Cross-Codebase Scoring | Raw scores default + diversity re-ranking for explicit cross-codebase queries |
| 19 | CLI Structure | Single `main.py` + shared `client.py` + inline Rich rendering |
| 20 | Cost Analysis | Measured dev spend + per-feature model + 4-tier projections + optimization strategies |

## Round 3 — Production Hardening, Scale & Meta-Strategy

| # | Decision | Recommendation |
|---|---|---|
| 21 | Re-indexing | Selective per-codebase via metadata delete + `--force` CLI flag |
| 22 | Cross-Language Mismatch | Respect filter + "Also found in other codebases" section |
| 23 | Demo Video | Narrative hook → architecture → story-driven features → split-screen finale → metrics |
| 24 | Render Keepalive | UptimeRobot with warm health endpoint (verify Qdrant connectivity) |
| 25 | "Why 8 features?" | Shared architecture efficiency + precision proof + product narrative |
| 26 | Day 1 Architecture | Clean multi-codebase interfaces, COBOL-only implementations |
| 27 | Social Media | Problem-first narrative (LinkedIn) + metrics-first punch (X/Twitter) |
| 28 | Highest Risk | Compound failure → mitigate: MVP first, small→large codebases, measure each step |
| 29 | "What would you change?" | User feedback loop + incremental indexing + semantic caching |
| 30 | Most Important Thing | Chunking quality (technical foundation) + time discipline (meta-skill) |

---

> *"The maximalist approach isn't about doing more work — it's about making architectural decisions that make more scope cheap. A shared pipeline that handles 8 features in 340 lines, a single collection that supports 5 codebases with one search call, a config-driven feature system that makes each new feature a 10-line dictionary entry. That's how you build 5 codebases, 8 features, and 2 interfaces in 5 days — not by working harder, but by designing smarter."*
