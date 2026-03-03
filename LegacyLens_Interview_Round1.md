# LegacyLens — Senior Full-Stack Engineer Interview
## Round 1 of 3: Foundation & Architecture Decisions

---

## Question 1: Which target codebase should you choose, and why does it matter more than you think?

The codebase choice isn't just a checkbox — it dictates your chunking strategy, embedding quality, retrieval edge cases, and how impressive your demo looks during the interview gate.

### Answer A: GnuCOBOL (COBOL)
**Pros:** COBOL is the poster child for "legacy enterprise" — interviewers immediately understand the value proposition. COBOL's rigid column-based structure (divisions, sections, paragraphs) gives you natural syntactic boundaries for chunking. The PROCEDURE DIVISION / DATA DIVISION separation means your RAG can meaningfully distinguish between business logic and data definitions. GnuCOBOL is actively maintained with ~200K+ LOC across files, easily clearing the 10K/50-file minimum.
**Cons:** COBOL's fixed-format structure (columns 1-6 are sequence numbers, column 7 is indicator, 8-72 are code) requires custom preprocessing that eats into your 24-hour MVP window. Embedding models have almost zero COBOL in their training data, so semantic similarity will be weaker than with Fortran. Fewer developers can validate your output correctness.

### Answer B: LAPACK (Fortran)
**Pros:** LAPACK is well-documented, mathematically rigorous, and has clear function-level boundaries (each subroutine is self-contained). At ~600K+ LOC it's massive enough to stress-test your pipeline. Fortran has better representation in embedding model training data than COBOL. The mathematical nature means queries like "find all matrix decomposition routines" have objectively correct answers — perfect for measuring retrieval precision. The code is dense with comments explaining algorithms, which enriches your embeddings.
**Cons:** Mathematical subroutine names (DGEMM, ZHEEV) are opaque to embedding models — they'll struggle with semantic matching on function names. The codebase is highly homogeneous (linear algebra everywhere), making it harder to demonstrate diverse query types. Less "wow factor" in interviews compared to COBOL.

### Answer C: OpenCOBOL Contrib (COBOL sample programs)
**Pros:** Sample programs are smaller, self-contained, and cover diverse business domains (banking, inventory, reporting). This diversity gives you richer testing scenarios and more interesting demo queries. Each program is understandable in isolation, making it easier to validate your RAG output for correctness. Lower complexity means faster iteration on chunking and retrieval quality.
**Cons:** May not hit the 10K LOC / 50 file minimum without combining with another source. "Sample programs" sounds less impressive than "production compiler" in interviews. The programs may be too simple to surface interesting retrieval challenges or demonstrate real-world value.

### **RECOMMENDATION: Answer A — GnuCOBOL**
First principles reasoning: The project is called "LegacyLens" and the entire narrative is about enterprise systems running COBOL/Fortran. GnuCOBOL is a real-world COBOL compiler written in COBOL — it's the most authentic representation of the problem domain. The rigid structure actually *helps* your chunking strategy once you handle the preprocessing, and the "wow factor" in interviews is unmatched. The weaker embedding performance on COBOL tokens is actually a *feature* for your architecture doc — it forces you to implement smarter chunking and metadata enrichment, which demonstrates deeper engineering thinking. Ship the harder path; it differentiates you.

---

## Question 2: Vector database selection — what actually matters when you have 7 days and a deployment requirement?

This decision cascades into your deployment architecture, cost profile, query latency, and how much time you spend on DevOps vs. actual RAG quality.

### Answer A: Pinecone (Managed Cloud)
**Pros:** Zero infrastructure management — you get a working vector DB in under 5 minutes. Free tier gives you 1 index with up to 100K vectors, which is more than enough for 10K-50K LOC. Built-in metadata filtering lets you filter by file path, language, or function type without custom code. Serverless architecture means your deployed app doesn't need to run a database process. Pinecone's API is dead simple: upsert, query, done.
**Cons:** Vendor lock-in is real — your entire ingestion pipeline is coupled to their API. Free tier limits you to a single index with a single namespace, constraining experimentation with different embedding strategies. Latency on free tier can spike to 200-500ms for cold starts. No hybrid search (vector + keyword) on the free tier. If Pinecone has an outage during your demo, you're dead.

