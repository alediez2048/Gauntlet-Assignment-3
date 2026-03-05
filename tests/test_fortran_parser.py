"""Unit tests for the Fortran preprocessor (G4-001).

Tests fixed-form column stripping, free-form comment/continuation handling,
format detection, encoding detection, and edge cases for preprocess_fortran().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion import fortran_parser
from src.ingestion.fortran_parser import preprocess_fortran
from src.types.chunks import ProcessedFile


# ---------------------------------------------------------------------------
# Fixtures — Fixed-Form
# ---------------------------------------------------------------------------


@pytest.fixture
def fixed_form_file(tmp_path: Path) -> Path:
    """Fixed-form Fortran with col 1 comments, labels, code, and identification field."""
    content = (
        "C     THIS IS A COMMENT LINE                                           ID0001\n"
        "      PROGRAM HELLO                                                    ID0002\n"
        "  100 FORMAT(I5)                                                       ID0003\n"
        "      CALL SUBROUTINE_A                                                ID0004\n"
        "      END                                                              ID0005\n"
    )
    p = tmp_path / "test.f"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def fixed_continuation_file(tmp_path: Path) -> Path:
    """Fixed-form with continuation lines (non-blank col 6)."""
    content = (
        "      CALL VERY_LONG_SUBROUTINE(\n"
        "     &     ARG1, ARG2,\n"
        "     &     ARG3)\n"
    )
    p = tmp_path / "cont.f"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def fixed_comment_variants_file(tmp_path: Path) -> Path:
    """All col 1 comment indicator types: C, c, *."""
    content = (
        "C     UPPERCASE C COMMENT\n"
        "c     lowercase c comment\n"
        "*     ASTERISK COMMENT\n"
        "      X = 1\n"
    )
    p = tmp_path / "comments.f77"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures — Free-Form
# ---------------------------------------------------------------------------


@pytest.fixture
def free_form_file(tmp_path: Path) -> Path:
    """Free-form Fortran with inline and full-line ! comments."""
    content = (
        "! This is a full-line comment\n"
        "program hello\n"
        "  x = 1.0  ! inline comment\n"
        "  print *, x\n"
        "end program hello\n"
    )
    p = tmp_path / "test.f90"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def free_continuation_file(tmp_path: Path) -> Path:
    """Free-form with & continuation lines."""
    content = (
        "x = a + b + c + &\n"
        "    d + e + f\n"
    )
    p = tmp_path / "cont.f90"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def free_long_lines_file(tmp_path: Path) -> Path:
    """Free-form file with lines longer than 72 characters."""
    long_var = "x" * 100
    content = f"  {long_var} = 1.0\n"
    p = tmp_path / "long.f90"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures — Edge Cases
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    """Empty Fortran file."""
    p = tmp_path / "empty.f90"
    p.write_text("", encoding="utf-8")
    return p


@pytest.fixture
def short_lines_file(tmp_path: Path) -> Path:
    """File with lines shorter than 7 characters (fixed-form edge case)."""
    content = "A\nBC\n\nXYZ\n"
    p = tmp_path / "short.f"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixed-Form Comment Tests
# ---------------------------------------------------------------------------


class TestFixedFormComments:
    """Tests that col 1 C/c/* indicators correctly extract comments."""

    def test_uppercase_c_comment(self, fixed_comment_variants_file: Path) -> None:
        result = preprocess_fortran(fixed_comment_variants_file)
        assert any("UPPERCASE C COMMENT" in c for c in result.comments)

    def test_lowercase_c_comment(self, fixed_comment_variants_file: Path) -> None:
        result = preprocess_fortran(fixed_comment_variants_file)
        assert any("lowercase c comment" in c for c in result.comments)

    def test_asterisk_comment(self, fixed_comment_variants_file: Path) -> None:
        result = preprocess_fortran(fixed_comment_variants_file)
        assert any("ASTERISK COMMENT" in c for c in result.comments)

    def test_comment_not_in_code(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert "THIS IS A COMMENT LINE" not in result.code
        assert any("THIS IS A COMMENT LINE" in c for c in result.comments)


# ---------------------------------------------------------------------------
# Fixed-Form Column Stripping Tests
# ---------------------------------------------------------------------------


class TestFixedFormColumnStripping:
    """Tests that cols 1-5 (labels) and 73+ (identification) are stripped."""

    def test_label_field_stripped(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert "ID0001" not in result.code
        assert "ID0002" not in result.code
        assert "ID0005" not in result.code

    def test_identification_field_stripped(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert "ID0001" not in result.code

    def test_code_area_preserved(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert "PROGRAM HELLO" in result.code
        assert "CALL SUBROUTINE_A" in result.code
        assert "END" in result.code

    def test_format_statement_preserved(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert "FORMAT(I5)" in result.code


# ---------------------------------------------------------------------------
# Fixed-Form Continuation Tests
# ---------------------------------------------------------------------------


class TestFixedFormContinuation:
    """Tests that col 6 continuation joins lines correctly."""

    def test_continuation_joins_lines(self, fixed_continuation_file: Path) -> None:
        result = preprocess_fortran(fixed_continuation_file)
        joined = " ".join(result.code.splitlines())
        assert "ARG1" in joined
        assert "ARG3" in joined

    def test_continuation_not_separate_line(self, fixed_continuation_file: Path) -> None:
        result = preprocess_fortran(fixed_continuation_file)
        code_lines = [ln for ln in result.code.splitlines() if ln.strip()]
        assert len(code_lines) == 1


# ---------------------------------------------------------------------------
# Free-Form Comment Tests
# ---------------------------------------------------------------------------


class TestFreeFormComments:
    """Tests that ! comments are extracted properly in free-form."""

    def test_full_line_comment_extracted(self, free_form_file: Path) -> None:
        result = preprocess_fortran(free_form_file)
        assert any("This is a full-line comment" in c for c in result.comments)

    def test_inline_comment_extracted(self, free_form_file: Path) -> None:
        result = preprocess_fortran(free_form_file)
        assert any("inline comment" in c for c in result.comments)

    def test_code_before_inline_preserved(self, free_form_file: Path) -> None:
        result = preprocess_fortran(free_form_file)
        assert "x = 1.0" in result.code


# ---------------------------------------------------------------------------
# Free-Form Continuation Tests
# ---------------------------------------------------------------------------


class TestFreeFormContinuation:
    """Tests that & continuation joins lines correctly in free-form."""

    def test_ampersand_joins_lines(self, free_continuation_file: Path) -> None:
        result = preprocess_fortran(free_continuation_file)
        joined = " ".join(result.code.splitlines())
        assert "a + b + c" in joined
        assert "d + e + f" in joined

    def test_long_lines_preserved(self, free_long_lines_file: Path) -> None:
        result = preprocess_fortran(free_long_lines_file)
        assert "x" * 100 in result.code


# ---------------------------------------------------------------------------
# Format Detection Tests
# ---------------------------------------------------------------------------


class TestFormatDetection:
    """Tests that format is detected correctly by extension."""

    def test_dot_f_is_fixed(self, tmp_path: Path) -> None:
        p = tmp_path / "test.f"
        p.write_text("      X = 1\n", encoding="utf-8")
        result = preprocess_fortran(p)
        assert result.metadata.get("source_format") == "fixed"

    def test_dot_f90_is_free(self, tmp_path: Path) -> None:
        p = tmp_path / "test.f90"
        p.write_text("x = 1\n", encoding="utf-8")
        result = preprocess_fortran(p)
        assert result.metadata.get("source_format") == "free"

    def test_dot_f77_is_fixed(self, tmp_path: Path) -> None:
        p = tmp_path / "test.f77"
        p.write_text("      X = 1\n", encoding="utf-8")
        result = preprocess_fortran(p)
        assert result.metadata.get("source_format") == "fixed"

    def test_dot_f95_is_free(self, tmp_path: Path) -> None:
        p = tmp_path / "test.f95"
        p.write_text("x = 1\n", encoding="utf-8")
        result = preprocess_fortran(p)
        assert result.metadata.get("source_format") == "free"


# ---------------------------------------------------------------------------
# Encoding Detection Tests
# ---------------------------------------------------------------------------


class TestEncodingDetection:
    """Tests chardet-based encoding detection."""

    def test_valid_encoding_detected(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert isinstance(result.encoding, str)
        assert len(result.encoding) > 0

    def test_low_confidence_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "binary.f90"
        p.write_bytes(bytes(range(256)) * 4)
        result = preprocess_fortran(p)
        assert result.code == ""
        assert result.comments == []

    def test_utf7_detection_overridden_to_utf8(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        p = tmp_path / "utf7-misdetection.f90"
        source = "program demo\n  print *, 'ok'\nend program demo\n"
        p.write_bytes(source.encode("utf-8"))

        def fake_detect(_: bytes) -> dict[str, str | float]:
            return {"encoding": "UTF-7", "confidence": 0.99}

        monkeypatch.setattr(fortran_parser.chardet, "detect", fake_detect)

        result = preprocess_fortran(p)
        assert result.encoding.lower().replace("-", "") == "utf8"
        assert "program demo" in result.code.lower()


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for empty files, short lines, and mixed indicators."""

    def test_empty_file(self, empty_file: Path) -> None:
        result = preprocess_fortran(empty_file)
        assert isinstance(result, ProcessedFile)
        assert result.code == ""
        assert result.comments == []

    def test_short_lines_no_crash(self, short_lines_file: Path) -> None:
        result = preprocess_fortran(short_lines_file)
        assert isinstance(result, ProcessedFile)

    def test_mixed_indicators_handled(self, tmp_path: Path) -> None:
        content = (
            "C     A COMMENT\n"
            "      X = 1\n"
            "*     ANOTHER COMMENT\n"
            "      Y = 2\n"
        )
        p = tmp_path / "mixed.f"
        p.write_text(content, encoding="utf-8")
        result = preprocess_fortran(p)
        assert isinstance(result, ProcessedFile)
        assert "X = 1" in result.code
        assert "Y = 2" in result.code
        assert any("A COMMENT" in c for c in result.comments)
        assert any("ANOTHER COMMENT" in c for c in result.comments)


# ---------------------------------------------------------------------------
# Return Contract Tests
# ---------------------------------------------------------------------------


class TestReturnContract:
    """Tests that the return value conforms to ProcessedFile contract."""

    def test_returns_processed_file(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert isinstance(result, ProcessedFile)

    def test_language_is_fortran(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert result.language == "fortran"

    def test_file_path_set(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert result.file_path == str(fixed_form_file)

    def test_encoding_is_nonempty_string(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert isinstance(result.encoding, str)
        assert len(result.encoding) > 0

    def test_accepts_string_path(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(str(fixed_form_file))
        assert isinstance(result, ProcessedFile)

    def test_accepts_path_object(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert isinstance(result, ProcessedFile)

    def test_codebase_in_metadata(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file, codebase="gfortran")
        assert isinstance(result.metadata, dict)
        assert result.metadata.get("codebase") == "gfortran"

    def test_source_format_in_metadata(self, fixed_form_file: Path) -> None:
        result = preprocess_fortran(fixed_form_file)
        assert result.metadata.get("source_format") in ("fixed", "free")
