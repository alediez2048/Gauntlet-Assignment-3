# LegacyLens — Senior Full-Stack Engineer Interview
## Round 3 of 3: Production Hardening, Failure Modes & Meta-Strategy

---

## Question 1: What happens when retrieval returns nothing relevant — how do you handle zero-result and low-confidence queries gracefully?

This is the failure mode graders will test first. They'll ask something the codebase doesn't contain and see if your system hallucinates or admits its limitation.

### Answer A: Return a generic "no results found" message
**Pros:** Honest and safe — never produces a hallucinated answer for an unanswerable query. Simple to implement: if top similarity score < threshold, return the static message. Zero risk of confidently wrong answers. Takes 5 minutes to implement.
**Cons:** Terrible user experience — the user gets no guidance on why the search failed or what to try instead. Doesn't distinguish between "the codebase doesn't contain this" and "your query was too vague." Makes the system feel dumb rather than helpful. Graders will note the lack of graceful degradation.

### Answer B: Tiered degradation — low-confidence results with caveats, then suggestions
**Pros:** When similarity scores are below the HIGH threshold but above a floor (e.g., 0.50), show results with an explicit caveat: "These results may not directly answer your question. Confidence: LOW." When scores are below the floor, show no results but suggest query reformulations: "I couldn't find relevant code. Try searching for specific COBOL paragraph names, data names, or rephrase your question." This keeps the user engaged and guides them toward successful queries. The LLM can generate suggestions based on the original query and the index's metadata (list of known paragraph names, file names).
**Cons:** The threshold calibration between "show with caveat" and "don't show" requires tuning. Suggestion generation adds an LLM call even on failed queries (latency + cost). The caveat text needs to be carefully worded to not undermine trust in high-confidence results.

### Answer C: Fallback to keyword search when vector search fails
**Pros:** If semantic search returns no relevant results, automatically fall back to a keyword search across the raw codebase. This catches queries for specific identifiers (COBOL paragraph names, variable names, file names) that embedding models fail to match. The fallback is transparent to the user: "Semantic search found no matches. Showing keyword results instead." This leverages hybrid search architecture you've already built. Significantly reduces the zero-result rate.
**Cons:** Keyword results without semantic ranking can be noisy — searching for "CUSTOMER" might return 200 matches. The transition between semantic and keyword results might confuse users. Requires maintaining a keyword index alongside the vector index (already part of the hybrid search recommendation). The fallback might mask embedding quality issues that you should fix instead.

### **RECOMMENDATION: Answer B + the fallback concept from Answer C**
First principles reasoning: Failure handling IS the product for edge cases. Implement tiered degradation: (1) if top-5 scores are all HIGH, show normally; (2) if scores are MEDIUM, show with a "partial match" indicator; (3) if scores are LOW, trigger hybrid keyword fallback (Answer C); (4) if keyword search also fails, show the helpful "no results + suggestions" message (Answer B). This four-tier approach means users almost always get something useful. The suggestion generation is lightweight — pull from a pre-computed list of indexed paragraph names and file paths, match against query keywords, suggest the closest. No LLM call needed. Document this tiered approach in your failure modes section — it directly demonstrates production thinking.

---

## Question 2: How do you handle queries that span multiple files or modules — cross-cutting concerns in legacy code?

"Show me all error handling in this codebase" or "What functions modify CUSTOMER-RECORD?" require aggregating results across files. This is where naive top-5 retrieval breaks down.

### Answer A: Standard top-k retrieval across all files, let the LLM synthesize
**Pros:** If your embeddings are good and your chunks are well-constructed, top-10 retrieval will naturally pull chunks from multiple files that relate to the query. The LLM is excellent at synthesizing patterns across multiple code snippets: "Error handling appears in three patterns: (1) file status checks in IO-MODULE, (2) numeric validation in VALIDATE-INPUT, (3) general error paragraphs in ERROR-HANDLING." This requires zero special handling — your existing pipeline does this.
**Cons:** Top-k retrieval is biased toward the most similar chunks, which may cluster in one file. "Show me ALL error handling" requires exhaustive retrieval, but top-10 only samples. If the codebase has 15 error handling paragraphs across 8 files, top-10 might find 6 of them — the user gets a partial picture without knowing it's partial. The LLM can only synthesize what it receives; it can't know what was missed.

