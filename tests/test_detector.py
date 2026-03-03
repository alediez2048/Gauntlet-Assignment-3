"""Unit tests for the language detection and dispatch module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.detector import detect_language, get_processing_route, is_supported_source_file


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    """Tests for detect_language(path) -> str | None."""

    @pytest.mark.parametrize("ext", [".cob", ".cbl", ".cpy"])
    def test_cobol_extensions(self, ext: str) -> None:
        assert detect_language(Path(f"some/path/file{ext}")) == "cobol"

    @pytest.mark.parametrize("ext", [".f", ".f90", ".f77", ".f95"])
    def test_fortran_extensions(self, ext: str) -> None:
        assert detect_language(Path(f"some/path/file{ext}")) == "fortran"

    def test_unknown_extension_returns_none(self) -> None:
        assert detect_language(Path("README.md")) is None

    def test_no_extension_returns_none(self) -> None:
        assert detect_language(Path("Makefile")) is None

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("FILE.CBL", "cobol"),
            ("routine.F90", "fortran"),
            ("PROG.COB", "cobol"),
            ("module.F95", "fortran"),
        ],
    )
    def test_case_insensitive(self, filename: str, expected: str) -> None:
        assert detect_language(Path(filename)) == expected

    def test_accepts_string_path(self) -> None:
        assert detect_language("data/raw/gnucobol/main.cob") == "cobol"


# ---------------------------------------------------------------------------
# get_processing_route
# ---------------------------------------------------------------------------


class TestGetProcessingRoute:
    """Tests for get_processing_route(path) -> dict | None."""

    def test_cobol_route_structure(self) -> None:
        route = get_processing_route(Path("gnucobol/main.cbl"))
        assert route is not None
        assert route["language"] == "cobol"
        assert route["preprocessor"] == "cobol"
        assert route["chunker"] == "cobol_paragraph"
        assert "extension" in route

    def test_fortran_route_structure(self) -> None:
        route = get_processing_route(Path("gfortran/solver.f90"))
        assert route is not None
        assert route["language"] == "fortran"
        assert route["preprocessor"] == "fortran"
        assert route["chunker"] == "fortran_subroutine"
        assert "extension" in route

    def test_unknown_extension_returns_none(self) -> None:
        assert get_processing_route(Path("notes.txt")) is None

    def test_route_contains_extension_field(self) -> None:
        route = get_processing_route(Path("foo.f77"))
        assert route is not None
        assert route["extension"] == ".f77"

    def test_case_insensitive_route(self) -> None:
        route = get_processing_route(Path("PROG.CPY"))
        assert route is not None
        assert route["language"] == "cobol"


# ---------------------------------------------------------------------------
# is_supported_source_file
# ---------------------------------------------------------------------------


class TestIsSupportedSourceFile:
    """Tests for is_supported_source_file(path) -> bool."""

    @pytest.mark.parametrize("ext", [".cob", ".cbl", ".cpy", ".f", ".f90", ".f77", ".f95"])
    def test_supported_extensions(self, ext: str) -> None:
        assert is_supported_source_file(Path(f"file{ext}")) is True

    @pytest.mark.parametrize("ext", [".py", ".txt", ".md", ".c", ".java", ""])
    def test_unsupported_extensions(self, ext: str) -> None:
        filename = f"file{ext}" if ext else "Makefile"
        assert is_supported_source_file(Path(filename)) is False

    def test_case_insensitive(self) -> None:
        assert is_supported_source_file(Path("MAIN.CBL")) is True