### Answer B: Qdrant (Self-hosted on Railway/Render)
**Pros:** Rust-based, extremely fast — sub-10ms query times on small datasets. Native hybrid search combining dense vectors with sparse (BM25-like) retrieval. Rich filtering with payload indexes means complex metadata queries are performant. Open source with a generous cloud free tier. You can run it locally during development and deploy to cloud for production, giving you the best of both worlds. The filtering capability is a superpower for code search (filter by file type, function name patterns, etc.).
**Cons:** Self-hosting adds operational complexity — you need to manage a Docker container or cloud instance alongside your app. Memory usage on small cloud instances can be tight. The learning curve is steeper than Pinecone; the API has more concepts (collections, points, payloads, scroll vs. search). If you're deploying to Vercel/Railway, you need a separate service for Qdrant, which complicates your deployment topology.

### Answer C: ChromaDB (Embedded/Local)
**Pros:** Absolute fastest path to a working prototype — `pip install chromadb` and you're running. Embedded mode means zero network latency for queries. Perfect for the 24-hour MVP sprint since there's no infrastructure to configure. The API is the simplest of all options: `collection.add()`, `collection.query()`. Supports persistence to disk, so you can pre-build the index locally and deploy it as a file artifact.
**Cons:** ChromaDB is designed for prototyping, not production. Embedded mode means your vector DB lives inside your application process — if the app restarts, you need to reload from persistence (adds startup latency). No built-in replication, no horizontal scaling. Metadata filtering is basic compared to Qdrant or Pinecone. The "deployed and publicly accessible" requirement becomes tricky — you'd need to bundle the persisted DB with your deployment, which can exceed free tier storage limits on platforms like Vercel.

### **RECOMMENDATION: Answer B — Qdrant**
First principles reasoning: The project requires deployment AND >70% retrieval precision in top-5 results. Qdrant's hybrid search (dense + sparse) is the single most impactful feature for hitting that precision target on legacy code, where function names like `PERFORM CALCULATE-INTEREST` are better matched by keyword than by semantic embedding. The self-hosting complexity is manageable — Qdrant Cloud offers a free tier with 1GB storage, or you can deploy their Docker image to Railway in one click. ChromaDB gets you to MVP faster but creates technical debt you'll pay for at the Final gate. Pinecone is viable but the lack of hybrid search on free tier will cost you precision points that matter for your grade.

---

## Question 3: Embedding model — code-specific or general-purpose, and what dimension tradeoff should you accept?

Your embedding model choice determines the quality ceiling of your entire retrieval pipeline. A bad embedding model cannot be fixed by better chunking or re-ranking.

### Answer A: Voyage Code 2 (1536 dimensions, code-optimized)
**Pros:** Purpose-built for code embedding — trained on code-specific datasets with understanding of syntax, semantics, and naming conventions across languages. Best-in-class performance on code search benchmarks. 1536 dimensions is a sweet spot: high enough for rich representation, small enough for fast similarity computation. Understands code structure (functions, classes, imports) natively, which is critical for legacy code where variable names carry business meaning.
**Cons:** API-only (no local inference) — every embedding requires a network call, adding latency to both ingestion and query. Pricing at ~$0.10/1M tokens adds up during development iteration. Less proven on COBOL/Fortran specifically since training data skews toward Python/JavaScript/Java. If Voyage has an API outage, your entire pipeline stops.

### Answer B: OpenAI text-embedding-3-small (1536 dimensions, general-purpose)
**Pros:** Most widely used embedding model in production RAG systems — battle-tested with extensive documentation and community support. Excellent at capturing natural language semantics, which matters because your users are querying in English ("find the interest calculation") not in COBOL. Supports dimension reduction via the `dimensions` parameter, letting you trade quality for speed at query time. OpenAI's API reliability is industry-leading. Cost is low at ~$0.02/1M tokens.
**Cons:** Not optimized for code — it treats code as text, missing structural cues like indentation, control flow, and scoping. On pure code-search benchmarks, it underperforms Voyage Code 2 by 5-15%. The 1536-dimension default may be unnecessarily large for a 10K-50K LOC codebase where the embedding space isn't that crowded. Being general-purpose means it's "good enough" at everything but "great" at nothing.