### Answer B: Query decomposition — split the query into sub-queries, run each, merge results
**Pros:** The LLM decomposes "what functions modify CUSTOMER-RECORD" into: (1) "CUSTOMER-RECORD definition" (find the data definition), (2) "MOVE to CUSTOMER-RECORD" (find write operations), (3) "READ into CUSTOMER-RECORD" (find I/O operations), (4) "PERFORM paragraphs that reference CUSTOMER-RECORD" (find indirect modifications). Each sub-query retrieves its own top-5, results are merged and deduplicated. This dramatically improves recall for cross-cutting queries. Each sub-query is more specific, so individual precision is higher.
**Cons:** An LLM call for decomposition adds 500-1500ms latency before retrieval even starts. Multiple retrieval passes (4 sub-queries × top-5 each) means 4x the vector DB queries and 4x the embedding generation. The decomposition may generate irrelevant sub-queries. Merging and deduplicating results from multiple passes requires custom logic. Total latency could hit 5-8 seconds, blowing the <3 second target.

### Answer C: Metadata-filtered aggregation — use filters to collect all chunks matching criteria
**Pros:** For queries about specific data items ("what modifies CUSTOMER-RECORD"), use metadata filtering to find all chunks that reference that identifier, then run vector similarity within that filtered set. For pattern queries ("show all error handling"), use chunk-type metadata filtering to find all chunks tagged as "error handling" or containing error-related keywords. This is a targeted scan, not a brute-force retrieval. Qdrant's payload filtering makes this efficient — filter on metadata first, then rank by vector similarity within the filtered set.
**Cons:** Requires rich metadata (specifically, which data items each chunk references) that may not have been extracted. Metadata-based approaches can't handle abstract concepts ("show me code that's hard to maintain") that don't map to filterable fields. The metadata filter may be too broad (too many results) or too narrow (misses relevant chunks) depending on extraction quality.

### **RECOMMENDATION: Answer A for MVP, Answer C for Final**
First principles reasoning: Cross-file queries are the hardest category for any RAG system, and over-engineering the solution risks blowing your timeline. For the MVP, standard top-k retrieval (Answer A) handles the common case: 70-80% of cross-file queries will naturally pull results from multiple files because the embedding space groups thematically similar code regardless of file location. For the Final gate, add metadata-filtered aggregation (Answer C) specifically for the "what modifies X" query pattern — this is the testing scenario most likely to trip up basic retrieval. Query decomposition (Answer B) is intellectually elegant but the latency cost makes it impractical for a system targeting <3 second response times. The honest answer for your architecture doc: "Cross-file queries work well for thematic retrieval (error handling patterns) but have reduced recall for exhaustive enumeration (every modification of a specific variable). This is documented as a known limitation with a roadmap to metadata-filtered aggregation."

---

## Question 3: How do you handle the COBOL COPY statement problem — code that references definitions not in the current file?

COBOL's COPY statement is like #include in C — it pulls in shared code from external files (copybooks). A program might COPY the customer record definition, meaning the actual data layout is in a separate .cpy file, not the .cbl file the user is querying about.

### Answer A: Index copybooks as separate files, rely on retrieval to connect them
**Pros:** If copybooks (.cpy files) are in the repository, they get indexed like any other file. When a user asks "what fields are in CUSTOMER-RECORD," the copybook chunk containing the record definition should be retrieved by semantic similarity. No special handling needed — the retrieval pipeline treats all files equally. This is the simplest approach.
**Cons:** The user queries "what does PROCESS-CUSTOMER do?" and gets the paragraph from program.cbl, but the answer depends on the CUSTOMER-RECORD layout defined in customer.cpy. The LLM doesn't know these are connected unless both chunks are retrieved. The COPY statement in the code ("COPY CUSTOMER-RECORD") is just a reference — the actual definition is elsewhere. If the retrieval doesn't return the copybook chunk alongside the program chunk, the LLM gives an incomplete or wrong answer.

### Answer B: Resolve COPY statements during preprocessing — inline the copybook content
**Pros:** After inlining, each program file contains its complete data definitions and shared routines. Chunks from this program include the full context. The retrieval pipeline works as if the program were self-contained. No cross-file dependency at query time. This is how COBOL compilers work — they inline COPY members before compilation.
**Cons:** Inlining duplicates content — if 10 programs COPY the same record, that record is embedded 10 times. Storage and embedding costs increase proportionally. If a copybook is updated, you need to re-inline and re-index every program that uses it. The inlining process requires finding copybook files (they may be in different directories with non-standard naming). Implementation complexity is moderate (30-60 minutes if copybook paths are predictable).

