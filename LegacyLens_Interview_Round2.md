# LegacyLens — Senior Full-Stack Engineer Interview
## Round 2 of 3: Implementation Deep Dive

---

## Question 1: How should you design the prompt template for answer generation over COBOL code chunks?

Prompt engineering is where most RAG systems silently fail. A bad prompt with perfect retrieval still produces garbage answers. COBOL adds a unique challenge: the LLM needs to understand column-based formatting, implicit control flow, and business domain terminology embedded in identifier names.

### Answer A: Minimal prompt — just inject chunks and ask
```
Here is relevant code from the codebase:
{retrieved_chunks}

User question: {query}

Answer the question based on the code above.
```
**Pros:** Fastest to implement. Lets the LLM use its own judgment about how to structure the response. Minimal token overhead means more room for code chunks in the context window. Works well enough for simple factual queries like "where is the main entry point?"
**Cons:** The LLM has no guidance on output format, so responses vary wildly — sometimes it cites file paths, sometimes it doesn't. It may hallucinate details not present in the retrieved chunks. It doesn't know it's looking at COBOL, so it might misinterpret column-based formatting or COBOL-specific syntax (PERFORM, EVALUATE, 88-level items). No instruction to admit when the retrieved context is insufficient, leading to confident wrong answers.

### Answer B: Structured prompt with COBOL-aware system instructions
```
SYSTEM: You are a COBOL code analysis expert helping developers understand
legacy enterprise codebases. You understand COBOL's structure: IDENTIFICATION,
ENVIRONMENT, DATA, and PROCEDURE divisions. You know that paragraphs are
execution units, PERFORM transfers control, and 88-level items are condition
names. Always cite specific file paths and line numbers. If the retrieved
context doesn't contain enough information to answer, say so explicitly.

CONTEXT FORMAT:
Each chunk below includes:
- File path and line range
- Division/Section/Paragraph hierarchy
- The actual code

{retrieved_chunks_with_metadata}

USER QUERY: {query}

INSTRUCTIONS:
1. Answer based ONLY on the provided code context
2. Cite specific file:line references for every claim
3. If the context is insufficient, state what's missing
4. Explain COBOL-specific constructs in plain English
5. Structure: Summary → Detail → References
```
**Pros:** The COBOL-specific system instruction dramatically reduces misinterpretation of language constructs. The structured output format ensures consistent, gradeable responses (always has citations, always admits gaps). The "answer based ONLY on provided context" instruction eliminates hallucination of code that doesn't exist. The metadata format gives the LLM the raw material to generate accurate file/line citations. This prompt design directly satisfies the spec's requirements: code snippets with file/line references, confidence scores, and generated explanations.
**Cons:** More tokens consumed by the system prompt (~200 tokens) means slightly less room for code chunks. The rigid output format can feel robotic for conversational queries. Requires careful chunk formatting to include all the metadata fields the prompt references. Over-constraining the LLM can sometimes reduce the quality of explanatory text.

### Answer C: Multi-step chain-of-thought prompt with self-verification
```
SYSTEM: [Same COBOL-aware instructions as Answer B]

STEP 1 - ANALYZE: Read the provided code chunks carefully. Identify which
chunks are relevant to the user's question and which are noise.

STEP 2 - REASON: For relevant chunks, trace the logic flow. Note any
PERFORM calls, data dependencies, or conditional branches.

STEP 3 - ANSWER: Provide your answer with:
- One-sentence summary
- Detailed explanation with file:line citations
- Confidence level (HIGH/MEDIUM/LOW) based on context coverage
- Related areas the user might want to explore next

STEP 4 - VERIFY: Check your answer against the code. Does every
claim have a supporting code reference? Remove any unsupported claims.
```
**Pros:** Chain-of-thought reasoning produces the most accurate answers, especially for complex queries involving control flow across multiple paragraphs. The self-verification step catches hallucinations before they reach the user. The confidence level directly maps to the spec's "confidence/relevance scores" requirement. The "related areas" suggestion drives engagement and demonstrates deep code understanding.
**Cons:** Significantly more output tokens (2-4x the cost per query). The multi-step process adds 2-5 seconds of latency, potentially blowing your <3 second target. The intermediate reasoning steps are wasted tokens if you're not displaying them to the user. Complexity to implement properly — you need to either parse the structured output or use a single large generation with all steps.