### Answer C: sentence-transformers (local, e.g., all-MiniLM-L6-v2 at 384 dims)
**Pros:** Completely free — no API costs during development or production. Runs locally with no network dependency, meaning your pipeline works offline and has zero latency for embedding generation. At 384 dimensions, storage and similarity computation are lightning fast. Full control over the model means you could fine-tune on COBOL/Fortran code if you had time. No vendor dependency whatsoever.
**Cons:** 384 dimensions is genuinely too small for nuanced code semantics — you'll see degraded retrieval quality on subtle queries like "find error handling patterns" vs. "find exception routines." The model has minimal code in its training data; it was optimized for English sentence similarity. Ingestion speed on CPU is 10-50x slower than API calls (matters for the "10K LOC in <5 minutes" target). The quality gap vs. Voyage/OpenAI embeddings is measurable and significant — expect 10-20% lower precision@5.

### **RECOMMENDATION: Answer A — Voyage Code 2**
First principles reasoning: Your retrieval precision target is >70% in top-5 — every percentage point of embedding quality matters because it's the foundation of the entire system. Voyage Code 2's code-specific training gives you the highest quality ceiling. The concern about COBOL being underrepresented is mitigated by the fact that your users query in *English* and your chunks contain *English comments* alongside COBOL code — the model needs to bridge natural language to code context, which is exactly what code-specific models excel at. The $0.10/1M token cost is negligible for a 10K-50K LOC codebase (you'll spend maybe $0.50-2.00 total on embeddings). If budget is genuinely zero, OpenAI text-embedding-3-small at $0.02/1M tokens is the fallback — never sentence-transformers for a graded project where precision is measured.

---

## Question 4: Chunking strategy — how do you split COBOL code that was written before structured programming existed?

Chunking is where most RAG systems fail on legacy code. COBOL doesn't have functions in the modern sense — it has divisions, sections, and paragraphs with implicit control flow through `PERFORM` and `GO TO`.

### Answer A: Paragraph-level chunking (COBOL's natural unit)
**Pros:** COBOL paragraphs are the closest equivalent to "functions" — each paragraph has a name and contains a discrete unit of business logic (e.g., `CALCULATE-INTEREST`, `VALIDATE-CUSTOMER`). Paragraph names ARE the business logic documentation in most legacy code. Splitting at paragraph boundaries preserves semantic coherence. Paragraph-level chunks are typically 20-100 lines, which is ideal for most embedding models' context windows (~512 tokens). This approach directly maps to the testing scenarios in the spec ("Explain what the CALCULATE-INTEREST paragraph does").
**Cons:** Some paragraphs are trivially small (1-3 lines) and lack enough context for meaningful embeddings. Others are monstrously large (500+ lines in poorly structured code) and need sub-splitting. `PERFORM THRU` chains multiple paragraphs into one logical unit — splitting them loses the execution context. DATA DIVISION entries don't have paragraph structure, requiring a different strategy for data definitions.

### Answer B: Fixed-size with overlap (e.g., 500 tokens, 100-token overlap)
**Pros:** Dead simple to implement — you can get this working in 30 minutes, which is critical for the 24-hour MVP. Works uniformly across all code regardless of structure. The overlap ensures no information is lost at chunk boundaries. Predictable chunk sizes mean predictable embedding costs and consistent vector density. This is the default strategy in LangChain/LlamaIndex, so framework support is excellent.
**Cons:** Chunks will split mid-paragraph, mid-statement, even mid-word in COBOL's fixed-format columns. A chunk containing the end of one paragraph and the beginning of another creates a semantically incoherent embedding. The retrieval pipeline will return fragments that make no sense without surrounding context. For code, this strategy is fundamentally wrong — it ignores the structural information that makes code searchable. You will fail the retrieval precision target.

### Answer C: Hierarchical chunking (file → division → section → paragraph)
**Pros:** Captures code at multiple granularities simultaneously — a query about "how does the program work" retrieves file-level summaries, while "what does CALCULATE-INTEREST do" retrieves paragraph-level chunks. Each chunk carries its hierarchical path as metadata (file/division/section/paragraph), enabling precise drill-down. This directly supports the "ability to drill down into full file context" requirement. Re-ranking can select the optimal granularity per query. This is the most architecturally sound approach and demonstrates senior-level thinking in interviews.
**Cons:** 3-4x more embeddings to generate and store (every level of the hierarchy produces chunks). Implementation complexity is significantly higher — you need a COBOL parser or at minimum a regex-based structure detector for divisions/sections/paragraphs. Query-time logic needs to decide which level(s) to search or how to merge results across levels. The 24-hour MVP deadline makes this risky if you haven't built parsers before.

### **RECOMMENDATION: Answer C — Hierarchical chunking, BUT with a phased rollout**
First principles reasoning: The spec explicitly requires "syntax-aware splitting" as a hard gate MVP requirement AND lists hierarchical chunking as a strategy option. The winning approach is to implement paragraph-level (Answer A) first as your MVP chunking, then layer in the hierarchical structure for the Final gate. Here's why: paragraph-level is your 80/20 — it gets you syntax-aware splitting that satisfies the hard gate in the least time. Then the hierarchy adds the "drill down into full file context" capability and demonstrates architectural depth for the interview. Never use fixed-size (Answer B) as anything but a temporary fallback for non-COBOL files. The interview gate will specifically ask about chunking tradeoffs — showing a phased approach from simple to hierarchical signals engineering maturity.

---

## Question 5: RAG framework — LangChain, LlamaIndex, or custom pipeline?

This choice determines your development velocity, debugging experience, and how much of the system you actually understand when questioned in the interview.

### Answer A: LangChain
**Pros:** Largest ecosystem — integrations with every vector DB, embedding model, and LLM listed in the spec. Extensive documentation and community examples for RAG pipelines. LCEL (LangChain Expression Language) lets you compose retrieval chains declaratively. Built-in callbacks for logging and observability. If you hit a wall, there's probably a StackOverflow answer or GitHub issue with a solution.
**Cons:** Notorious abstraction leakage — when something breaks, you're debugging through 5+ layers of abstraction to find the actual HTTP call that failed. The API surface is enormous and changes frequently, making tutorials from 6 months ago unreliable. The "chain" abstraction adds overhead (both cognitive and computational) that isn't justified for a straightforward RAG pipeline. In interviews, saying "I used LangChain" without being able to explain what happens under the hood is a red flag.

### Answer B: LlamaIndex
**Pros:** Purpose-built for RAG — the entire framework is designed around the ingest → index → query paradigm. First-class support for hierarchical indexes, which aligns perfectly with the hierarchical chunking strategy. Better abstractions for document-oriented RAG (which code chunks essentially are). Built-in evaluation tools for measuring retrieval quality. The `VectorStoreIndex` + `QueryEngine` pattern maps 1:1 to this project's architecture.
**Cons:** Smaller ecosystem than LangChain — fewer integrations, less community support. The framework makes strong opinionated choices about index structures that may not match your needs. Debugging is still abstraction-heavy, though less so than LangChain. Some vector DB integrations (like Qdrant) are less mature in LlamaIndex than in LangChain.

### Answer C: Custom pipeline (no framework)
**Pros:** Total transparency — every line of code is yours, every API call is explicit. In the interview, you can explain exactly how query processing, embedding, similarity search, re-ranking, and answer generation work because you built each step. Zero framework overhead means faster execution and easier debugging. You learn the most by building from scratch, which is the entire point of this program. The pipeline is simple enough (embed → store → retrieve → generate) that a framework adds more complexity than it removes.
**Cons:** You're writing boilerplate that frameworks handle for free: retry logic, batch embedding, context window management, streaming responses. No built-in evaluation tools — you'll build your own precision measurement. Integration bugs that frameworks have already solved (embedding dimension mismatches, metadata serialization, token counting) will cost you hours. Higher risk of not finishing in the 24-hour MVP window.

### **RECOMMENDATION: Answer C — Custom pipeline**
First principles reasoning: The spec's Critical Guidance says "a simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results." The actual pipeline is: (1) read files, (2) chunk them, (3) embed chunks, (4) store in vector DB, (5) embed query, (6) similarity search, (7) assemble context, (8) call LLM. That's 8 steps, each 20-50 lines of Python. A framework adds abstraction over something that isn't complex enough to warrant abstraction. More importantly, the interview gate will grill you on why you chose your architecture — answering "because I understood every component deeply enough to build it myself" is categorically stronger than "because LangChain had a tutorial." The risk mitigation: keep the Qdrant client library, the embedding API client, and the LLM API client as your only dependencies. Those aren't frameworks — they're API wrappers.

---

## Question 6: LLM selection for answer generation — which model gives you the best cost/quality/latency triangle?

The LLM generates the final natural language answer from retrieved code chunks. It needs to understand code, follow instructions precisely, and cite specific file/line references.

### Answer A: GPT-4o (OpenAI)
**Pros:** Best-in-class code understanding — it can read COBOL, explain business logic, and generate accurate file/line citations. 128K token context window means you can stuff more retrieved chunks into the prompt without truncation. Fast inference (~5-15 tokens/sec for streaming). The instruction-following quality ensures consistent output formatting (always including file paths, line numbers, confidence). Mature API with excellent reliability.
**Cons:** Most expensive option at ~$2.50/1M input tokens, $10/1M output tokens. For the cost analysis deliverable, this will show the highest production cost projections. Latency for complex code explanation queries can hit 3-5 seconds, cutting into your <3 second target (though embedding + retrieval is typically <500ms, leaving 2.5s for LLM). Vendor lock-in to OpenAI.

### Answer B: Claude 3.5 Sonnet (Anthropic)
**Pros:** Exceptional at code explanation and long-context reasoning. 200K token context window — the largest of any option — means you can include entire files as context alongside retrieved chunks. Strong instruction following for structured output (JSON with file paths, line numbers, explanations). Arguably better than GPT-4o at explaining *why* code works a certain way, not just *what* it does. Competitive pricing at ~$3/1M input, $15/1M output tokens.
**Cons:** Slightly slower time-to-first-token than GPT-4o in practice. The API is less mature with fewer client libraries and community examples. Rate limits on free/low-tier plans can throttle you during development. Higher per-token cost than GPT-4o for output tokens.

### Answer C: GPT-4o-mini or GPT-3.5-turbo (Budget option)
**Pros:** Dramatically cheaper — GPT-4o-mini is ~$0.15/1M input, $0.60/1M output (roughly 15x cheaper than GPT-4o). Faster inference means better chance of hitting the <3 second latency target. For 100-1000 user scale, monthly costs stay under $50. Good enough for straightforward code explanation where the retrieved context is highly relevant. The cost analysis deliverable will look impressive with low production projections.
**Cons:** Measurably worse at complex code reasoning — will miss nuanced business logic in COBOL, generate vague explanations, and sometimes hallucinate file references. Smaller context window (128K for mini, 16K for 3.5-turbo) limits how much context you can provide. The quality difference is visible in side-by-side comparison, which an interviewer might do. Answer accuracy (a performance metric in the spec) will suffer.

### **RECOMMENDATION: Answer A — GPT-4o, with Answer C as a configurable fallback**
First principles reasoning: The spec measures "answer accuracy" with "correct file/line references" — this is a quality-sensitive metric where the LLM's code comprehension directly impacts your score. GPT-4o's code understanding is measurably superior for legacy languages. The cost concern is irrelevant for the project itself (you'll make maybe 100-500 queries during development, costing $1-5 total). For the cost analysis deliverable, present BOTH models: GPT-4o for accuracy-critical use cases and GPT-4o-mini for cost-sensitive production — this shows you think about production economics without sacrificing demo quality. Make the LLM configurable via environment variable so switching takes zero code changes.

---

## Question 7: How should you implement query processing to bridge the gap between natural language questions and legacy code semantics?

Users ask "what handles customer validation?" but the code has `PERFORM 2100-VALIDATE-CUST-REC`. Your query processing layer needs to bridge this semantic gap.

### Answer A: Direct embedding similarity (embed the query as-is)
**Pros:** Simplest implementation — embed the user's natural language query and find the closest chunks. Zero additional processing latency. Works surprisingly well when chunks contain English comments alongside code. No additional API calls or processing steps. This is your MVP path.
**Cons:** Fails catastrophically on queries referencing specific COBOL constructs ("find all PERFORM THRU statements") because the embedding model doesn't understand COBOL syntax. The semantic gap between "customer validation" and `2100-VALIDATE-CUST-REC` may be too large for the embedding model to bridge. Single-query retrieval has a hard precision ceiling — if the top-5 results miss, there's no recovery mechanism.

### Answer B: Query expansion with LLM preprocessing
**Pros:** Use the LLM to expand "what handles customer validation?" into multiple search queries: the original, plus "VALIDATE-CUST", "customer record checking", "input validation routine." Run each expanded query against the vector DB and merge results. This dramatically increases recall — if one query formulation misses, another catches it. The LLM can also extract entities (module names, data types) and inject them as metadata filters. This is the single highest-impact technique for improving retrieval precision.
**Cons:** Adds an LLM call before retrieval, increasing latency by 500-1500ms. Each expanded query needs a separate embedding + similarity search, multiplying compute costs. The LLM might hallucinate COBOL terms that don't exist in the codebase, wasting search capacity. Implementation complexity is moderate — you need to parse the LLM's expansion output and manage multiple search results.

### Answer C: Hybrid search (vector + keyword BM25)
**Pros:** Keyword search catches exact matches that embedding models miss — searching for "CALCULATE-INTEREST" as a keyword will always find the paragraph named `CALCULATE-INTEREST`, even if the embedding model doesn't place them close in vector space. Hybrid search combines the best of semantic understanding (vector) and exact matching (keyword). This is especially powerful for legacy code where identifier names ARE the documentation. Qdrant natively supports this with sparse vectors.
**Cons:** Requires building and maintaining a keyword index alongside the vector index — more storage, more complexity. Tuning the balance between vector and keyword scores (alpha parameter) requires experimentation. BM25 tokenization needs customization for COBOL (hyphens in identifiers, section numbering). Adds implementation time that might not fit in the MVP window.

### **RECOMMENDATION: Answer C — Hybrid search, combined with lightweight query expansion**
First principles reasoning: The testing scenarios in the spec include both semantic queries ("explain what CALCULATE-INTEREST does") and exact-match queries ("find all file I/O operations," "what are the dependencies of MODULE-X"). No single retrieval method handles both well. Hybrid search is the correct architectural answer because it's the only approach that doesn't sacrifice an entire category of queries. Since we already recommended Qdrant (which has native hybrid search), the implementation cost is low — you're enabling a feature, not building infrastructure. Add lightweight query expansion (extract keywords from the natural language query using regex, not LLM) as a middle ground that adds no latency. Save full LLM-based query expansion for the Final gate as a precision booster.

---

## Question 8: Deployment architecture — how do you satisfy "deployed and publicly accessible" without blowing your budget or timeline?

This is a hard gate MVP requirement. Your deployed app needs to handle the query interface, vector DB access, embedding generation, and LLM calls.

### Answer A: Vercel (frontend) + Vercel Serverless Functions (backend)
**Pros:** Vercel's free tier is generous — unlimited deployments, serverless functions with 10-second timeout on hobby plan. Next.js gives you a polished frontend with server-side rendering out of the box. Deployment is `git push` and done. The serverless model means you pay nothing when nobody's using it. Great developer experience with instant preview deployments for iteration.
**Cons:** 10-second function timeout on free tier is dangerously close to your pipeline's worst-case latency (embedding + vector search + LLM generation can take 5-8 seconds). Cold starts add 1-3 seconds on top. No persistent process means you can't keep a vector DB connection warm. If using ChromaDB embedded, you'd need to load the index on every cold start. Serverless functions have a 250MB deployment size limit, which can be tight with ML dependencies.

### Answer B: Railway (full-stack monolith)
**Pros:** Railway gives you a full Linux container — no function timeouts, persistent connections, long-running processes. The free tier includes $5/month of credits, which covers a small app running 24/7. You can run your backend + Qdrant in the same project with internal networking. Docker-based deployment means your local dev environment exactly matches production. No cold start problem — the server is always running.
**Cons:** $5/month free credit runs out fast if you're running multiple services (app + Qdrant). RAM is limited on the starter plan — running both your app and an embedded vector DB might exhaust it. Less polished frontend hosting compared to Vercel (no edge caching, no preview deployments). If you exceed the free tier, billing kicks in immediately.

### Answer C: Render (web service) + Qdrant Cloud (managed vector DB)
**Pros:** Clean separation of concerns — your application on Render, your vector DB on Qdrant Cloud. Both have free tiers that are independent, maximizing your free resource pool. Render's free web service has no function timeout limits. Qdrant Cloud's free tier gives you 1GB storage with no time limits. This architecture mirrors production patterns (stateless app + managed data store), which looks mature in your architecture doc. Each service can scale independently.
**Cons:** Two services to manage means two potential points of failure. Cross-service latency (Render → Qdrant Cloud) adds 20-50ms per query. Render's free tier spins down after 15 minutes of inactivity — first request after spin-down takes 30-60 seconds. More complex deployment configuration (two platforms, two sets of credentials, two CI/CD pipelines).

### **RECOMMENDATION: Answer C — Render + Qdrant Cloud**
First principles reasoning: The deployment requirement is "publicly accessible" — it needs to work when the graders click the link. Render + Qdrant Cloud gives you the most resilient free tier because the services are independent (one going down doesn't kill the other). The spin-down issue on Render is solved with a simple cron ping (free services like UptimeRobot or a GitHub Action hitting your endpoint every 14 minutes). The separation of app and data also makes your architecture doc more credible — you're describing a production-ready topology, not a hack. Railway is a strong alternative if you want a simpler single-platform experience, but the combined free credits of Render + Qdrant Cloud give you more runway.

---

## Question 9: Which 4 code understanding features should you implement to maximize impact with minimum effort?

The spec requires at least 4 of 8 features. Choosing the right 4 is a resource allocation decision that determines your grade ceiling.

### Answer A: Code Explanation + Dependency Mapping + Documentation Gen + Business Logic Extract
**Pros:** These four are the most synergistic — they all build on the same retrieval pipeline with different prompts. Code Explanation is your core feature (it's literally what RAG does). Dependency Mapping adds a graph traversal layer on top of retrieval. Documentation Gen is just Code Explanation with a different output format. Business Logic Extract is the "killer feature" for COBOL — the whole point of LegacyLens is making business rules understandable. Together, they tell a cohesive story: "I help you understand, document, and navigate legacy code."
**Cons:** No "detection" features (Pattern Detection, Bug Pattern Search) means you can't demonstrate automated code analysis. Missing Impact Analysis means you can't answer "what breaks if I change this?" — a high-value enterprise question. This set is more passive (explain existing code) than active (find problems), which may seem less impressive.

### Answer B: Code Explanation + Pattern Detection + Bug Pattern Search + Impact Analysis
**Pros:** This set is analysis-heavy — it goes beyond "explain the code" to "find problems in the code." Pattern Detection and Bug Pattern Search demonstrate that your RAG can do more than answer questions; it can proactively surface issues. Impact Analysis is the most technically impressive feature (it requires understanding call graphs and data flow). This set is more likely to impress interviewers who value engineering ambition.
**Cons:** Pattern Detection and Bug Pattern Search require curated knowledge bases of known patterns/bugs — building these for COBOL is a significant effort. Impact Analysis is genuinely hard to implement well and may produce unreliable results on legacy code with heavy `GO TO` usage. You risk implementing four features poorly instead of four features well. The spec says "a simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results."

### Answer C: Code Explanation + Dependency Mapping + Translation Hints + Documentation Gen
**Pros:** Translation Hints (suggest modern language equivalents) is unique and immediately resonates with anyone who's heard of COBOL modernization. Combined with Code Explanation and Documentation Gen, you tell the story of "legacy-to-modern migration assistant." Dependency Mapping adds technical depth. These four are all achievable with retrieval + LLM prompting — no custom analysis engines needed. The migration narrative is compelling for the social media post deliverable.
**Cons:** Translation Hints is risky — generating accurate Python/Java equivalents of COBOL code requires the LLM to deeply understand COBOL semantics, which even GPT-4o struggles with. A bad translation suggestion is worse than no suggestion. This set lacks any "detection" or "analysis" capabilities. Documentation Gen and Code Explanation have significant overlap, which might appear lazy.

### **RECOMMENDATION: Answer A — Code Explanation + Dependency Mapping + Documentation Gen + Business Logic Extract**
First principles reasoning: The spec's testing scenarios are all about understanding code ("explain what CALCULATE-INTEREST does," "what are the dependencies of MODULE-X," "show me error handling patterns"). Answer A directly addresses these scenarios. Business Logic Extract is the standout feature — it's the reason LegacyLens exists. COBOL codebases encode business rules that govern billions of dollars in transactions; extracting those rules in plain English is the highest-value capability you can demonstrate. The synergy between these four means each feature reinforces the others with minimal additional code. Avoid Answer B's ambition trap — the spec repeatedly warns that accuracy beats complexity. Avoid Answer C's translation risk — you don't want to demo a feature that generates wrong code.

---

## Question 10: How should you structure your re-ranking strategy to hit >70% retrieval precision in top-5?

The spec targets >70% relevant chunks in top-5 results. With a naive single-pass retrieval, you'll typically see 40-60% precision. Re-ranking is how you close that gap.

### Answer A: No re-ranking — increase top-k and rely on embedding quality
**Pros:** Simplest approach — retrieve top-20 from the vector DB, return the top-5. Zero additional latency. No additional API calls or model costs. If your embeddings and chunking are good enough, this might be all you need. The doc says re-ranking is "optional," so you're not penalized for skipping it.
**Cons:** Embedding similarity alone is a noisy signal for code — two chunks about completely different features might have similar embeddings because they share boilerplate structure. Without re-ranking, your precision is capped by embedding quality. For COBOL code where embedding models have weak training signal, this cap might be below 70%. You're leaving precision points on the table.

### Answer B: Cross-encoder re-ranking (e.g., Cohere Rerank or a cross-encoder model)
**Pros:** Cross-encoders evaluate query-document relevance by processing both together, which is fundamentally more accurate than comparing independent embeddings. Cohere Rerank API is purpose-built for this — pass your query + top-20 candidates, get back re-scored results. Typical precision improvement is 10-25 percentage points over embedding-only retrieval. This is the industry standard for production RAG systems. The API is cheap (~$1/1000 searches) and fast (100-300ms).
**Cons:** Adds 100-300ms latency per query (eating into your <3 second budget). Another API dependency and vendor to manage. Another cost line item in your cost analysis. For the 24-hour MVP, this is scope that might not be necessary — get retrieval working first. The model isn't trained on COBOL, so gains might be smaller than on standard text.

### Answer C: Metadata-based re-ranking (custom scoring using chunk metadata)
**Pros:** Zero additional API calls — re-rank using metadata you already have (file path relevance, function name match, line proximity, chunk type). For example, boost paragraphs whose names partially match the query keywords, boost chunks from the PROCEDURE DIVISION when the query asks about logic. This leverages your domain knowledge of COBOL structure, which no general-purpose re-ranker has. Fast (pure computation, no network calls) and free.
**Cons:** Requires manual tuning of scoring weights — how much to boost a paragraph name match vs. a division match? The scoring heuristics are brittle and may not generalize well. No semantic understanding — the re-ranker doesn't know that "calculate interest" and `COMPUTE-INT-AMT` are related. Limited precision improvement compared to cross-encoder approaches (typically 5-10 points).

### **RECOMMENDATION: Answer C first, then Answer B — layered re-ranking**
First principles reasoning: Re-ranking should be layered because each layer catches different types of relevance failures. Start with metadata-based re-ranking (Answer C) because it's free, fast, and leverages your COBOL-specific knowledge — boost chunks where the paragraph name contains keywords from the query, boost PROCEDURE DIVISION chunks for "how" questions and DATA DIVISION chunks for "what data" questions. This alone can add 5-10 precision points at zero cost. Then layer Cohere Rerank (Answer B) on top for the Final gate — it catches the semantic relevance that metadata misses. Together, they can push you from ~55% baseline to >75% precision. Skip Answer A entirely — the precision target is too tight to leave points on the table.

---

## Summary of Round 1 Recommendations

| # | Decision | Recommendation | Core Principle |
|---|----------|---------------|----------------|
| 1 | Target Codebase | GnuCOBOL | Authenticity + interview differentiation |
| 2 | Vector Database | Qdrant | Hybrid search for precision |
| 3 | Embedding Model | Voyage Code 2 | Quality ceiling determines system ceiling |
| 4 | Chunking Strategy | Hierarchical (phased from paragraph) | Syntax-aware → MVP, hierarchical → Final |
| 5 | RAG Framework | Custom pipeline | Full understanding + interview credibility |
| 6 | LLM for Generation | GPT-4o (with mini fallback) | Answer accuracy is graded |
| 7 | Query Processing | Hybrid search + lightweight expansion | Cover both semantic and exact-match queries |
| 8 | Deployment | Render + Qdrant Cloud | Independent free tiers, production topology |
| 9 | Code Understanding Features | Explain + Deps + Docs + Business Logic | Synergy + addresses spec test scenarios |
| 10 | Re-ranking | Metadata-first, then cross-encoder | Layered precision, zero-cost foundation |

---

*Round 2 will go deeper into implementation specifics: prompt engineering, context window management, evaluation methodology, failure modes, and scaling architecture.*
