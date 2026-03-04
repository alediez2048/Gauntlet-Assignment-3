# LegacyLens

**RAG-Powered Legacy Code Intelligence System**

> Make 850,000+ lines of COBOL and Fortran queryable through natural language.

## Overview

LegacyLens is a Retrieval-Augmented Generation system that helps developers understand legacy enterprise codebases. Ask questions in natural language, get cited answers with file:line references.

### Codebases Indexed

| Codebase | Language | Description |
|---|---|---|
| GnuCOBOL | COBOL | Open source COBOL compiler |
| GNU Fortran | Fortran | Fortran compiler in GCC |
| LAPACK | Fortran | Linear algebra library |
| BLAS | Fortran | Basic linear algebra subprograms |
| OpenCOBOL Contrib | COBOL | Sample COBOL programs |

### Features

1. **Code Explanation** — Plain English explanations with citations
2. **Dependency Mapping** — Trace PERFORM/CALL chains
3. **Pattern Detection** — Find similar code patterns across codebases
4. **Impact Analysis** — What breaks if this code changes?
5. **Documentation Gen** — Auto-generate docs for undocumented code
6. **Translation Hints** — Modern language equivalents (Python default)
7. **Bug Pattern Search** — Find anti-patterns with severity levels
8. **Business Logic Extract** — Identify business rules in plain English

## Quick Start

### Prerequisites
- Python 3.11+
- API keys: Voyage AI, OpenAI, Cohere, Qdrant Cloud

### Setup

```bash
# Clone and install
git clone <repo-url>
cd legacylens
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the API server
uvicorn src.api.app:app --reload --port 8000

# Query via CLI
python -m src.cli.main query "What does CALCULATE-INTEREST do?"
```

### Web Interface

```bash
cd frontend
npm install
npm run dev
```

## Architecture

See [system-design.md](Docs/architecture/system-design.md) for the full data flow and component map.

**Tech Stack:** Python 3.11 · FastAPI · Qdrant · Voyage Code 2 · GPT-4o · Next.js 14 · Click + Rich

**Deployed:** API on Render (`render.yaml` + `Dockerfile`). See [Environment Guide](Docs/reference/ENVIRONMENT.md) for deployment and verification steps.

## Documentation

- [Architecture Document](Docs/architecture/architecture.md)
- [Cost Analysis](Docs/architecture/cost-analysis.md)
- [Pre-Search Document](Docs/requirements/pre-search.md)
- [System Design](Docs/architecture/system-design.md)
- [PRD](Docs/requirements/LegacyLens_PRD_Maximalist.md)
- [Interview Guide](Docs/interviews/LegacyLens_Maximalist_Interview_Guide.md)
- [Environment Guide](Docs/reference/ENVIRONMENT.md)
- [Dev Log](Docs/tickets/DEVLOG.md)

## License

MIT
