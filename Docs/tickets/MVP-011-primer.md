# MVP-011 Primer: COBOL-Aware Prompt Template

**For:** New Cursor Agent session  
**Project:** LegacyLens - RAG-Powered Legacy Code Intelligence System  
**Date:** Mar 3, 2026  
**Previous work:** MVP-010 (metadata reranker) should be complete and merged before starting this ticket. See `Docs/tickets/DEVLOG.md`.

---

## What Is This Ticket?

MVP-011 implements the **COBOL-aware prompt template layer** used by generation.

In MVP-009 and MVP-010, retrieval and reranking produce prioritized `RetrievedChunk` context. In MVP-011, that context must be assembled into robust prompt messages with strict citation and confidence instructions, so MVP-012 can call the LLM without redefining prompt logic.

### Why It Matters

- **Accuracy guardrail:** Prompt instructions reduce hallucination and force grounding in retrieved context.
- **Citation contract:** UI/API output quality depends on reliable `file:line` references.
- **Confidence consistency:** Prompt must enforce `HIGH / MEDIUM / LOW` confidence output.
- **Pipeline sequencing:** MVP-012 LLM caller should focus on transport/runtime, not prompt design.

---

## What Was Already Done

- MVP-003 detector is implemented (`src/ingestion/detector.py`)
- MVP-004 parser is implemented (`src/ingestion/cobol_parser.py`)
- MVP-005/006 chunking + metadata are implemented (`src/ingestion/cobol_chunker.py`)
- MVP-007 embedding is implemented (`src/ingestion/embedder.py`)
- MVP-008 indexing is implemented (`src/ingestion/indexer.py`)
- MVP-009 hybrid search should be implemented (`src/retrieval/search.py`)
- MVP-010 reranker should be implemented (`src/retrieval/reranker.py`)
- Response dataclasses already exist in `src/types/responses.py`:
  - `RetrievedChunk`
  - `Confidence`
  - `QueryResponse`
- Feature names already exist in `src/config.py` (`FEATURES`)
- Prompt module placeholder exists:
  - `src/generation/prompts.py`
- Test placeholder exists:
  - `tests/test_generation.py`

---

## Prompt Template Contract (Critical Reference)

MVP-011 should define stable prompt-building APIs in `src/generation/prompts.py`:

```python
build_system_prompt(
    feature: str = "code_explanation",
    language: str = "cobol",
) -> str
```

```python
build_user_prompt(
    query: str,
    chunks: list[RetrievedChunk],
) -> str
```

```python
build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
) -> list[dict[str, str]]
```

Expected behavior:

- produce deterministic system instructions tuned for COBOL context
- enforce citation requirement (`file:line` references)
- enforce confidence labels (`HIGH`, `MEDIUM`, `LOW`)
- include retrieved chunk evidence in user/context prompt
- avoid LLM API calls inside prompt module

Hard requirements from project rules:

- Generation ownership: `src/generation/prompts.py`
- Structured language-aware prompt is required
- All answers must include file:line citations
- Confidence output must be `HIGH / MEDIUM / LOW`
- No LangChain, no LlamaIndex

---

## What MVP-011 Must Accomplish

### Goal

Implement a production-ready prompt template module in `src/generation/prompts.py` that converts query + retrieved chunks into citation-grounded, language-aware prompt messages for MVP-012 LLM execution.

### Deliverables Checklist

#### A. Prompt Logic (`src/generation/prompts.py`)

- [ ] Create public prompt APIs:
  - `build_system_prompt(feature: str = "code_explanation", language: str = "cobol") -> str`
  - `build_user_prompt(query: str, chunks: list[RetrievedChunk]) -> str`
  - `build_messages(query: str, chunks: list[RetrievedChunk], feature: str = "code_explanation", language: str = "cobol") -> list[dict[str, str]]`
- [ ] Validate inputs:
  - blank query raises deterministic error
  - unsupported language raises deterministic error (or explicit fallback behavior)
- [ ] Implement COBOL-aware system template with:
  - role framing (legacy code intelligence assistant)
  - strict grounding rule ("use provided context only")
  - citation requirement (`file:line` format)
  - confidence requirement (`HIGH / MEDIUM / LOW`)
  - explicit uncertainty behavior when evidence is insufficient
- [ ] Implement feature-aware prompt insert strategy:
  - at minimum support `code_explanation`
  - deterministic fallback for unknown feature names
- [ ] Implement context formatting helper:
  - include file path, line range, paragraph/section name when available
  - include chunk content in deterministic order
  - avoid crashes when metadata fields are missing
- [ ] Keep module generation-template-only:
  - no OpenAI call logic (MVP-012 scope)
  - no retrieval/rerank logic
  - no API route logic
  - no CLI route logic