### Answer C: Metadata linking — store COPY references as chunk metadata, expand at query time
**Pros:** During preprocessing, parse COPY statements and record which copybooks each program references. Store these as metadata: `{"copy_members": ["CUSTOMER-RECORD", "ACCOUNT-LAYOUT"]}`. At query time, when a chunk is retrieved that has COPY references, automatically fetch the referenced copybook chunks and include them in the context. This is a lazy resolution strategy — only resolve what's needed, when it's needed. No duplication, no inlining, minimal preprocessing complexity.
**Cons:** Requires parsing COPY statements during preprocessing (regex for `COPY [A-Z0-9-]+`). Requires a lookup mechanism to map copybook names to chunk IDs. The query-time expansion adds latency (additional vector DB lookups). If copybook names don't match file names (common in enterprise COBOL), the lookup fails. More complex implementation than either alternative.

### **RECOMMENDATION: Answer A for MVP, Answer C for Final**
First principles reasoning: This is a classic build-vs-optimize decision. For the MVP hard gate, indexing copybooks as separate files (Answer A) works because: (1) GnuCOBOL's source tree includes .cpy files that will be indexed, (2) queries about data definitions will retrieve the copybook chunks via semantic similarity, and (3) the LLM can often infer the connection from the COPY statement in the retrieved code. The failure mode is real but bounded — it only manifests when the user asks about code that depends on a copybook AND the copybook chunk isn't retrieved. Document this as a known limitation. For the Final gate, implement metadata linking (Answer C) — it's the architecturally correct solution that resolves dependencies without duplication. Skip Answer B (inlining) because content duplication wastes embedding budget and pollutes similarity search with near-duplicate vectors.

---

## Question 4: What's your testing strategy to validate that the entire pipeline works end-to-end before the demo?

The demo video is a deliverable. If the system breaks during recording, you don't have a submission.

### Answer A: Manual testing — run 10 queries, eyeball the results
**Pros:** Fast — 15 minutes to run queries and check outputs. Tests the actual user experience including UI rendering, latency feel, and answer quality. You'll naturally discover UX issues (formatting bugs, missing line numbers, error states) that automated tests miss. Covers the exact queries from the spec's testing scenarios.
**Cons:** Not reproducible — you can't re-run the same test after code changes to verify nothing regressed. Subjective evaluation — "this looks right" isn't a precision metric. You might unconsciously avoid queries that you know will fail. Doesn't test edge cases (empty results, very long queries, special characters).