### **RECOMMENDATION: Answer B — Structured prompt with COBOL-aware system instructions**
First principles reasoning: The prompt must serve two masters — the user (who needs clear, accurate answers) and the grading rubric (which checks for file/line references and answer accuracy). Answer B satisfies both without the latency cost of Answer C. The COBOL-specific system instruction is the critical differentiator: without it, the LLM will misparse COBOL code 10-20% of the time (misinterpreting columns, confusing paragraphs with functions, not understanding PERFORM THRU). Answer A is a trap — it works in demos but fails under evaluation. The key insight from Answer C worth borrowing: add the confidence level instruction to Answer B's format. It's one line that adds immense value at negligible token cost. Skip the chain-of-thought reasoning — the latency trade-off isn't worth it when your context window already contains highly relevant pre-ranked chunks.

---

## Question 2: How do you handle COBOL's encoding and preprocessing nightmares before chunking?

COBOL source files from real enterprise systems carry decades of encoding decisions, dead code, copy members, and formatting quirks that will silently corrupt your embeddings if not handled.

### Answer A: Minimal preprocessing — strip columns 1-6 and 73-80, normalize whitespace
**Pros:** Handles the most critical COBOL formatting issue: columns 1-6 (sequence numbers) and 73-80 (identification) are not code and would pollute embeddings. Whitespace normalization handles the mix of tabs/spaces across files. Implementation is 20 lines of Python regex. Gets you to functional chunks in the MVP window. Most legacy code repos on GitHub have already been partially cleaned.
**Cons:** Doesn't handle EBCDIC encoding (mainframe COBOL is natively EBCDIC, not ASCII). Ignores COPY statements (include directives that pull in shared code), meaning referenced copybooks are invisible to your index. Doesn't differentiate between code and comments (column 7 indicator). Dead code and commented-out blocks get embedded as live code, polluting retrieval results.

### Answer B: Full preprocessing pipeline — encoding detection, column parsing, comment extraction, COPY resolution
**Pros:** Encoding detection (chardet/charset-normalizer) handles EBCDIC→UTF-8 conversion automatically. Column-7 indicator parsing correctly separates comments (*), debug lines (D), and continuation lines (-). Extracting comments separately and storing them as metadata enriches your chunks — the embedding gets the code, and the metadata filter can search comments independently. COPY member resolution inlines shared definitions so your index sees the complete program. This produces the cleanest possible input for embedding, maximizing retrieval quality.
**Cons:** COPY member resolution requires you to have the copybook files, which may not be in the repository. Building a proper column parser takes 2-4 hours. Encoding detection is imperfect and may mangle some files. This pipeline has many failure modes that are hard to test without diverse COBOL samples. Significant development time for what is technically a preprocessing step.

### Answer C: Pragmatic middle ground — column stripping + comment separation + encoding handling, skip COPY resolution
**Pros:** Covers the three highest-impact preprocessing steps without the hardest one (COPY resolution). Encoding handling with chardet is a 5-line addition. Comment separation means your embeddings contain only executable code, while comments become searchable metadata — this is a retrieval quality multiplier because developers' queries often match comment language more than code syntax. Column stripping is essential regardless. Total implementation: ~50 lines, 1-2 hours.
**Cons:** Missing COPY resolution means inlined data definitions and shared routines are invisible. Some retrieval failures will be unexplainable until you realize the relevant code was in a copybook. You'll need to document this as a known limitation in your architecture doc's "failure modes" section.

