# LegacyLens — Pre-Search Document

> Completed as part of Phase 0 configuration.

## Phase 1: Define Your Constraints
- Scale: 850K+ LOC across 5 codebases, 1-2 users at launch
- Budget: $35-75 sprint spend, free tier hosting
- Timeline: 24h MVP, 3-day G4, 5-day GFA
- Data: All open source, no compliance constraints
- Skills: Python/FastAPI/React known, RAG/COBOL/Fortran gaps mitigated via docs

## Phase 2: Architecture Discovery
- Vector DB: Qdrant Cloud (native hybrid search, free 1GB)
- Embedding: Voyage Code 2 (code-optimized, 1536 dims)
- Chunking: Language-specific (COBOL paragraphs, Fortran subroutines), adaptive 64-768 tokens
- Retrieval: Hybrid dense+BM25, query-adaptive weights
- Re-ranking: Metadata-first + Cohere cross-encoder
- Generation: GPT-4o with language-aware prompts, streaming
- Framework: Custom pipeline (no LangChain/LlamaIndex)

## Phase 3: Post-Stack Refinement
- Failure modes: 12 documented with mitigations (see system-design.md)
- Evaluation: 50+ ground truth queries, precision@5 target >85%
- Caching: LRU for query embeddings
- Observability: Logging, latency metrics, health checks
- Deployment: Render + Vercel + Qdrant Cloud, UptimeRobot keepalive
