# G4-021 Primer: Cost Analysis Document

**For:** New Cursor Agent session
**Project:** LegacyLens — RAG-Powered Legacy Code Intelligence System
**Date:** Mar 4, 2026
**Previous work:** All phases complete through G4-008. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

G4-021 creates a cost analysis document at `Docs/architecture/cost-analysis.md`. This is a **documentation-only ticket** — no code changes.

The document should cover actual API costs incurred during development, current operational costs, and projections for scaling to production usage tiers.

---

## Cost Components

LegacyLens uses 4 paid external APIs:

| Service | Usage Type | Pricing Model |
|---------|-----------|---------------|
| Voyage Code 2 | Embedding (ingestion + query) | Per token |
| Qdrant Cloud | Vector storage + search | Per node/month (free tier available) |
| OpenAI GPT-4o | Answer generation | Per input/output token |
| Cohere Rerank | Cross-encoder re-ranking | Per search unit |

### Voyage Code 2 (Embeddings)

- **Model:** `voyage-code-2`
- **Dimensions:** 1536
- **Batch size:** 128 texts per call
- **Usage contexts:**
  - Ingestion: embed all chunks (one-time per codebase)
  - Query: embed each user query (per request)
- **Pricing:** Check current rates at `https://docs.voyageai.com/pricing/`

### Qdrant Cloud

- **Collection:** `legacylens`
- **Total points:** ~17,225 (across 5 codebases)
- **Dimensions:** 1536
- **Free tier:** Available (used for this project)
- **Pricing:** Check `https://qdrant.tech/pricing/`

### OpenAI GPT-4o

- **Primary model:** `gpt-4o`
- **Fallback model:** `gpt-4o-mini`
- **Usage:** One generation call per query
- **Input:** system prompt (~500 tokens) + formatted chunks (~2,000-5,000 tokens) + user query
- **Output:** ~200-800 tokens per answer
- **Pricing:** Check `https://openai.com/pricing`

### Cohere Rerank

- **Model:** Cohere cross-encoder
- **Usage:** Optional re-ranking stage (runs when API key is set)
- **Input:** query + top-k chunks
- **Pricing:** Check `https://cohere.com/pricing`

---

## Document Structure

Create `Docs/architecture/cost-analysis.md` with the following sections:

### 1. Development Costs (Actual)

Calculate actual costs incurred during development:

**Ingestion costs (Voyage embedding):**

| Codebase | Chunks | Est. Tokens | Runs |
|----------|--------|-------------|------|
| gnucobol | 3 | ~1,500 | 1 |
| gfortran | ~13,800 | ~5,500,000 | 3+ (multiple failed attempts) |
| lapack | 12,515 | ~5,000,000 | 2 (1 failed, 1 success) |
| blas | 814 | ~325,000 | 1 |
| opencobol-contrib | 3,893 | ~1,550,000 | 2 |

Note: Token estimates assume ~400 tokens/chunk average. Multiply by Voyage per-token rate.

**Query costs during development (Voyage + GPT-4o + Cohere):**
- Estimate ~100-200 test queries during development and evaluation
- Each query: ~50 tokens embedding + ~3,000-5,000 tokens GPT-4o input + ~500 tokens output

### 2. Per-Query Cost Breakdown

Break down the cost of a single query:

| Stage | Service | Est. Tokens | Est. Cost |
|-------|---------|-------------|-----------|
| Embed query | Voyage | ~50 | $ |
| Vector search | Qdrant | N/A | Free tier |
| Re-rank | Cohere | 10 chunks | $ |
| Generate answer | GPT-4o input | ~4,000 | $ |
| Generate answer | GPT-4o output | ~500 | $ |
| **Total per query** | | | **$** |

Fill in actual dollar amounts using current pricing.

### 3. Scaling Projections

Project costs across 4 usage tiers:

| Tier | Queries/month | Voyage | Qdrant | GPT-4o | Cohere | Total/month |
|------|--------------|--------|--------|--------|--------|-------------|
| Dev (current) | ~200 | $ | Free | $ | $ | $ |
| Small (100 users) | ~1,000 | $ | $ | $ | $ | $ |
| Medium (1K users) | ~10,000 | $ | $ | $ | $ | $ |
| Large (10K users) | ~100,000 | $ | $ | $ | $ | $ |

Assumptions to state:
- Average 10 queries per user per month
- Qdrant free tier supports dev/small, paid tier needed at medium+
- GPT-4o-mini fallback could reduce generation costs by ~10x
- Cohere is optional — metadata-only reranking is free

### 4. Cost Optimization Strategies

List practical ways to reduce costs:

1. **Embedding cache:** Cache query embeddings for repeated queries (saves Voyage costs)
2. **GPT-4o-mini default:** Use 4o-mini for simple queries, 4o only for complex ones
3. **Skip Cohere for simple queries:** Metadata-only reranking is free and often sufficient
4. **Reduce top_k:** Fewer chunks = less GPT-4o input tokens
5. **Chunk size optimization:** Smaller chunks = more chunks but less per-query context cost
6. **Batch ingestion timing:** Re-index during off-peak API hours

### 5. Infrastructure Costs

| Service | Tier | Monthly Cost |
|---------|------|-------------|
| Render (API hosting) | Free | $0 |
| Vercel (Frontend) | Free | $0 |
| Qdrant Cloud | Free | $0 |
| **Total infra** | | **$0** (current) |

Note: Free tiers have limitations (cold starts, storage limits, rate limits). Document what would change at each scaling tier.

---

## Deliverables

- [ ] `Docs/architecture/cost-analysis.md` created
- [ ] Actual development costs estimated
- [ ] Per-query cost breakdown with real pricing
- [ ] 4-tier scaling projections (dev/100/1K/10K users)
- [ ] Cost optimization strategies listed
- [ ] No code changes

### Files to Create

| File | Action |
|------|--------|
| `Docs/architecture/cost-analysis.md` | Create cost analysis document |

### Files to READ for Context

| File | Why |
|------|-----|
| `src/config.py` | API keys, model names, batch sizes |
| `src/ingestion/embedder.py` | Embedding batch size and model |
| `src/generation/llm.py` | GPT-4o model and fallback logic |
| `src/retrieval/reranker.py` | Cohere reranking setup |
| `Docs/tickets/DEVLOG.md` | Ingestion stats (chunk counts, run counts) |
| `Dockerfile` | Deployment config |
| `render.yaml` | Render service config |

### Files You Should NOT Modify

- Any source code in `src/`
- Test files
- Evaluation files
- Config files

---

## How to Research Current Pricing

Use these URLs to get current pricing (prices change frequently):

- **Voyage:** `https://docs.voyageai.com/pricing/`
- **OpenAI:** `https://openai.com/pricing`
- **Cohere:** `https://cohere.com/pricing`
- **Qdrant Cloud:** `https://qdrant.tech/pricing/`
- **Render:** `https://render.com/pricing`
- **Vercel:** `https://vercel.com/pricing`

---

## Definition of Done

- [ ] Cost analysis document created with all 5 sections
- [ ] Real pricing numbers (not placeholders)
- [ ] 4-tier scaling projections
- [ ] Optimization strategies documented
- [ ] DEVLOG updated with G4-021 entry