### **RECOMMENDATION: Answer C — Pragmatic middle ground**
First principles reasoning: Preprocessing exists to serve embedding quality, not to achieve perfect parsing. The three biggest ROI preprocessing steps are: (1) column stripping (removes noise), (2) comment separation (enriches metadata), and (3) encoding handling (prevents corruption). Together they eliminate ~80% of preprocessing-related retrieval failures. COPY resolution (Answer B's addition) is the right thing to do in a production system, but for a one-week sprint, the implementation risk exceeds the retrieval benefit — GnuCOBOL's source tree includes its copy members as separate files that get indexed anyway. Document the COPY limitation in your failure modes section; this shows self-awareness that interviewers value. Never ship Answer A — embeddings polluted with sequence numbers and identification columns will measurably degrade your precision.

---

## Question 3: How should you manage the context window when assembling retrieved chunks for the LLM?

You retrieve 5-10 relevant chunks, each 100-500 tokens. Your prompt template consumes ~300 tokens. The LLM needs room to generate a response (~500-1000 tokens). The math matters.

### Answer A: Fixed budget — always pass top-5 chunks, truncate if necessary
**Pros:** Predictable token usage and cost per query. Simple implementation — retrieve 5, format them, send them. No complex logic for deciding what fits. Ensures you always have response generation headroom by capping input size. Easy to reason about performance characteristics.
**Cons:** If chunks are large (500 tokens each), 5 chunks = 2500 tokens of context, which is fine. But if chunks are small (50 tokens), you're wasting context window capacity by not including more relevant information. Truncating large chunks mid-code-block destroys their semantic value. The "always 5" approach doesn't adapt to query complexity — some questions need 2 chunks, others need 15.

### Answer B: Dynamic budget — fill context window to a target utilization
**Pros:** Maximizes the information available to the LLM by dynamically fitting as many chunks as possible within a token budget (e.g., 4000 tokens for context out of 8000 total). Uses a tokenizer (tiktoken) to precisely count tokens per chunk. Adds chunks in relevance order until the budget is exhausted, then includes as much of the next chunk as fits without truncating mid-statement. This approach adapts naturally — short chunks mean more of them, long chunks mean fewer but complete.
**Cons:** Requires a tokenizer dependency (tiktoken for OpenAI, or model-specific tokenizer). More complex implementation — you need token counting, budget tracking, and smart truncation logic. The "partial chunk" edge case is tricky — do you include the first 200 tokens of a 500-token chunk, or skip it entirely? Token counting adds ~5ms of latency (negligible, but adds code paths).

### Answer C: Hierarchical context assembly — include the target chunk plus its surrounding context
**Pros:** When a paragraph-level chunk is retrieved, automatically include the section header, the preceding paragraph, and the following paragraph as additional context. This gives the LLM structural awareness: "this paragraph is in the INPUT-VALIDATION section, preceded by VALIDATE-ACCOUNT and followed by VALIDATE-BALANCE." This is the only approach that supports the spec's "ability to drill down into full file context" requirement. The LLM can trace PERFORM chains across adjacent paragraphs. Produces the most accurate and contextually rich answers.
**Cons:** 3-5x more tokens per retrieved result (you're including surrounding chunks). Fewer distinct results fit in the context window, reducing diversity. Requires chunk adjacency metadata (which chunk comes before/after in the file). Implementation complexity is higher — you need to maintain chunk ordering and file-level grouping. Risk of including too much irrelevant surrounding code that dilutes the signal.

### **RECOMMENDATION: Answer B — Dynamic budget, with hierarchical expansion for top-1 result**
First principles reasoning: Context window management is fundamentally a resource allocation problem. You have a fixed budget (say 6000 tokens for context) and need to maximize the information density within it. Answer B's dynamic approach is the correct general strategy — pack the most relevant chunks in relevance order until the budget is exhausted. But borrow one key idea from Answer C: for the single most relevant chunk, include its surrounding context (parent section header + adjacent paragraphs). This gives the LLM structural context for its primary answer while preserving token budget for diverse supporting evidence from other chunks. Implementation: retrieve top-10, expand top-1 with surrounding context, then fill remaining budget with chunks 2-10 in order. Use tiktoken for precise counting. This hybrid approach maximizes both depth (for the primary answer) and breadth (for supporting evidence).

---

## Question 4: How do you build a ground truth evaluation dataset to measure retrieval precision?

The spec requires >70% retrieval precision in top-5. You can't optimize what you can't measure. But building a ground truth dataset for COBOL code is genuinely hard.

### Answer A: Manually curate 20-30 query/answer pairs from the codebase
**Pros:** Highest quality ground truth — you've read the code and know exactly which chunks should be returned for each query. Can be targeted to cover the spec's testing scenarios (entry points, data modifications, dependencies, I/O operations, error handling). Manual curation forces you to deeply understand the codebase, which pays dividends in the interview. 20-30 pairs is enough for statistically meaningful precision measurements.
**Cons:** Extremely time-consuming — expect 3-5 hours to build a quality dataset of 30 pairs. Requires you to actually understand COBOL well enough to identify correct answers. Subjective bias — you'll unconsciously create queries that your system handles well. The dataset is fragile — if you change your chunking strategy, the "correct" chunk IDs change and you need to re-map ground truth.

### Answer B: LLM-generated evaluation set — have GPT-4 read code and generate questions
**Pros:** Fast — you can generate 50-100 query/answer pairs in 30 minutes. The LLM will generate diverse question types you wouldn't think of. Scalable to larger codebases. Can be regenerated automatically when chunking changes. The generated questions are from a "naive user" perspective, which better represents real usage patterns than your expert-crafted queries.
**Cons:** The LLM may generate questions that don't have clear answers in the code, or questions where multiple chunks are equally correct. Ground truth quality is lower — you need to manually verify at least a subset. The LLM might hallucinate code structures that don't exist in the codebase. Circular reasoning risk: if you use the same LLM for generation and evaluation, biases compound.

### Answer C: Hybrid — manually curate 10 critical pairs, LLM-generate 40 more, manually verify 20 of those
**Pros:** Best of both worlds — your 10 manually curated pairs cover the spec's exact testing scenarios (guaranteed), while the 40 LLM-generated pairs add diversity and coverage. Manual verification of 20 LLM pairs catches the worst hallucinations while keeping time investment reasonable. Total: 30 verified pairs in ~2 hours. The mix of manual and LLM-generated questions also tests different query formulations, which stress-tests your query processing pipeline.
**Cons:** Still requires 2+ hours of investment. The unverified 20 LLM-generated pairs may introduce noise into your precision metrics. Managing two different sources of ground truth adds bookkeeping complexity. You might disagree with the LLM about what constitutes a "correct" chunk for a given query.

### **RECOMMENDATION: Answer C — Hybrid evaluation dataset**
First principles reasoning: Evaluation is a deliverable (the architecture doc requires "performance results" with "actual precision metrics"). You need real numbers, not vibes. The hybrid approach gives you the coverage needed for credible metrics without the time cost of full manual curation. The key insight: your 10 manually curated pairs should map directly to the 6 testing scenarios in the spec plus 4 edge cases (empty results, ambiguous queries, cross-file references, data definition queries). These are the queries the graders will actually test. The LLM-generated pairs round out your dataset to a statistically meaningful N=30+. Store your ground truth as a JSON file in the repo — it doubles as documentation of what your system can and can't do.

---

## Question 5: How should you handle metadata extraction and storage to enable powerful filtering?

Metadata is the unsung hero of RAG precision. The right metadata turns a brute-force similarity search into a targeted, filterable retrieval system.

### Answer A: Minimal metadata — file path and line numbers only
**Pros:** Zero additional processing time. Universally available (every chunk has a file and line range). Enables basic filtering ("search only in file X") and citation ("found in utils.cbl:45-67"). This is all you need for the MVP hard gate requirement of "return relevant code snippets with file/line references."
**Cons:** Can't filter by function name, division, section, or code type. Can't distinguish between data definitions and business logic. Similarity search across the entire codebase means more noise in results. You're ignoring structural information that COBOL gives you for free (division names, section headers, paragraph names).

### Answer B: Rich structural metadata — file path, lines, division, section, paragraph name, code type, dependencies
**Pros:** Enables surgical retrieval: "find paragraphs in the PROCEDURE DIVISION of accounts.cbl" becomes a metadata filter + vector search. Paragraph names become searchable fields — keyword match on `CALCULATE-INTEREST` is 100% precise. Division/section hierarchy supports the drill-down feature. Code type tagging (data definition vs. procedure vs. comment) lets you route queries to the right subset. Dependency metadata (which paragraphs this chunk PERFORMs) enables dependency mapping without a separate graph database.
**Cons:** Extracting all this metadata requires a COBOL structure parser — likely 100-200 lines of regex-based parsing. Dependency extraction (parsing PERFORM and CALL statements) adds complexity. Some metadata fields will be empty for poorly structured code. More metadata means larger payloads in the vector DB, increasing storage costs. The parsing might have bugs that produce wrong metadata, which is worse than no metadata.

### Answer C: Moderate metadata — file path, lines, paragraph/function name, division, chunk type tag
**Pros:** Captures the highest-value structural metadata without the hardest extraction tasks. Paragraph name + division gives you 90% of the filtering power. Chunk type tag (PROCEDURE/DATA/ENVIRONMENT/IDENTIFICATION) is trivially extractable from division headers. No dependency parsing needed — that can be done at query time by the LLM. Implementation: ~50 lines of regex parsing that handles the common cases. Good enough for metadata-based re-ranking (boost paragraph name matches) and filtered search.
**Cons:** Missing dependency information means Dependency Mapping (one of your 4 chosen features) requires runtime analysis rather than pre-computed lookups. No comment content in metadata means you can't do comment-only search. Regex parsing will fail on edge cases in unusual COBOL formatting styles.

### **RECOMMENDATION: Answer C — Moderate metadata**
First principles reasoning: Metadata serves two purposes in this system: (1) enabling filtered search that improves precision, and (2) providing citation information for the answer. Answer C's fields directly serve both: paragraph name enables keyword filtering and citation, division enables query routing, chunk type enables code-vs-data differentiation. The dependency extraction from Answer B is valuable but belongs in a later phase — you can extract PERFORM targets at query time by including them in the prompt and asking the LLM to identify call relationships. This shifts complexity from ingestion (where bugs silently corrupt your entire index) to query time (where bugs are immediately visible and fixable). Ship the moderate metadata for MVP, add dependencies for Final.

---

## Question 6: What's the optimal chunk size for legacy COBOL code, and how should overlap work?

Chunk size directly impacts embedding quality. Too small and you lose context. Too large and the embedding averages over too many concepts, becoming less discriminative.

### Answer A: Small chunks — target 128-256 tokens with 32-token overlap
**Pros:** Small chunks are highly specific — each chunk represents one discrete concept, making embeddings maximally discriminative. More chunks means more potential matches, increasing the chance of finding the exact relevant piece. For COBOL, where a single paragraph might be 10-30 lines of focused logic, this maps well. Overlap ensures no information is lost at boundaries. Embedding models often perform best on shorter inputs where they can capture fine-grained semantics.
**Cons:** Very small chunks lose surrounding context — a 10-line paragraph chunk doesn't tell you what section it's in or what data it operates on. You'll need many more chunks in the context window to provide enough information for answer generation. More chunks = more embeddings = more storage = higher costs. The overhead of metadata per chunk becomes proportionally larger.

### Answer B: Medium chunks — target 512-768 tokens with 128-token overlap
**Pros:** This is the empirically validated sweet spot for most embedding models (including Voyage Code 2 and OpenAI embeddings, which have 512-token optimal input windows). A 512-token COBOL chunk captures an entire paragraph with some surrounding context. Large enough for self-contained semantic meaning, small enough for discriminative embeddings. The 128-token overlap captures context from adjacent paragraphs, helping with queries that span boundaries. Balanced storage costs.
**Cons:** Some COBOL paragraphs are much shorter than 512 tokens — you'll pad them with surrounding code, diluting specificity. Some are much longer — you'll split mid-logic, creating chunks that start or end mid-computation. The fixed target size doesn't adapt to COBOL's variable structure. Overlap means ~20% storage overhead.

### Answer C: Adaptive chunks — use paragraph boundaries with min/max constraints (min 64, max 768 tokens)
**Pros:** Respects COBOL's natural structure — each paragraph becomes one chunk, preserving semantic coherence. The min constraint handles trivially small paragraphs by merging them with neighbors. The max constraint handles monster paragraphs by splitting at statement boundaries (period-terminated sentences in COBOL). This produces the most semantically meaningful chunks because boundaries align with the programmer's original logic structure. No arbitrary splits mid-concept.
**Cons:** Variable chunk sizes mean variable embedding quality — very short chunks (64 tokens) will have weaker embeddings than longer ones. The merging logic (when to combine small paragraphs, which neighbors to merge with) requires heuristic decisions. Max-splitting needs COBOL statement boundary detection (splitting at periods). More complex implementation than fixed-size approaches. Harder to reason about storage requirements and costs upfront.

### **RECOMMENDATION: Answer C — Adaptive chunks with paragraph boundaries**
First principles reasoning: The entire point of syntax-aware splitting (a hard gate requirement) is to align chunks with the code's structural boundaries. COBOL paragraphs ARE those boundaries. Fixed-size chunking (Answers A and B) fundamentally ignores this structure and will produce chunks that split business logic mid-thought. The min/max constraints are essential pragmatism: merge paragraphs under 64 tokens with their predecessor (these are usually `EXIT PARAGRAPH` stubs or single-statement paragraphs), and split paragraphs over 768 tokens at COBOL sentence boundaries (periods). The variable size "concern" is overstated — embedding models handle variable-length inputs natively, and the semantic coherence gain far outweighs any embedding quality variance. Implementation: parse paragraph headers (regex for `[A-Z0-9-]+\.` at the start of a line in PROCEDURE DIVISION), use them as split points, apply min/max merging. ~80 lines of Python.

---

## Question 7: How do you implement the "confidence/relevance score" requirement for retrieved chunks?

The spec requires displaying confidence scores alongside results. This isn't just cosmetic — it's how users know whether to trust the answer.

### Answer A: Raw cosine similarity score from the vector DB
**Pros:** Already computed — the vector DB returns a similarity score with every result. Zero additional computation. Directly reflects how close the query embedding is to the chunk embedding. Values range from 0 to 1 (for cosine similarity), making them intuitive to display. Simple to implement: just pass through the score from the DB response.
**Cons:** Raw similarity scores are poorly calibrated — a score of 0.78 might be excellent for one query and mediocre for another. Users have no intuition for what "0.78 similarity" means. Scores cluster in narrow ranges (most results fall between 0.65-0.85), making it hard to distinguish "great match" from "okay match." If you're using hybrid search, vector and keyword scores are on different scales and can't be naively combined.

### Answer B: Normalized relevance score with thresholds
**Pros:** Map raw scores to meaningful categories: HIGH (>0.85), MEDIUM (0.70-0.85), LOW (<0.70). This gives users actionable confidence information. You can calibrate thresholds using your ground truth dataset — find the score ranges where correct answers typically fall. Include both the category label and the numeric score for transparency. You can also compute an aggregate "answer confidence" based on the distribution of chunk scores — if all 5 chunks are HIGH, the answer is likely reliable.
**Cons:** Threshold calibration requires experimentation and will differ across query types. The thresholds are specific to your embedding model and chunk strategy — they need recalibration if either changes. A static threshold can't account for query-dependent difficulty variations. Still based on embedding similarity, which doesn't directly measure "will this chunk help answer the question."

### Answer C: LLM-assessed relevance — have the LLM rate each chunk's relevance to the query
**Pros:** The most semantically accurate relevance assessment — the LLM understands both the query and the code chunk, and can judge whether the chunk actually answers the question (not just whether it's textually similar). Can provide explanatory confidence: "HIGH — this chunk contains the exact function that handles interest calculation." Catches false positives that embedding similarity misses (chunks that are similar in embedding space but semantically irrelevant). This is what production RAG systems at scale actually do.
**Cons:** Requires an additional LLM call per chunk (or a single call to assess all chunks), adding significant latency (1-3 seconds) and cost. Defeats the purpose of having the user see results quickly. The LLM's relevance assessment is itself imperfect and can be wrong. If you're already passing chunks to the LLM for answer generation, this becomes a separate pre-processing step with its own failure modes.

### **RECOMMENDATION: Answer B — Normalized relevance with calibrated thresholds**
First principles reasoning: The confidence score's primary job is user trust calibration — helping the user decide whether to trust the answer. LLM-assessed relevance (Answer C) is the most accurate but the latency cost is prohibitive when your budget is <3 seconds total. Raw scores (Answer A) are meaningless to users. Normalized scores with thresholds (Answer B) hit the sweet spot: they're computed instantly (just a comparison), they're meaningful ("HIGH/MEDIUM/LOW"), and they're calibratable using your ground truth dataset. The calibration process: run your 30 evaluation queries, record the similarity scores of correct vs. incorrect chunks, and set thresholds at the decision boundaries. This process takes 30 minutes and produces a tuned system. Bonus: display both the label and the numeric score, and add an aggregate "answer confidence" that's the mean score of the top-3 chunks. This satisfies the spec and builds user trust.

---

## Question 8: How do you architect the ingestion pipeline for the "10K+ LOC in <5 minutes" throughput target?

Ingestion performance matters because re-indexing is common during development (every chunking change requires full re-ingestion) and in production (codebase updates trigger incremental or full re-indexing).

### Answer A: Sequential processing — read, chunk, embed, store one file at a time
**Pros:** Simplest implementation — a single for-loop over files. Easy to debug because processing is linear and deterministic. Memory usage is minimal (one file in memory at a time). Error handling is straightforward — if a file fails, log and continue. This is your MVP implementation.
**Cons:** Embedding API calls are the bottleneck (network latency per call), and sequential processing means you wait for each call to complete before starting the next. For 10K LOC across 50 files, expect ~200-500 chunks. At ~100ms per embedding API call (single chunk), sequential embedding alone takes 20-50 seconds. Adding file I/O, chunking, and DB upserts, you're looking at 1-2 minutes total — well within the 5-minute target. But at larger scales (100K+ LOC), this breaks down completely.

### Answer B: Batch embedding with concurrent upserts
**Pros:** Most embedding APIs support batch input (Voyage: up to 128 texts per call, OpenAI: up to 2048). A single batch call for 100 chunks takes ~200-500ms instead of 100 × 100ms = 10 seconds. Concurrent vector DB upserts (asyncio or thread pool) overlap network I/O with embedding computation. This is 10-50x faster than sequential for the embedding step. For 10K LOC, total ingestion drops to 10-30 seconds. For 100K LOC, stays under 3 minutes.
**Cons:** Batch API calls have size limits — you need chunking the chunks into batches (meta). Error handling is more complex — one bad chunk in a batch can fail the entire batch. Memory usage scales with batch size. The async/concurrent code adds complexity (though Python's asyncio makes this manageable).

### Answer C: Full parallel pipeline — concurrent file reading, batch embedding, bulk upserts with progress tracking
**Pros:** Maximum throughput — read files concurrently (asyncio file I/O or thread pool), batch embed with maximum batch sizes, bulk upsert to vector DB. Progress tracking (tqdm or custom logging) gives visibility during long ingestion runs. Checkpoint/resume capability means a failure at file 47 of 50 doesn't require restarting from scratch. This is the production-grade approach that handles arbitrarily large codebases. Can ingest 100K+ LOC in under 60 seconds.
**Cons:** Significantly more complex to implement (~200 lines vs. ~50 for sequential). Concurrent file reading adds minimal benefit since file I/O is fast for source code files. The checkpoint logic is overkill for a 50-file codebase. Race conditions in concurrent upserts can cause subtle bugs. Development time: 2-4 hours for a robust implementation.

### **RECOMMENDATION: Answer B — Batch embedding with concurrent upserts**
First principles reasoning: The bottleneck in ingestion is embedding API latency, not file I/O or computation. Batch embedding eliminates this bottleneck by amortizing network round-trips across 50-128 chunks per call. This single optimization gets you from 60-second sequential to 10-second batch, easily meeting the 5-minute target with room to spare. Concurrent upserts are a cheap addition (10 lines of asyncio code) that overlap the remaining I/O. Skip Answer C's full parallel pipeline — the checkpoint/resume and concurrent file reading add complexity that isn't justified for a 50-file codebase. But batch embedding (Answer B) is a must — it's the difference between "ingestion takes a minute" and "ingestion takes 10 seconds," and that iteration speed compounds over a week of development. Implementation: collect all chunks, batch them into groups of 100, embed each batch in one API call, upsert results concurrently.

---

## Question 9: How should you implement the query interface — CLI, web app, or both?

The spec says "CLI or web" — but the choice impacts your demo, interview, deployment, and development velocity differently.

### Answer A: CLI only (Python Click/Typer)
**Pros:** Fastest to build — a CLI query tool is ~50 lines with Click or Typer. No frontend dependencies, no CSS, no JavaScript. Perfect for the 24-hour MVP. You can demo it by screen-sharing a terminal, which actually looks impressive and technical. Easy to script for evaluation (batch-run your 30 ground truth queries). Deployment is a Docker container or a simple pip install.
**Cons:** The "deployed and publicly accessible" requirement is hard to satisfy with a CLI — you'd need to deploy a web terminal (ttyd, Gotty) or a REST API wrapper. Less visually impressive in a demo video (no syntax highlighting, no interactive drill-down). Non-technical stakeholders can't evaluate it. The social media post deliverable is weaker with terminal screenshots vs. a polished web UI.

### Answer B: Web app (Next.js/React frontend + FastAPI backend)
**Pros:** A polished web interface with syntax highlighting, file/line references as clickable links, confidence score badges, and a chat-like query interface is dramatically more impressive in demos and social media posts. Next.js gives you server-side rendering for fast initial load. React enables the drill-down feature (click a result to see full file context). The frontend can display code with COBOL syntax highlighting (Prism.js or highlight.js). This is what the graders will interact with — first impressions matter.
**Cons:** Frontend development is a significant time investment (8-16 hours for a polished UI). CSS, layout, responsiveness, error states, loading indicators — all take time. Two codebases to deploy and maintain (frontend + backend). If your retrieval isn't great, a pretty UI makes bad results MORE obvious, not less. The frontend can become a time sink that steals time from retrieval quality.

### Answer C: Minimal web app (single-page FastAPI with Jinja2 templates)
**Pros:** One codebase, one deployment, one language (Python). Jinja2 templates produce functional HTML with zero JavaScript framework overhead. You can add syntax highlighting with a CSS-only library (highlight.js CDN). A form input + results display is ~100 lines of HTML template. Deploys as a single service on Render/Railway. Development time: 2-4 hours for a functional, presentable interface. Meets the "deployed and publicly accessible" requirement with minimal effort.
**Cons:** No interactivity — no streaming responses, no dynamic drill-down, no client-side filtering. The UI will look utilitarian, not polished. Limited by what server-rendered HTML can do. If you want to add features later (typeahead suggestions, result filtering), you'll need to refactor to a proper frontend framework.

### **RECOMMENDATION: Answer C for MVP, upgrade to Answer B for Final**
First principles reasoning: Time allocation is the core decision here. The spec's hard gate is "basic RAG pipeline working" — not "beautiful web interface." Answer C gives you a functional, deployed, publicly accessible interface in 2-4 hours, leaving maximum time for retrieval quality, chunking refinement, and evaluation. For the Final gate (Wednesday/Sunday), upgrade to a Next.js frontend if and only if your retrieval precision is >70% and your 4 code understanding features are working. A beautiful UI on top of bad retrieval is worthless. A simple UI on top of excellent retrieval passes every gate and impresses in the interview. The CLI (Answer A) is your development tool regardless — use it for batch evaluation and debugging. But don't ship it as the deployed interface.

---

## Question 10: How do you structure your cost analysis to be both accurate and impressive?

The cost analysis is a required deliverable. It needs to cover development costs AND production projections at 100/1K/10K/100K users. This is your chance to demonstrate production thinking.

### Answer A: Simple spreadsheet with per-API pricing math
**Pros:** Straightforward to build — list each API (embedding, LLM, vector DB), their per-unit costs, and multiply by volume. Clear and verifiable. Quick to produce (30-60 minutes). Shows you understand the cost components. Easy to present in a table format that matches the spec's template.
**Cons:** Doesn't account for caching, batching optimizations, or tiered pricing. Doesn't model how costs change with user behavior patterns. The projections look like napkin math, not engineering analysis. Doesn't differentiate between fixed costs (vector DB hosting) and variable costs (API calls per query).

### Answer B: Detailed cost model with assumptions, variable costs, and optimization strategies
**Pros:** Model with explicit assumptions: queries/user/day (3-5), average tokens/query (2000 input + 500 output), embedding costs for codebase updates (monthly re-index), vector DB storage scaling. Separate fixed costs (hosting, DB) from variable costs (API calls). Include cost optimization strategies: embedding cache hit rates, LLM response caching for common queries, cheaper model routing for simple queries. Show the math for each tier. This demonstrates you can think about unit economics.
**Cons:** Takes 2-3 hours to build thoroughly. Some assumptions are guesswork without real user data. Optimization strategies are theoretical without implementation. Risk of over-engineering a deliverable that's one of seven.

### Answer C: Cost model with dual-track analysis (current stack vs. optimized stack)
**Pros:** Show two scenarios: (1) current implementation costs (GPT-4o, Voyage Code 2, Qdrant Cloud) and (2) optimized production costs (GPT-4o-mini for simple queries, cached embeddings, reserved capacity pricing). This demonstrates architectural thinking — you're not just reporting costs, you're proposing how to reduce them. Include a break-even analysis: at what user count does self-hosting the vector DB beat cloud pricing? At what query volume does an embedding cache pay for itself? This is the kind of analysis that gets you promoted at an actual company.
**Cons:** Most complex to build (3-4 hours). Requires knowledge of reserved pricing, self-hosting costs, and caching infrastructure. Some analysis may be speculative. Risk of spending too much time on the cost doc vs. the actual system.

### **RECOMMENDATION: Answer B — Detailed cost model with assumptions and optimization strategies**
First principles reasoning: The cost analysis deliverable exists to test whether you think about production viability, not whether you can build a financial model. Answer B hits the target: explicit assumptions (auditable), separated fixed/variable costs (correct framing), and optimization strategies (forward thinking). Answer C's dual-track analysis is impressive but the time investment isn't justified when you have 6 other deliverables. The key to a strong cost analysis: be specific about your assumptions and conservative in your projections. A cost analysis that says "GPT-4o at $10/1M output tokens × 5 queries/user/day × 500 output tokens/query × 100K users = $250K/month, mitigated by response caching (est. 40% hit rate) = $150K/month" is far more credible than vague estimates. Track your actual development spend using your API dashboards and include real numbers — this is the easiest differentiator since most students will estimate rather than measure.

---

## Summary of Round 2 Recommendations

| # | Decision | Recommendation | Core Principle |
|---|----------|---------------|----------------|
| 1 | Prompt Template | Structured COBOL-aware with confidence | Reduce hallucination, ensure citations |
| 2 | Preprocessing | Column strip + comment separation + encoding | 80/20 — highest ROI preprocessing |
| 3 | Context Window | Dynamic budget + hierarchical expand top-1 | Maximize depth + breadth |
| 4 | Evaluation Dataset | Hybrid: 10 manual + 20 verified LLM-generated | Credible metrics in 2 hours |
| 5 | Metadata | File path + lines + paragraph name + division + type | Enables filtering without over-engineering |
| 6 | Chunk Size | Adaptive paragraph-based (64-768 tokens) | Align chunks with code structure |
| 7 | Confidence Scores | Normalized with calibrated thresholds | User trust at zero latency cost |
| 8 | Ingestion Pipeline | Batch embedding + concurrent upserts | 10x throughput for one optimization |
| 9 | Query Interface | FastAPI + Jinja2 MVP → Next.js for Final | Time on retrieval > time on UI |
| 10 | Cost Analysis | Detailed model with real dev spend + projections | Specific assumptions + measured data |

---

*Round 3 will cover production hardening, failure modes, edge cases, interview-specific questions, and the meta-strategy for maximizing your overall score across all deliverables.*
