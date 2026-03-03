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