### Answer B: Automated evaluation script — run ground truth queries, compute precision@5
**Pros:** Reproducible and quantifiable — run the script after every change and get a precision number. Catches regressions immediately. Tests against your 30-query ground truth dataset. Can be run in CI or as a pre-demo smoke test. Produces the actual metrics you need for your architecture doc's "Performance Results" section. Takes 20 minutes to build, saves hours of manual testing.
**Cons:** Only tests retrieval precision, not answer quality (the LLM's explanation might be wrong even with correct chunks). Doesn't test UI rendering or UX. Requires ground truth maintenance. Doesn't catch latency issues or timeout errors.

### Answer C: End-to-end test suite — automated queries through the API with assertion on response format
**Pros:** Tests the complete stack: API endpoint → query processing → retrieval → context assembly → LLM generation → response formatting. Asserts on response structure (has file paths, has line numbers, has confidence score, response time < 3 seconds). Catches integration bugs between components. Can test error cases (invalid queries, empty input, very long input). This is what production systems have.
**Cons:** Most complex to build (2-4 hours for comprehensive coverage). Requires the full stack to be running (vector DB, embedding API, LLM API). Flaky tests from API timeouts or LLM non-determinism. Over-engineering for a one-week project — the maintenance cost exceeds the benefit.

### **RECOMMENDATION: Answer B + a targeted subset of Answer A**
First principles reasoning: You need two things: (1) a quantitative metric for your architecture doc (precision@5), and (2) confidence that the demo won't break. The automated evaluation script (Answer B) gives you #1 and catches retrieval regressions. Targeted manual testing (the 6 specific testing scenarios from the spec) gives you #2 and validates the user experience. Together they take 45 minutes to build and 10 minutes to run. Skip Answer C's full test suite — the investment doesn't pay off in a one-week sprint. The evaluation script is your highest-leverage testing investment: `python evaluate.py` → "Precision@5: 73.3% (22/30 queries with majority relevant chunks)." That number goes directly into your architecture doc and demo video.

---

## Question 5: How do you optimize for the <3 second query latency target when your pipeline has 4+ network calls?

A typical query path: embed query (100-200ms) → vector search (50-200ms) → re-ranking (100-300ms) → LLM generation (1000-3000ms). That's 1250-3700ms total. You're right at the edge.

### Answer A: Optimize the LLM call — use streaming + shorter prompts
**Pros:** The LLM call dominates latency (60-80% of total). Streaming the response means the user sees the first token in 500-800ms even if full generation takes 3 seconds — the perceived latency drops dramatically. Shorter prompts (fewer chunks, more concise system instructions) reduce time-to-first-token. Using GPT-4o-mini for simple queries (detected via query classification) cuts LLM latency by 50-70%. These optimizations require minimal code changes.
**Cons:** Streaming requires WebSocket or SSE support in your frontend — significant if you're using Jinja2 templates. Shorter prompts mean less context for the LLM, potentially reducing answer quality. GPT-4o-mini's quality drop is noticeable for complex questions. Query classification (simple vs. complex) is another model call or heuristic that adds complexity.

### Answer B: Parallelize embedding and metadata lookup
**Pros:** The query embedding and metadata preprocessing (keyword extraction, query classification) can run concurrently — they're independent operations. If you cache the embedding model's tokenizer, you can compute token counts and metadata while waiting for the embedding API response. This saves 50-100ms — small but meaningful when you're at the margin. Implementation: Python asyncio with `asyncio.gather()`.
**Cons:** The actual savings are modest — 50-100ms when your budget is 3000ms. Adds async complexity to the query path. The biggest bottleneck (LLM generation) is still sequential and can't be parallelized with retrieval (it depends on retrieval results).

### Answer C: Implement an embedding cache for repeated/similar queries
**Pros:** If users ask the same question (or very similar questions), you can cache the query embedding and even the full response. An LRU cache with 1000 entries covers the most common queries. Cache hit eliminates the embedding API call (100-200ms saved) AND can skip retrieval + LLM entirely if you cache full responses. For repeated queries during development and evaluation, this makes the system feel instant. In production, common queries ("where is the main entry point?") will cache quickly.
**Cons:** Similar (but not identical) queries produce different embeddings, so exact-match caching has limited hit rates in production. Response caching means users don't get fresh results if the index is updated. Cache invalidation on index updates adds complexity. Memory usage for 1000 cached embeddings is ~6MB (negligible).

### **RECOMMENDATION: Answer A — Streaming + model routing, supplemented by Answer C's embedding cache**
First principles reasoning: The <3 second target is about *perceived* latency, not actual computation time. Streaming (Answer A) transforms a 3-second wait into a 500ms wait followed by progressive text rendering — this fundamentally changes the user experience even if total computation time is unchanged. Implementing streaming in FastAPI is straightforward: `StreamingResponse` with SSE events. For the Jinja2 MVP, you don't even need real streaming — just measure actual latency; if it's under 3 seconds without streaming, you're fine. The embedding cache (Answer C) is a 10-line addition (`functools.lru_cache` on the embedding function) that eliminates redundant API calls during development and evaluation. Model routing (GPT-4o-mini for simple queries) is a nice-to-have for the Final gate but not necessary if your total pipeline latency is under 3 seconds.

---

## Question 6: How should you structure your GitHub repository to maximize your evaluation score?

The repo is a deliverable. Its structure, README, and documentation contribute to the graders' impression of your engineering quality.

### Answer A: Flat structure — all Python files in root, README with setup instructions
**Pros:** Fast to set up, no time spent on project organization. Everything is findable because it's all in one place. No import path issues. Works fine for a small project.
**Cons:** Signals junior engineering — no separation of concerns, no clear architecture. Graders looking at the repo see `app.py`, `ingest.py`, `search.py`, `utils.py` all at the top level. Doesn't scale if you add features. The README is doing all the heavy lifting for understanding the codebase.

### Answer B: Clean modular structure with documented architecture
```
legacylens/
├── README.md              # Setup, architecture overview, deployed link
├── docs/
│   ├── architecture.md    # RAG architecture doc (required deliverable)
│   ├── cost-analysis.md   # AI cost analysis (required deliverable)
│   └── pre-search.md      # Pre-search document (required deliverable)
├── src/
│   ├── ingestion/
│   │   ├── parser.py      # COBOL preprocessing & chunking
│   │   ├── embedder.py    # Embedding generation (batch)
│   │   └── indexer.py     # Vector DB ingestion
│   ├── retrieval/
│   │   ├── search.py      # Hybrid search (vector + keyword)
│   │   ├── reranker.py    # Metadata + cross-encoder re-ranking
│   │   └── context.py     # Context window assembly
│   ├── generation/
│   │   ├── prompts.py     # Prompt templates
│   │   └── llm.py         # LLM client wrapper
│   └── api/
│       ├── app.py         # FastAPI application
│       └── templates/     # Jinja2 templates
├── evaluation/
│   ├── ground_truth.json  # 30-query evaluation dataset
│   └── evaluate.py        # Precision measurement script
├── data/                  # Target codebase (gitignored if large)
├── .env.example           # Required env vars template
├── requirements.txt
├── Dockerfile
└── docker-compose.yml     # App + Qdrant
```
**Pros:** The structure IS the architecture diagram. Any grader can understand the system by reading the directory tree. Separation into ingestion/retrieval/generation mirrors the RAG pipeline stages. The evaluation directory shows you measure quality. The docs directory contains all three required documents. Docker support signals production readiness. `.env.example` shows you handle secrets properly.
**Cons:** Takes 30-60 minutes to set up properly. Import paths need management (relative imports, `__init__.py` files). Moving fast during development is slightly slower when you need to create files in the right directories.

### Answer C: Monorepo with frontend and backend separation
```
legacylens/
├── backend/         # FastAPI + RAG pipeline
├── frontend/        # Next.js web app
├── shared/          # Shared types/configs
├── docs/
├── evaluation/
└── infrastructure/  # Docker, deployment configs
```
**Pros:** Clean separation between frontend and backend if you implement a full web app. Each part has its own dependency management. Mirrors professional repository structures. Independent deployment of frontend and backend.
**Cons:** Over-architected for this project scope. Two package managers (pip + npm), two build processes, two Docker images. The overhead of maintaining separate codebases is not justified for a one-week sprint where you're the only developer. If you go with the Jinja2 MVP (recommended), you don't need this split.

### **RECOMMENDATION: Answer B — Clean modular structure**
First principles reasoning: Your repository is evaluated by humans who will spend 2-5 minutes forming an impression. Answer B's structure communicates "this person thinks in systems" without a single line of code being read. The directory tree maps directly to the RAG pipeline discussed in the architecture doc, creating consistency across deliverables. The evaluation directory is a differentiator — most students won't include one. The Dockerfile and docker-compose.yml signal that deployment isn't an afterthought. This structure takes 30 minutes to set up at project start and pays dividends in code organization, evaluation impression, and your own development velocity (you always know where code goes). Skip Answer C unless you're building a React frontend — the separation adds complexity with no benefit for a single-backend project.

---

## Question 7: How do you prepare for the behavioral interview questions about ambiguity, failure, and pressure?

The spec explicitly lists behavioral topics: handling ambiguity, pivoting on failure, self-learning, and pressure management. These aren't throwaway questions — they gate Austin admission.

### Answer A: Prepare scripted answers for each topic
**Pros:** You have polished, concise answers ready for predictable questions. No fumbling or rambling. Can be practiced until delivery is smooth. Covers the known topics.
**Cons:** Scripted answers sound scripted — experienced interviewers detect rehearsed responses immediately. Doesn't handle follow-up questions or unexpected angles. If the interviewer asks something outside your scripts, the contrast between rehearsed and unrehearsed answers is stark. Comes across as performative rather than reflective.

### Answer B: Map each behavioral topic to a specific moment from your LegacyLens build
**Pros:** Every answer is grounded in the actual project — "When I was building the chunking pipeline and my paragraph parser failed on GnuCOBOL's non-standard formatting, I had to pivot from regex to a different parsing approach within 4 hours of the MVP deadline." These answers are authentic, specific, and impossible to fake. They demonstrate self-awareness AND technical depth simultaneously. The interviewer can ask follow-ups and you'll have answers because you actually lived it. This is what the behavioral questions are designed to surface — your process under real constraints.
**Cons:** Requires you to actually document your decision points, failures, and pivots during the build week. If the build goes smoothly (unlikely), you may lack compelling stories. Requires reflective thinking in real-time during development.

### Answer C: Use the STAR framework (Situation, Task, Action, Result) for each answer
**Pros:** STAR provides structure that prevents rambling and ensures you cover all parts of the story. Interviewers trained in structured behavioral interviewing expect STAR-format answers. Forces you to articulate results, not just actions. Widely recommended and proven effective.
**Cons:** STAR can feel formulaic — experienced interviewers hear hundreds of STAR answers. The structure can constrain naturally flowing conversation. Not all situations map neatly to STAR's linear narrative.

### **RECOMMENDATION: Answer B, delivered with Answer C's structure**
First principles reasoning: Behavioral interviews assess two things: (1) do you actually learn from experience, and (2) can you communicate that learning clearly. Answer B gives you authentic material (real project moments), and Answer C's STAR structure gives you clear delivery. The synthesis: keep a "decision log" during your build week — every time you make a non-obvious choice, hit a wall, or change direction, jot down a one-line note. At interview prep, map your best stories to the behavioral topics. Example: "Ambiguity → choosing between Qdrant and Pinecone when I hadn't used either." "Failure → my first chunking strategy produced 45% precision and I had to rebuild." "Pressure → shipping the MVP at hour 22 with 2 features still incomplete." These stories are your most powerful interview asset because they're true and specific. No one else will have the same stories.

---

## Question 8: What's the optimal time allocation across the one-week sprint to maximize your total score?

You have 7 days, 3 checkpoints (MVP at 24h, G4 Final at 3 days, GFA Final at 5 days), and 7 deliverables. Time management IS the meta-game.

### Answer A: Front-load everything — burn hard on MVP, coast to Final
**Pros:** If you nail the MVP in 24 hours, you have 4-6 days for polish, documentation, and advanced features. The MVP hard gate is pass/fail — failing it means nothing else matters. Going all-in on Day 1 ensures you pass the gate. The remaining days have less pressure, allowing for better quality work.
**Cons:** Burnout risk — 24 hours of intense coding leaves you impaired for the nuanced work (architecture docs, cost analysis, demo video) that follows. If the MVP takes longer than expected (it always does), you have no buffer. The features that differentiate your submission (advanced code understanding, evaluation metrics, polished UI) need focused, fresh-brain effort.

### Answer B: Structured sprint with time-boxed phases
```
Day 1 (MVP - 24h):
  Hours 1-2:   Project setup, repo structure, codebase download
  Hours 2-6:   Ingestion pipeline (preprocessing + chunking + embedding)
  Hours 6-10:  Vector DB setup + storage + basic retrieval
  Hours 10-14: Query interface (FastAPI + Jinja2)
  Hours 14-18: Answer generation (LLM integration)
  Hours 18-22: Testing, bug fixes, deployment
  Hours 22-24: Buffer for overruns

Days 2-3 (G4 Final):
  Day 2 AM:    Evaluation dataset + precision measurement
  Day 2 PM:    Chunking refinement (paragraph-level → hierarchical)
  Day 3 AM:    4 code understanding features
  Day 3 PM:    Architecture doc + cost analysis

Days 4-5 (GFA Final):
  Day 4:       UI polish (Next.js if time), re-ranking, hybrid search
  Day 5 AM:    Demo video recording
  Day 5 PM:    Social media post, final documentation, submission
```
**Pros:** Every hour has a purpose. Buffer time built in (Hours 22-24 on Day 1). Higher-risk items (ingestion, retrieval) are scheduled first when you're freshest. Documentation is after implementation (you can document what you actually built). The demo video is near the end so it captures the final product. This schedule has been battle-tested across hundreds of hackathon projects.
**Cons:** Rigid schedules break when unexpected problems arise (and they will). The time estimates assume familiarity with the tools — if you've never used Qdrant, the "Hours 6-10" block will overrun. Some tasks are shorter than allocated and some are longer; the plan doesn't dynamically rebalance.

### Answer C: Agile micro-sprints — 4-hour blocks with retro and re-planning
**Pros:** Maximum adaptability — every 4 hours, assess progress and re-prioritize. If ingestion is done early, pull forward retrieval refinement. If chunking is taking long, defer UI polish. The retrospective forces you to acknowledge what's working and what isn't, enabling faster pivots. This approach handles the uncertainty of working with unfamiliar technologies.
**Cons:** The overhead of re-planning every 4 hours can consume 15-30 minutes each cycle. Without a long-range plan, you might optimize locally (perfect chunking) at the expense of globally (no deployment). The cognitive switching cost of stepping back every 4 hours can break flow state. Risk of perpetual re-prioritization without shipping anything.

### **RECOMMENDATION: Answer B — Structured sprint, with Answer C's retrospective at each checkpoint**
First principles reasoning: The one-week sprint has hard deadlines — MVP at 24h is non-negotiable. A structured plan ensures you don't reach hour 20 without a deployed app. The key insight: the plan is a *commitment device*, not a prediction. You won't follow it exactly, but having it means deviations are conscious choices rather than time slipping away. The specific schedule in Answer B is calibrated to this project's requirements: ingestion before retrieval (you can't search what isn't indexed), retrieval before generation (you can't generate from nothing), deployment before features (the hard gate requires deployment). Add a 15-minute retro at each checkpoint (end of Day 1, Day 3, Day 5) to recalibrate — this is Answer C's best idea without the overhead. One critical rule: if you're at hour 18 of Day 1 without a deployed app, drop everything and deploy what you have. A deployed app with basic search beats a perfect pipeline that only runs locally.