#### B. Unit Tests (`tests/test_generation.py`)

- [ ] TDD first: write tests before implementation
- [ ] Test return contract:
  - system prompt returns `str`
  - user prompt returns `str`
  - messages return `list[dict[str, str]]`
- [ ] Test validation:
  - blank query raises deterministic error
  - unsupported language behavior is deterministic
- [ ] Test citation instruction presence:
  - system prompt requires `file:line` citations
- [ ] Test confidence instruction presence:
  - system prompt requires `HIGH/MEDIUM/LOW`
- [ ] Test context formatting:
  - includes `file_path`, `line_start`, `line_end`
  - includes chunk content snippets
- [ ] Test unknown feature fallback:
  - still returns valid prompt with deterministic defaults
- [ ] Test empty chunk list behavior:
  - prompt still valid and instructs uncertainty appropriately
- [ ] Test deterministic output:
  - identical inputs produce identical prompt strings
- [ ] Minimum: 10+ focused tests

#### C. Integration Expectations

- [ ] Consumes `list[RetrievedChunk]` outputs from retrieval/rerank modules unchanged in shape
- [ ] Produces prompt messages ready for MVP-012 OpenAI chat call
- [ ] Prompt contract aligns with final API/UI expectations for citations and confidence
- [ ] Compatible with current MVP COBOL scope and future multi-language extension

#### D. Documentation

- [ ] Add MVP-011 entry in `Docs/tickets/DEVLOG.md` when complete
- [ ] Document system prompt structure and citation/confidence assumptions
- [ ] Record helper signatures introduced in `prompts.py`
- [ ] Note deterministic fallback behavior for missing context or unknown feature

---

## Branch & Merge Workflow (Required)

- Create a dedicated branch before code changes:
  - `git switch main && git pull`
  - `git switch -c feature/mvp-011-cobol-prompt-template`
- Never commit directly to `main` for ticket work.
- Commit in small increments with Conventional Commits:
  - `test:`, `feat:`, `fix:`, `docs:`, `refactor:`
- Push and open PR when Definition of Done is met:
  - `git push -u origin feature/mvp-011-cobol-prompt-template`
- Merge to `main` only after checks/review pass.

---

## Important Context

### Files to Modify

| File | Action |
|------|--------|
| `src/generation/prompts.py` | Implement prompt templates, context formatting, and message builder |
| `tests/test_generation.py` | Add prompt-focused unit tests |
| `Docs/tickets/DEVLOG.md` | Add MVP-011 completion entry (after done) |

### Files You May Need to Create

| File | Why |
|------|-----|
| `src/generation/__init__.py` | Package entry if exports are needed |

### Files You Should NOT Modify

- `src/retrieval/search.py` (MVP-009 scope)
- `src/retrieval/reranker.py` (MVP-010 scope)
- `src/generation/llm.py` (MVP-012 scope)
- `src/api/*` (MVP-013 scope)
- `src/cli/*` (MVP-014 scope)
- `src/ingestion/*` modules (MVP-003 through MVP-008 are complete)
- Deployment config files (`Dockerfile`, `render.yaml`)

### Files You Should READ for Context

| File | Why |
|------|-----|
| `src/types/responses.py` | `RetrievedChunk` and `Confidence` contracts |
| `src/config.py` | feature names and model/config constants |
| `src/retrieval/search.py` | upstream retrieval output assumptions |
| `src/retrieval/reranker.py` | confidence/citation expectations from reranked chunks |
| `.cursor/rules/rag-pipeline.mdc` | generation/citation constraints |
| `.cursor/rules/tdd.mdc` | test-first workflow requirements |
| `.cursor/rules/code-patterns.mdc` | module ownership and typing conventions |

### Cursor Rules to Follow

- `.cursor/rules/tdd.mdc` - test-first workflow
- `.cursor/rules/code-patterns.mdc` - module ownership + typing conventions
- `.cursor/rules/rag-pipeline.mdc` - generation/citation/confidence constraints
- `.cursor/rules/tech-stack.mdc` - strict stack requirements
- `.cursor/rules/multi-codebase.mdc` - preserve future cross-codebase compatibility

---

## Suggested Implementation Pattern

### Main Public Contract

```python
def build_system_prompt(
    feature: str = "code_explanation",
    language: str = "cobol",
) -> str:
```

```python
def build_user_prompt(
    query: str,
    chunks: list[RetrievedChunk],
) -> str:
```

```python
def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    feature: str = "code_explanation",
    language: str = "cobol",
) -> list[dict[str, str]]:
```

### Processing Flow

