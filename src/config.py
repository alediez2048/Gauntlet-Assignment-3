"""LegacyLens configuration — environment variables and constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# --- API Keys ---
VOYAGE_API_KEY: str = os.getenv("VOYAGE_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

# --- Model Configuration ---
EMBEDDING_MODEL: str = os.getenv("LEGACYLENS_EMBEDDING_MODEL", "voyage-code-2")
EMBEDDING_DIMENSIONS: int = 1536
EMBEDDING_BATCH_SIZE: int = 128

LLM_MODEL: str = os.getenv("LEGACYLENS_LLM_MODEL", "gpt-4o")
LLM_FALLBACK_MODEL: str = os.getenv("LEGACYLENS_LLM_FALLBACK_MODEL", "gpt-4o-mini")

# --- Qdrant ---
QDRANT_COLLECTION_NAME: str = os.getenv("LEGACYLENS_COLLECTION", "legacylens")

# --- Chunking ---
CHUNK_MIN_TOKENS: int = 64
CHUNK_MAX_TOKENS: int = 768
TIKTOKEN_ENCODING: str = "cl100k_base"

# --- Retrieval ---
DEFAULT_TOP_K: int = 10
CONTEXT_BUDGET_TOKENS: int = 5000
TOP1_EXPANSION_BUDGET: int = 2000

# --- Codebase Registry ---
CODEBASES: dict[str, dict] = {
    "gnucobol": {
        "language": "cobol",
        "extensions": [".cob", ".cbl", ".cpy"],
        "preprocessor": "cobol",
        "chunker": "cobol_paragraph",
        "description": "Open source COBOL compiler",
    },
    "gfortran": {
        "language": "fortran",
        "extensions": [".f", ".f90", ".f77", ".f95"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Fortran compiler in GCC",
    },
    "lapack": {
        "language": "fortran",
        "extensions": [".f", ".f90"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Linear algebra library",
    },
    "blas": {
        "language": "fortran",
        "extensions": [".f"],
        "preprocessor": "fortran",
        "chunker": "fortran_subroutine",
        "description": "Basic linear algebra subprograms",
    },
    "opencobol-contrib": {
        "language": "cobol",
        "extensions": [".cob", ".cbl", ".cpy"],
        "preprocessor": "cobol",
        "chunker": "cobol_paragraph",
        "description": "Sample COBOL programs and utilities",
    },
}

# --- Feature Names ---
FEATURES: list[str] = [
    "code_explanation",
    "dependency_mapping",
    "pattern_detection",
    "impact_analysis",
    "documentation_gen",
    "translation_hints",
    "bug_pattern_search",
    "business_logic",
]

# --- API ---
API_HOST: str = os.getenv("LEGACYLENS_API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("LEGACYLENS_API_PORT", "8000"))
LEGACYLENS_API_URL: str = os.getenv(
    "LEGACYLENS_API_URL", f"http://{API_HOST}:{API_PORT}"
)
