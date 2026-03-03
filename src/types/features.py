"""Feature configuration types for LegacyLens."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeatureConfig:
    """Configuration for a config-driven code understanding feature."""

    name: str
    display_name: str
    system_prompt: str
    top_k: int = 10
    retrieval_strategy: str = "hybrid"
    rerank: bool = True
    metadata_filters: dict[str, str] = field(default_factory=dict)
    max_context_tokens: int = 5000


@dataclass
class FeatureResponse:
    """Output from a feature handler."""

    feature: str
    answer: str
    chunks_used: int
    confidence: str
    citations: list[str] = field(default_factory=list)
