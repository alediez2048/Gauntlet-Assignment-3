"""FastAPI application entrypoint for LegacyLens."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as api_router
from src.config import CODEBASES

app = FastAPI(
    title="LegacyLens API",
    description="RAG-powered legacy code intelligence API.",
    version="0.1.0",
)

# Keep CORS open during early MVP development. Tighten per-env later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Basic health endpoint for Render health checks."""
    return {"status": "ok"}


@app.get("/api/codebases")
async def list_codebases() -> dict[str, list[dict[str, str]]]:
    """List configured codebases and language metadata."""
    items: list[dict[str, str]] = []
    for name, details in CODEBASES.items():
        items.append(
            {
                "name": name,
                "language": str(details.get("language", "")),
                "description": str(details.get("description", "")),
            }
        )
    return {"codebases": items}
