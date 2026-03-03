"""Language detection and processing dispatch for legacy source files.

Builds an extension map from the codebase registry in src.config so that
routing stays in sync with configuration and avoids hardcoded duplicates.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

from src.config import CODEBASES

logger = logging.getLogger(__name__)


class ProcessingRoute(TypedDict):
    """Dispatch metadata returned by get_processing_route."""

    language: str
    codebase: str
    preprocessor: str
    chunker: str
    extension: str


def _build_extension_map() -> dict[str, list[ProcessingRoute]]:
    """Build a mapping from lowercase extension to possible processing routes.

    Each extension may map to multiple codebases (e.g. ".f" appears in
    gfortran, lapack, and blas), so we store a list of routes per extension.
    """
    ext_map: dict[str, list[ProcessingRoute]] = {}
    for codebase_name, info in CODEBASES.items():
        for ext in info["extensions"]:
            route: ProcessingRoute = {
                "language": info["language"],
                "codebase": codebase_name,
                "preprocessor": info["preprocessor"],
                "chunker": info["chunker"],
                "extension": ext,
            }
            ext_map.setdefault(ext.lower(), []).append(route)
    return ext_map


_EXTENSION_MAP: dict[str, list[ProcessingRoute]] = _build_extension_map()


def detect_language(path: str | Path) -> str | None:
    """Detect the source language of a file from its extension.

    Args:
        path: File path (only the extension is inspected).

    Returns:
        ``"cobol"``, ``"fortran"``, or ``None`` for unsupported extensions.
    """
    ext = Path(path).suffix.lower()
    routes = _EXTENSION_MAP.get(ext)
    if routes:
        return routes[0]["language"]
    if ext:
        logger.warning("Unsupported file extension '%s' for path: %s", ext, path)
    else:
        logger.warning("No file extension for path: %s", path)
    return None


def get_processing_route(path: str | Path) -> ProcessingRoute | None:
    """Return dispatch metadata for a file based on its extension.

    The returned dict contains ``language``, ``codebase``, ``preprocessor``,
    ``chunker``, and the matched ``extension``.  When an extension maps to
    multiple codebases, the first registered codebase is returned — callers
    that need a specific codebase should pass an explicit codebase filter.

    Args:
        path: File path (only the extension is inspected).

    Returns:
        A :class:`ProcessingRoute` dict, or ``None`` for unsupported files.
    """
    ext = Path(path).suffix.lower()
    routes = _EXTENSION_MAP.get(ext)
    if routes:
        route = dict(routes[0])
        route["extension"] = ext
        return route  # type: ignore[return-value]
    if ext:
        logger.warning("Unsupported file extension '%s' for path: %s", ext, path)
    else:
        logger.warning("No file extension for path: %s", path)
    return None


def is_supported_source_file(path: str | Path) -> bool:
    """Check whether a file has a recognized legacy-language extension.

    Args:
        path: File path to check.

    Returns:
        ``True`` if the extension maps to a supported language, ``False`` otherwise.
    """
    ext = Path(path).suffix.lower()
    return ext in _EXTENSION_MAP
