"""Unit tests for the COBOL preprocessor (MVP-004).

Tests column stripping, comment extraction, continuation handling,
encoding detection, and edge cases for preprocess_cobol().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.cobol_parser import preprocess_cobol
from src.types.chunks import ProcessedFile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def classic_cobol_file(tmp_path: Path) -> Path:
    """Fixed-format COBOL with sequence numbers, indicators, and identification area."""
    content = (
        "000100 IDENTIFICATION DIVISION.                                        PROG01\n"
        "000200 PROGRAM-ID. TEST-PROG.                                         PROG01\n"
        "000300*THIS IS A COMMENT LINE                                         PROG01\n"
        "000400 PROCEDURE DIVISION.                                            PROG01\n"
        "000500 MAIN-LOGIC.                                                    PROG01\n"
        "000600     DISPLAY \"HELLO\".                                           PROG01\n"
        "000700     STOP RUN.                                                  PROG01\n"
    )
    p = tmp_path / "test.cob"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def continuation_file(tmp_path: Path) -> Path:
    """COBOL with continuation line (col 7 = '-')."""
    content = (
        "000100     MOVE \"THIS IS A VERY LONG LI                              PROG01\n"
        "000200-    \"TERAL VALUE\" TO WS-FIELD.                                PROG01\n"
    )
    p = tmp_path / "cont.cob"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def comment_variants_file(tmp_path: Path) -> Path:
    """All comment indicator types: *, /, D."""
    content = (
        "000100*FULL LINE COMMENT                                              PROG01\n"
        "000200/PAGE BREAK COMMENT                                             PROG01\n"
        "000300DDEBUG LINE                                                     PROG01\n"
        "000400 NORMAL CODE LINE.                                              PROG01\n"
    )
    p = tmp_path / "comments.cob"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def free_format_comment_file(tmp_path: Path) -> Path:
    """Modern GnuCOBOL *> inline comment style."""
    content = (
        "      *> This is a free-format comment\n"
        "       IDENTIFICATION DIVISION. *> inline comment\n"
        "       PROGRAM-ID. TEST.\n"
    )
    p = tmp_path / "free.cob"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    """Empty COBOL file."""
    p = tmp_path / "empty.cob"
    p.write_text("", encoding="utf-8")
    return p


@pytest.fixture
def short_lines_file(tmp_path: Path) -> Path:
    """File with lines shorter than 7 characters."""
    content = "A\nBC\n\nXYZ\n"
    p = tmp_path / "short.cob"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Column Stripping Tests
# ---------------------------------------------------------------------------


class TestColumnStripping:
    """Tests that cols 1-6 and 73-80 are stripped, code area preserved."""

    def test_sequence_numbers_removed(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert "000100" not in result.code
        assert "000200" not in result.code
        assert "000700" not in result.code

    def test_identification_area_removed(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert "PROG01" not in result.code

    def test_code_area_preserved(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert "IDENTIFICATION DIVISION." in result.code
        assert "PROGRAM-ID. TEST-PROG." in result.code
        assert "PROCEDURE DIVISION." in result.code
        assert "DISPLAY \"HELLO\"." in result.code
        assert "STOP RUN." in result.code


# ---------------------------------------------------------------------------
# Comment Detection Tests
# ---------------------------------------------------------------------------


class TestCommentDetection:
    """Tests that col-7 indicators correctly separate comments from code."""

    def test_star_comment_extracted(self, comment_variants_file: Path) -> None:
        result = preprocess_cobol(comment_variants_file)
        assert any("FULL LINE COMMENT" in c for c in result.comments)

    def test_slash_comment_extracted(self, comment_variants_file: Path) -> None:
        result = preprocess_cobol(comment_variants_file)
        assert any("PAGE BREAK COMMENT" in c for c in result.comments)

    def test_debug_line_extracted(self, comment_variants_file: Path) -> None:
        result = preprocess_cobol(comment_variants_file)
        assert any("DEBUG LINE" in c for c in result.comments)

    def test_normal_code_not_in_comments(self, comment_variants_file: Path) -> None:
        result = preprocess_cobol(comment_variants_file)
        assert not any("NORMAL CODE LINE" in c for c in result.comments)
        assert "NORMAL CODE LINE." in result.code

    def test_comment_not_in_code(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert "THIS IS A COMMENT LINE" not in result.code
        assert any("THIS IS A COMMENT LINE" in c for c in result.comments)


# ---------------------------------------------------------------------------
# Free-Format (*>) Comment Tests
# ---------------------------------------------------------------------------


class TestFreeFormatComments:
    """Tests for modern GnuCOBOL *> inline comment style."""

    def test_standalone_free_comment_extracted(
        self, free_format_comment_file: Path
    ) -> None:
        result = preprocess_cobol(free_format_comment_file)
        assert any("This is a free-format comment" in c for c in result.comments)

    def test_inline_free_comment_extracted(
        self, free_format_comment_file: Path
    ) -> None:
        result = preprocess_cobol(free_format_comment_file)
        assert any("inline comment" in c for c in result.comments)

    def test_code_before_inline_comment_preserved(
        self, free_format_comment_file: Path
    ) -> None:
        result = preprocess_cobol(free_format_comment_file)
        assert "IDENTIFICATION DIVISION." in result.code


# ---------------------------------------------------------------------------
# Continuation Handling Tests
# ---------------------------------------------------------------------------


class TestContinuationHandling:
    """Tests that col-7 '-' appends content to previous line."""

    def test_continuation_joins_lines(self, continuation_file: Path) -> None:
        result = preprocess_cobol(continuation_file)
        lines = result.code.splitlines()
        joined = " ".join(lines)
        assert "\"TERAL VALUE\" TO WS-FIELD." in joined

    def test_continuation_not_separate_line(self, continuation_file: Path) -> None:
        result = preprocess_cobol(continuation_file)
        code_lines = [ln for ln in result.code.splitlines() if ln.strip()]
        assert len(code_lines) == 1


# ---------------------------------------------------------------------------
# Encoding Detection Tests
# ---------------------------------------------------------------------------


class TestEncodingDetection:
    """Tests chardet-based encoding detection."""

    def test_utf8_detected(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert result.encoding.lower().replace("-", "") in ("utf8", "ascii")

    def test_low_confidence_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "binary.cob"
        p.write_bytes(bytes(range(256)) * 4)
        result = preprocess_cobol(p)
        assert result.code == ""
        assert result.comments == []


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for short lines, empty files, and boundary conditions."""

    def test_empty_file(self, empty_file: Path) -> None:
        result = preprocess_cobol(empty_file)
        assert isinstance(result, ProcessedFile)
        assert result.code == ""
        assert result.comments == []
        assert result.language == "cobol"

    def test_short_lines_no_crash(self, short_lines_file: Path) -> None:
        result = preprocess_cobol(short_lines_file)
        assert isinstance(result, ProcessedFile)

    def test_line_exactly_72_chars(self, tmp_path: Path) -> None:
        line = "000100 " + "X" * 65 + "\n"
        assert len(line.rstrip("\n")) == 72
        p = tmp_path / "exact72.cob"
        p.write_text(line, encoding="utf-8")
        result = preprocess_cobol(p)
        assert "X" * 65 in result.code


# ---------------------------------------------------------------------------
# Return Type / Contract Tests
# ---------------------------------------------------------------------------


class TestReturnContract:
    """Tests that the return value conforms to ProcessedFile contract."""

    def test_returns_processed_file(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert isinstance(result, ProcessedFile)

    def test_language_is_cobol(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert result.language == "cobol"

    def test_file_path_set(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert result.file_path == str(classic_cobol_file)

    def test_encoding_set(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert isinstance(result.encoding, str)
        assert len(result.encoding) > 0

    def test_accepts_string_path(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(str(classic_cobol_file))
        assert isinstance(result, ProcessedFile)

    def test_accepts_path_object(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file)
        assert isinstance(result, ProcessedFile)

    def test_codebase_in_metadata(self, classic_cobol_file: Path) -> None:
        result = preprocess_cobol(classic_cobol_file, codebase="gnucobol")
        assert isinstance(result.metadata, dict)