---

## Question 9: How do you make your demo video compelling in 3-5 minutes when graders watch dozens of them?

The demo video is the graders' primary impression of your system. It needs to show capability, accuracy, and engineering depth without being boring.

### Answer A: Screen recording of live queries — just show it working
**Pros:** Authentic — the system either works or it doesn't. No slides to hide behind. Shows real query latency, real results, real answer quality. Quick to produce (15 minutes to record, 15 to edit). Demonstrates the deployed version, proving deployment works.
**Cons:** If the system is slow or returns a bad result, it's on camera forever. No context for WHY design decisions were made. The grader sees the frontend but not the architecture. A sequence of queries can be monotonous — "here's another query, here's another result."

### Answer B: Structured demo: 30s architecture overview → 2min live queries → 1min metrics/learnings
**Pros:** The 30-second architecture overview (a single diagram slide) gives graders the mental model to appreciate what they're seeing. Live queries are the proof of work. The closing metrics (precision@5: 73%, latency: 2.1s avg) and learnings ("our biggest challenge was COBOL paragraph detection") demonstrate rigor and self-awareness. The structure ensures you hit all evaluation criteria in sequence. The architecture slide maps to the architecture doc, creating deliverable consistency.
**Cons:** Requires creating a diagram and slides, adding 30-60 minutes of prep. The transitions between slides and live demo need to be smooth. The structured format might feel rehearsed.

