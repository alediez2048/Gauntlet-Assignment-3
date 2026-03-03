# LegacyLens — Claude Code Context

## Build Commands
```
pip install -r requirements.txt
cd frontend && npm install
```

## Test Command
```
python -m pytest tests/ -v
```

## Lint Command
```
ruff check . --fix
```

## Dev Server (API)
```
uvicorn src.api.app:app --reload --port 8000
```

## Dev Server (Web)
```
cd frontend && npm run dev
```

## CLI
```
python -m src.cli.main
```

## Evaluate
```
python evaluation/evaluate.py --dataset evaluation/ground_truth.json
```

## Project Summary
LegacyLens is a custom RAG pipeline (no LangChain/LlamaIndex) that makes
legacy COBOL and Fortran codebases queryable through natural language.
5 codebases, 8 code understanding features, dual CLI + web interface.
Qdrant for vectors, Voyage Code 2 for embeddings, GPT-4o for generation.
