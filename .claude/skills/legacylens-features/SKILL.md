---
name: legacylens-features
description: Implementation guide for all 8 LegacyLens code understanding features — routing, retrieval strategies, prompt design, and output format. Use when implementing or modifying src/features/ modules, adding new features, working on the feature router, or building feature-specific prompt templates in src/generation/prompts.py.
---

# LegacyLens Code Understanding Features

## Architecture

All 8 features follow this pattern:

1. Feature router receives `(query, feature_name, codebase_filter)` from the API
2. Router dispatches to the correct handler
3. Handler may customize retrieval (different `top_k`, filters, or search strategy)
4. Handler provides a feature-specific system prompt
5. LLM generates a response with citations
6. Handler returns a `FeatureResponse`

Feature logic lives in `src/features/`. Prompt templates live in `src/generation/prompts.py`. The router lives in `src/features/router.py`.

## Feature Router (`router.py`)

Map `feature` param to handler. Default to `code_explanation` for unknown values:

```python
FEATURE_HANDLERS = {
    "code_explanation": handle_code_explanation,
    "dependency_mapping": handle_dependency_mapping,
    "pattern_detection": handle_pattern_detection,
    "impact_analysis": handle_impact_analysis,
    "documentation_gen": handle_documentation_gen,
    "translation_hints": handle_translation_hints,
    "bug_pattern_search": handle_bug_pattern_search,
    "business_logic": handle_business_logic,
}
```

Every feature must be accessible via both the API (`/api/query` with `feature` param) and the CLI (`legacylens query --feature <name>`).

## Feature Specifications

For detailed retrieval strategies and prompt patterns per feature, see [references/feature-specs.md](references/feature-specs.md).

Quick reference:

| # | Feature | Retrieval | Type |
|---|---------|-----------|------|
| 1 | code_explanation | Standard hybrid search | Config-driven |
| 2 | dependency_mapping | PERFORM/CALL regex + metadata filter | Custom module |
| 3 | pattern_detection | Top-30 search + LLM grouping | Custom module |
| 4 | impact_analysis | Reverse metadata lookup + LLM | Custom module |
| 5 | documentation_gen | Hierarchical context expansion | Config-driven |
| 6 | translation_hints | Language-specific prompt (Python default) | Config-driven |
| 7 | bug_pattern_search | 14-pattern checklist + BM25 keyword search | Config-driven |
| 8 | business_logic | PROCEDURE DIVISION focus | Config-driven |

## Config-Driven Features

5 of 8 features use `FeatureConfig` from `src/types/features.py` — they differ only in their system prompt and minor retrieval tuning:

```python
FeatureConfig(
    name="code_explanation",
    display_name="Code Explanation",
    system_prompt="...",
    top_k=10,
    retrieval_strategy="hybrid",
    rerank=True,
)
```

## Custom Features

3 features need custom retrieval logic beyond config-driven:

- **dependency_mapping**: Parse PERFORM/CALL from retrieved chunks, then search for those targets
- **pattern_detection**: Retrieve top-30 (not top-10), cluster by embedding similarity, group results
- **impact_analysis**: Reverse lookup — find all chunks whose `dependencies` field contains the target

## Output Contract

Every feature returns `FeatureResponse`:

```python
FeatureResponse(
    feature=str,        # feature name
    answer=str,         # LLM-generated answer
    chunks_used=int,    # number of chunks in context
    confidence=str,     # "HIGH" | "MEDIUM" | "LOW"
    citations=list[str] # ["file_path:line_start-line_end", ...]
)
```

## Citation Format

All citations must follow: `file_path:line_start-line_end`

Example: `src/cobol/CALCULATE-INTEREST.cob:45-67`

## Prompt Design Rules

- Every prompt must instruct the LLM to answer ONLY from the provided context
- Every prompt must require `file:line` citations
- Every prompt must be language-aware (mention COBOL or Fortran specifics)
- Include a confidence instruction: "Rate your confidence as HIGH, MEDIUM, or LOW"
- Use structured output format in the prompt to make parsing reliable