### Answer C: Narrative demo — tell the story of a developer encountering the legacy codebase for the first time
**Pros:** "Imagine you're a developer who just joined a bank that runs on 40-year-old COBOL. You open the codebase and see 50,000 lines of code you can't read. Here's how LegacyLens helps." This narrative hook makes the demo memorable. Each query becomes part of the story: first find the entry point, then understand a specific module, then trace dependencies. The narrative naturally showcases multiple features. Graders remember stories better than feature lists.
**Cons:** Takes more preparation to script the narrative. Risk of spending too much time on the story and not enough on showing the system. The narrative approach only works if the system actually delivers on the story's promises.

### **RECOMMENDATION: Answer B structure with Answer C's narrative hook**
First principles reasoning: Graders watch dozens of these. You have 10 seconds to capture attention before they start skimming. Open with the narrative hook from Answer C ("imagine inheriting a COBOL codebase..."), then transition to the architecture slide (Answer B), then live queries that follow the narrative, then close with metrics. The specific demo script: (1) Narrative hook — 15 seconds, (2) Architecture diagram — 30 seconds, (3) "Where's the entry point?" query — 30 seconds, (4) "Explain CALCULATE-INTEREST paragraph" — 45 seconds, (5) "What depends on CUSTOMER-RECORD?" — 45 seconds, (6) "Generate documentation for this module" — 30 seconds, (7) Metrics + what you'd improve — 30 seconds. Total: ~3.5 minutes. Record in one take if possible — edits make it feel produced rather than authentic. Use the deployed version, not localhost — this proves deployment works.

