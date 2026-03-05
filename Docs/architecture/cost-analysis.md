# LegacyLens — Cost Analysis

This document covers actual API costs incurred during development, per-query cost breakdown, scaling projections, and optimization strategies.

---

## 1. Development Costs (Actual)

### Ingestion Costs (Voyage Code 2 Embedding)

LegacyLens uses Voyage Code 2 (`voyage-code-2`) for embeddings. Pricing: **$0.12 per million tokens**. First **50 million tokens** are free per account.

| Codebase | Chunks | Est. Tokens (~400/chunk) | Runs | Est. Cost |
|----------|--------|---------------------------|------|-----------|
| gnucobol | 3 | ~1,200 | 1 | $0 (within free tier) |
| lapack | 12,515 | ~5,000,000 | 2 (1 failed, 1 success) | ~$0.60 |
| blas | 814 | ~326,000 | 1 | $0 (within free tier) |
| opencobol-contrib | 3,893 | ~1,557,000 | 2 | ~$0.19 |
| gfortran | ~13,800 | ~5,520,000 | 3+ (multiple attempts) | ~$0.66 |

**Total ingestion (Voyage):** ~$1.45 (most within 50M free tier; excess at $0.12/M)

### Query Costs During Development

- **Test queries:** ~150–200 during development and evaluation
- **Per query:** Voyage embed (~50 tokens) + GPT-4o (~4,000 input, ~500 output) + Cohere rerank (10 chunks)
- **Voyage:** 200 × 50 = 10,000 tokens ≈ $0.001 (within free tier)
- **GPT-4o:** 200 × (4,000 × $2.50/1M + 500 × $10/1M) ≈ 200 × $0.015 = **~$3.00**
- **Cohere:** Trial keys are free; production would add ~$0.001–0.002 per query

**Total development (queries):** ~$3.00 (GPT-4o dominant)

**Estimated total development cost:** ~$4.50 (ingestion + queries)

---

## 2. Per-Query Cost Breakdown

| Stage | Service | Est. Usage | Price | Est. Cost |
|-------|---------|------------|-------|-----------|
| Embed query | Voyage Code 2 | ~50 tokens | $0.12/1M | ~$0.000006 |
| Vector search | Qdrant Cloud | N/A | Free tier | $0 |
| Re-rank | Cohere | 10 chunks, ~500 tokens | Trial free / ~$0.001/query prod | $0–0.001 |
| Generate answer | GPT-4o input | ~4,000 tokens | $2.50/1M | ~$0.01 |
| Generate answer | GPT-4o output | ~500 tokens | $10/1M | ~$0.005 |
| **Total per query** | | | | **~$0.015–0.016** |

**With GPT-4o-mini fallback:** Input $0.15/1M, output $0.60/1M → ~$0.001 per query (≈10× cheaper).

*Pricing sources: Voyage docs, OpenAI API pricing (GPT-4o ~$2.50/$10 per 1M tokens), Cohere trial/production.*

---

## 3. Scaling Projections

Assumptions:
- **10 queries per user per month**
- **Qdrant:** Free tier for dev/small; paid tier at medium+ (~$25–70/mo)
- **Cohere:** Trial free for dev; production ~$0.001/query
- **GPT-4o-mini fallback** could reduce generation cost by ~10× if used as default

| Tier | Users | Queries/mo | Voyage | Qdrant | GPT-4o | Cohere | Total/mo |
|------|-------|------------|--------|--------|--------|---------|----------|
| Dev (current) | 1–2 | ~200 | $0 | $0 | ~$3 | $0 | **~$3** |
| Small (100) | 100 | ~1,000 | ~$0.001 | $0 | ~$15 | ~$1 | **~$16** |
| Medium (1K) | 1,000 | ~10,000 | ~$0.01 | ~$25 | ~$150 | ~$10 | **~$185** |
| Large (10K) | 10,000 | ~100,000 | ~$0.10 | ~$70 | ~$1,500 | ~$100 | **~$1,670** |

*Voyage stays negligible (query embedding only). GPT-4o dominates at scale.*

---

## 4. Cost Optimization Strategies

| Strategy | Impact | Implementation |
|----------|--------|----------------|
| **Embedding cache** | Saves Voyage on repeated queries | Cache query → vector; invalidate on codebase re-index |
| **GPT-4o-mini default** | ~10× cheaper generation | Use 4o-mini for simple queries; 4o for complex/feature-specific |
| **Skip Cohere for simple queries** | Saves Cohere cost | Metadata-only reranking is free; use Cohere only when confidence matters |
| **Reduce top_k** | Fewer chunks = less GPT input | Default 10; consider 5–7 for cost-sensitive deployments |
| **Context budget tuning** | Less input to LLM | `CONTEXT_BUDGET_TOKENS` (5,000) can be lowered for simpler answers |
| **Batch ingestion timing** | Avoid peak API rates | Re-index during off-peak; use Voyage Batch API (33% discount) |
| **Reserved capacity** | Predictable high-volume pricing | OpenAI Scale Tier / Voyage enterprise for fixed rates |

---

## 5. Infrastructure Costs

| Service | Tier | Monthly Cost | Notes |
|---------|------|--------------|-------|
| Render (API) | Free | $0 | Cold starts after inactivity; 750 hrs/mo |
| Vercel (Frontend) | Free | $0 | Hobby tier; serverless |
| Qdrant Cloud | Free | $0 | 1 cluster, limited storage |
| **Total infra (current)** | | **$0** | |

**At scale:**
- Render: Paid tier ~$7–25/mo for always-on
- Vercel: Pro ~$20/mo for team features
- Qdrant: Paid ~$25–70/mo for more storage and nodes

---

## 6. Summary

| Phase | Dominant Cost | Est. Total |
|-------|---------------|------------|
| Development | GPT-4o (queries) | ~$4.50 |
| Per query (production) | GPT-4o | ~$0.015 |
| 1K users/mo | GPT-4o | ~$185 |
| 10K users/mo | GPT-4o + infra | ~$1,670 |

**Key takeaway:** Embedding (Voyage) and reranking (Cohere) are low cost. Generation (GPT-4o) dominates. Switching to GPT-4o-mini as default would reduce query cost by ~90%.