```python
def build_messages(query, chunks, feature="code_explanation", language="cobol"):
    _validate_prompt_inputs(query=query, feature=feature, language=language)

    system_prompt = build_system_prompt(feature=feature, language=language)
    user_prompt = build_user_prompt(query=query, chunks=chunks)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
```

Suggested helper responsibilities:

- `_validate_prompt_inputs(query: str, feature: str, language: str) -> None`
- `_feature_prompt_insert(feature: str) -> str`
- `_language_prompt_insert(language: str) -> str`
- `_citation_instruction_block() -> str`
- `_confidence_instruction_block() -> str`
- `_format_context_chunks(chunks: list[RetrievedChunk]) -> str`
- `_format_chunk_citation(chunk: RetrievedChunk) -> str`

### System Prompt Strategy

Keep prompt deterministic and explicit:

- include a strict grounding rule ("do not invent behavior not in evidence")
- require inline or line-item citations in `file:line` format
- require confidence label exactly as one of `HIGH`, `MEDIUM`, `LOW`
- require uncertainty statement when context is insufficient
- keep instructions short, directive, and testable

### Context Formatting Strategy

Format each chunk using stable, parseable structure:

- header: source + line range + optional name
- body: raw chunk content
- deterministic ordering by incoming chunk order
- safe fallbacks when fields are missing (avoid crashes)

Example format (illustrative):

```text
[Chunk 1]
Source: data/raw/gnucobol/sample.cob:10-20
Name: MAIN-LOGIC
Content:
MAIN-LOGIC. PERFORM INIT-DATA.
```

---

## Edge Cases to Handle

1. **Blank query:** raise actionable validation error
2. **Unsupported language:** deterministic error or explicit fallback (documented in tests)
3. **Unknown feature:** deterministic fallback insert
4. **Empty chunk list:** prompt still valid with uncertainty guidance
5. **Missing chunk metadata fields:** safe fallback formatting without KeyError
6. **Line range anomalies (`line_end < line_start`):** deterministic formatting fallback
7. **Very large chunk content:** deterministic truncation policy (if applied) documented in tests
8. **Non-ASCII in legacy source:** preserve content safely without prompt-builder crash
9. **Repeated chunks:** deterministic output ordering remains stable

---

## Test Fixture Suggestions

```python
@pytest.fixture
def sample_retrieved_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            content="MAIN-LOGIC. PERFORM INIT-DATA.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=10,
            line_end=11,
            name="MAIN-LOGIC",
            language="cobol",
            codebase="gnucobol",
            score=0.82,
            confidence=Confidence.HIGH,
            metadata={"division": "PROCEDURE", "paragraph_name": "MAIN-LOGIC"},
        ),
        RetrievedChunk(
            content="INIT-DATA. MOVE 1 TO WS-COUNT.",
            file_path="data/raw/gnucobol/sample.cob",
            line_start=20,
            line_end=21,
            name="INIT-DATA",
            language="cobol",
            codebase="gnucobol",
            score=0.74,
            confidence=Confidence.MEDIUM,
            metadata={"division": "PROCEDURE", "paragraph_name": "INIT-DATA"},
        ),
    ]
```

Core assertions:

- system prompt contains citation and confidence instructions
- message list has deterministic role ordering (`system`, `user`)
- context block includes `file_path` + line ranges from chunks
- unknown feature/language behavior is deterministic and tested
- outputs are stable across repeated calls

---

## Definition of Done for MVP-011

- [ ] `src/generation/prompts.py` implemented with stable prompt-building APIs
- [ ] COBOL-aware system template implemented with explicit citation/confidence rules
- [ ] Context formatting from `RetrievedChunk` implemented with deterministic output
- [ ] Unit tests added and passing in `tests/test_generation.py`
- [ ] TDD flow followed (failing tests first, then pass)
- [ ] DEVLOG updated with MVP-011 entry
- [ ] Work completed on `feature/mvp-011-cobol-prompt-template` and merged via PR

---

## Estimated Time: 45-75 minutes

| Task | Estimate |
|------|----------|
| Review generation constraints + retrieval contracts | 10-15 min |
| Write failing prompt-template tests | 15-25 min |
| Implement prompt/system/context builders | 15-20 min |
| Edge-case handling + test fixes | 5-10 min |
| DEVLOG update | 5-10 min |

---

## After MVP-011: What Comes Next

- **MVP-012:** LLM generation module (`src/generation/llm.py`) with GPT-4o call path + fallback behavior
- **MVP-013:** FastAPI query route wiring retrieval + rerank + prompt + generation

MVP-011 should leave generation inputs deterministic and citation-enforced so MVP-012 can focus on runtime model invocation, retries, and response parsing without changing prompt contracts.