---

## Question 10: What's the single most important thing to get right if you can only optimize one part of the system?

Everything else aside — if you had to pick one thing to invest disproportionate time in, what should it be?

### Answer A: Chunking quality
**Pros:** Chunking is the foundation. Bad chunks produce bad embeddings. Bad embeddings produce bad retrieval. Bad retrieval produces bad answers. No amount of re-ranking, prompt engineering, or LLM quality can compensate for chunks that split business logic mid-statement or combine unrelated code. Getting chunking right means every downstream component performs better. It's the highest-leverage intervention point in the entire pipeline.
**Cons:** Chunking is a preprocessing step — you do it once during ingestion. If it's wrong, you re-ingest (5 minutes). It's fixable. Spending disproportionate time on chunking at the expense of the query pipeline means you have perfect chunks with no way to search them.

### Answer B: Retrieval precision
**Pros:** Retrieval is where the user's question meets your indexed code. All the downstream features (code explanation, dependency mapping, business logic extraction) depend on retrieving the RIGHT chunks. The spec measures retrieval precision directly (>70% in top-5). Optimizing retrieval means tuning search parameters, re-ranking, hybrid search, and metadata filtering — all of which are tunable without re-ingesting. This is where iterative improvement has the most impact.
**Cons:** Retrieval precision depends on chunking and embedding quality — you can't optimize retrieval if the underlying data is bad. Retrieval optimization can become an infinite rabbit hole of parameter tuning. You might optimize for your evaluation dataset and overfit to specific query patterns.

