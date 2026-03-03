# Feature Specifications

## 1. Code Explanation

**Goal:** Explain what a function/paragraph/subroutine does in plain English.

**Retrieval:** Standard hybrid search, top-10, full re-ranking pipeline.

**Prompt pattern:**
```
You are a legacy code expert. Explain the following {language} code in plain English.
Focus on: what it does, what data it operates on, and why it matters in the program flow.
Cite every claim with file:line references.
```

**Output:** Narrative explanation with inline citations.

---

## 2. Dependency Mapping

**Goal:** Trace PERFORM/CALL chains — show what calls what and data flow.

**Retrieval:** Custom two-stage:
1. Standard search for the target paragraph/subroutine
2. Parse `dependencies` from retrieved chunks
3. Search for each dependency to build the call chain

**Prompt pattern:**
```
Given the following {language} code, map all dependencies:
- For COBOL: list all PERFORM and CALL targets
- For Fortran: list all CALL and USE targets
Show the call chain as a hierarchy. Cite file:line for each node.
```

**Output:** Hierarchical call chain with citations.

---

## 3. Pattern Detection

**Goal:** Find similar code patterns across the codebase(s).

**Retrieval:** Custom high-volume:
1. Search with top-30 (3x normal) to get a wide net
2. Cluster results by embedding similarity (cosine > 0.85)
3. Group clusters by pattern type
4. Present representative examples from each group

**Prompt pattern:**
```
Analyze the following code chunks and identify recurring patterns:
- Name each pattern
- Show 2-3 examples with file:line citations
- Note which codebases contain each pattern
Filter out false positives: similar embeddings != similar patterns.
```

**Output:** Named pattern groups with examples and citations.

---

## 4. Impact Analysis

**Goal:** What would break if this code changes?

**Retrieval:** Custom reverse-lookup:
1. Search for the target chunk
2. Query Qdrant for all chunks where `dependencies` contains the target name
3. For each dependent, also check its dependents (1 level deep)

**Prompt pattern:**
```
If the following {language} code were modified or removed, analyze the impact:
- List all direct callers (who PERFORMs/CALLs this)
- List indirect dependents (callers of callers, 1 level)
- Assess severity: CRITICAL (breaks program flow), MODERATE (affects data), LOW (cosmetic)
Cite file:line for every affected component.
```

**Output:** Impact tree with severity ratings and citations.

---

## 5. Documentation Gen

**Goal:** Auto-generate documentation for undocumented code.

**Retrieval:** Hierarchical context expansion:
1. Standard search for the target
2. Expand top-1 chunk aggressively (use full 2,000-token expansion budget)
3. Include enclosing section/division context

**Prompt pattern:**
```
Generate technical documentation for the following undocumented {language} code:
- Purpose and behavior
- Input/output parameters or data items
- Side effects
- Called by / calls
- Business context if inferrable
Format as a doc comment appropriate for the language.
```

**Output:** Formatted documentation block with citations.

---

## 6. Translation Hints

**Goal:** Suggest modern language equivalents.

**Retrieval:** Standard hybrid search, top-10.

**Prompt pattern:**
```
Suggest a modern {target_language} (default: Python) equivalent for the following {source_language} code.
- Show the original code with file:line citation
- Show the suggested modern equivalent
- Note any semantic differences or limitations
- Caveat: "These are suggestions, not guaranteed equivalents."
```

**Target language:** Python by default. Allow override via query param.

**Output:** Side-by-side original and suggested translation with caveats.

---

## 7. Bug Pattern Search

**Goal:** Find potential issues based on known anti-patterns.

**Retrieval:** BM25-heavy hybrid search (boost keyword matching for pattern names).

**14-pattern checklist:**
1. Unchecked file status after I/O
2. Missing null/space checks on data items
3. Hardcoded values that should be configurable
4. Dead code (unreachable paragraphs/subroutines)
5. Missing error handling on CALL statements
6. Implicit type conversions
7. Uninitialized variables
8. GO TO usage (spaghetti flow)
9. Missing STOP RUN / END markers
10. Duplicate paragraph/subroutine names
11. Oversized paragraphs (>200 lines)
12. Missing PERFORM THRU boundaries
13. Unused COPY members
14. Numeric overflow potential

**Prompt pattern:**
```
Scan the following {language} code for potential bugs and anti-patterns.
Check against the known pattern list. For each finding:
- Pattern name and severity (CRITICAL / WARNING / INFO)
- File:line citation
- Brief explanation of the risk
- Suggested fix
```

**Output:** Findings list with severity, citations, and fix suggestions.

---

## 8. Business Logic Extraction

**Goal:** Identify and explain business rules embedded in code.

**Retrieval:** Standard search with metadata filter on PROCEDURE DIVISION (COBOL) or main program/subroutine bodies (Fortran).

For COBOL: filter to chunks where `division` = "PROCEDURE DIVISION".
For Fortran: no division filter (business logic may be anywhere).

**Prompt pattern:**
```
Extract business rules from the following {language} code:
- Identify conditional logic that implements business rules (IF/EVALUATE/COMPUTE)
- For each rule: state the business rule in plain English
- Provide file:line citation
- Note any thresholds, rates, or magic numbers that represent business parameters
```

**Output:** Numbered business rules with plain English explanation and citations.