### Answer C: Answer generation quality
**Pros:** The answer is what the user sees. Even with imperfect retrieval, a well-prompted LLM can synthesize a useful answer from partially relevant chunks. Answer quality is what the demo video showcases and what graders remember. A system with 60% retrieval precision but excellent answer formatting, citations, and explanations can score higher than one with 80% precision but raw, unformatted output. The prompt template is the easiest thing to iterate on — change a few words, run a query, see the difference.
**Cons:** "Garbage in, garbage out" — the LLM can't generate accurate answers from irrelevant chunks. Prompt engineering is not a substitute for accurate retrieval. Optimizing generation at the expense of retrieval is polishing a broken system.

### **RECOMMENDATION: Answer A — Chunking quality, with the understanding that it enables everything else**
First principles reasoning: First principles says optimize the bottleneck, and in RAG systems, the bottleneck is almost always the data layer — not the model layer. Here's the causal chain: **chunking → embedding quality → retrieval precision → answer accuracy**. Every component downstream is bounded by the quality of the component upstream. You can have a perfect re-ranker, a perfect prompt, and GPT-4o, but if your chunks split `CALCULATE-INTEREST` across two fragments and mix in unrelated code, the system fails. The converse is not true — good chunks with a basic retrieval pipeline still produce useful results. The spec validates this: "A simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results." Accurate retrieval starts with accurate chunks. Spend your first 4-6 hours getting chunking right (paragraph-aware, properly preprocessed, well-sized, rich metadata). Then validate with 5-10 manual queries before building any advanced features. This is the single decision that separates systems that work from systems that look like they work.

---

## Final Summary: All 30 Recommendations Across 3 Rounds

### Round 1 — Foundation
| # | Decision | Recommendation |
|---|----------|---------------|
| 1 | Target Codebase | GnuCOBOL |
| 2 | Vector Database | Qdrant (hybrid search) |
| 3 | Embedding Model | Voyage Code 2 |
| 4 | Chunking Strategy | Hierarchical, phased from paragraph |
| 5 | RAG Framework | Custom pipeline |
| 6 | LLM for Generation | GPT-4o + configurable fallback |
| 7 | Query Processing | Hybrid search + keyword extraction |
| 8 | Deployment | Render + Qdrant Cloud |
| 9 | Code Features | Explain + Deps + Docs + Business Logic |
| 10 | Re-ranking | Metadata-first, then cross-encoder |

### Round 2 — Implementation
| # | Decision | Recommendation |
|---|----------|---------------|
| 1 | Prompt Template | Structured COBOL-aware + confidence |
| 2 | Preprocessing | Column strip + comments + encoding |
| 3 | Context Window | Dynamic budget + expand top-1 |
| 4 | Evaluation Dataset | 10 manual + 20 LLM-verified |
| 5 | Metadata | File + lines + paragraph + division + type |
| 6 | Chunk Size | Adaptive 64-768 tokens on paragraph bounds |
| 7 | Confidence Scores | Normalized thresholds, calibrated |
| 8 | Ingestion | Batch embedding + concurrent upserts |
| 9 | Query Interface | FastAPI+Jinja2 MVP → Next.js Final |
| 10 | Cost Analysis | Detailed model with real measured spend |

### Round 3 — Production & Meta
| # | Decision | Recommendation |
|---|----------|---------------|
| 1 | Zero-result Handling | Tiered degradation + keyword fallback |
| 2 | Cross-file Queries | Top-k MVP → metadata-filtered Final |
| 3 | COPY Statements | Index separately MVP → metadata linking Final |
| 4 | Testing Strategy | Eval script + targeted manual testing |
| 5 | Latency Optimization | Streaming + embedding cache |
| 6 | Repo Structure | Clean modular (ingestion/retrieval/generation) |
| 7 | Interview Prep | Decision log → STAR-structured real stories |
| 8 | Time Allocation | Structured sprint with checkpoint retros |
| 9 | Demo Video | Narrative hook + architecture + live queries + metrics |
| 10 | Single Most Important | Chunking quality — it's the foundation of everything |

---

### The Meta-Principle

Every recommendation above follows one rule: **optimize the system's quality ceiling, not its feature count.** The spec says it twice: "A simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results." Ship accuracy. Ship precision. Ship a system where every query returns the right code with the right citations. Then, and only then, add features on top.

Good luck, Alex. Ship it.
