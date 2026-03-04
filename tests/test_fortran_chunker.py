"""Unit tests for Fortran subroutine chunking and metadata extraction (G4-002)."""

from __future__ import annotations

from src.ingestion.fortran_chunker import chunk_fortran
from src.types.chunks import Chunk, ProcessedFile


def _to_int(value: object) -> int:
    """Convert metadata values that may be str/int into int for assertions."""
    return int(str(value))


def _collect_dependencies(chunks: list[Chunk]) -> list[str]:
    """Flatten chunk dependency lists in chunk order."""
    flattened: list[str] = []
    for chunk in chunks:
        flattened.extend(chunk.dependencies)
    return flattened


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _build_single_subroutine_file() -> ProcessedFile:
    """Preprocessed Fortran file with a single subroutine."""
    return ProcessedFile(
        code=(
            "SUBROUTINE DGEMM(TRANSA, TRANSB, M, N, K)\n"
            "      DOUBLE PRECISION ALPHA, BETA\n"
            "      INTEGER K, M, N\n"
            "      CALL XERBLA('DGEMM', INFO)\n"
            "      END\n"
        ),
        comments=["performs matrix-matrix operations"],
        language="fortran",
        file_path="data/raw/blas/dgemm.f",
        encoding="utf-8",
    )


def _build_single_function_file() -> ProcessedFile:
    """Preprocessed Fortran file with a single function."""
    return ProcessedFile(
        code=(
            "FUNCTION DNRM2(N, X, INCX)\n"
            "      DOUBLE PRECISION DNRM2\n"
            "      INTEGER N, INCX\n"
            "      DNRM2 = 0.0D0\n"
            "      END FUNCTION DNRM2\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/blas/dnrm2.f",
        encoding="utf-8",
    )


def _build_program_file() -> ProcessedFile:
    """Preprocessed Fortran file with a PROGRAM unit."""
    return ProcessedFile(
        code=(
            "PROGRAM MAIN\n"
            "      USE CONSTANTS\n"
            "      IMPLICIT NONE\n"
            "      PRINT *, 'HELLO'\n"
            "      END PROGRAM MAIN\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/main.f90",
        encoding="utf-8",
    )


def _build_module_file() -> ProcessedFile:
    """Preprocessed Fortran file with a MODULE unit."""
    return ProcessedFile(
        code=(
            "MODULE CONSTANTS\n"
            "      IMPLICIT NONE\n"
            "      REAL, PARAMETER :: PI = 3.14159265\n"
            "      END MODULE CONSTANTS\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/constants.f90",
        encoding="utf-8",
    )


def _build_typed_function_file() -> ProcessedFile:
    """Fortran file with typed function declarations."""
    return ProcessedFile(
        code=(
            "INTEGER FUNCTION ILAENV(ISPEC, NAME, OPTS, N1)\n"
            "      INTEGER ISPEC, N1\n"
            "      CHARACTER NAME, OPTS\n"
            "      ILAENV = 1\n"
            "      END FUNCTION ILAENV\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/lapack/ilaenv.f",
        encoding="utf-8",
    )


def _build_double_precision_function_file() -> ProcessedFile:
    """Fortran file with DOUBLE PRECISION FUNCTION."""
    return ProcessedFile(
        code=(
            "DOUBLE PRECISION FUNCTION DDOT(N, DX, INCX, DY, INCY)\n"
            "      INTEGER N, INCX, INCY\n"
            "      DOUBLE PRECISION DX(*), DY(*)\n"
            "      DDOT = 0.0D0\n"
            "      END\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/blas/ddot.f",
        encoding="utf-8",
    )


def _build_multi_unit_file() -> ProcessedFile:
    """Fortran file with multiple program units, each large enough to avoid merging."""
    body1 = "\n".join([f"      A({i}) = {i}.0D0" for i in range(1, 30)])
    body2 = "\n".join([f"      B({i}) = {i}.0D0" for i in range(1, 30)])
    return ProcessedFile(
        code=(
            "SUBROUTINE DGETRF(M, N, A, LDA, IPIV, INFO)\n"
            "      INTEGER M, N, LDA, INFO\n"
            "      DOUBLE PRECISION A(LDA, *)\n"
            "      INTEGER IPIV(*)\n"
            "      CALL DGETF2(M, N, A, LDA, IPIV, INFO)\n"
            f"{body1}\n"
            "      END SUBROUTINE DGETRF\n"
            "\n"
            "SUBROUTINE DGETRS(TRANS, N, NRHS, A, LDA, IPIV, B, LDB, INFO)\n"
            "      CHARACTER TRANS\n"
            "      INTEGER N, NRHS, LDA, LDB, INFO\n"
            "      DOUBLE PRECISION A(LDA, *), B(LDB, *)\n"
            "      INTEGER IPIV(*)\n"
            f"{body2}\n"
            "      END SUBROUTINE DGETRS\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/lapack/dgetrf.f",
        encoding="utf-8",
    )


def _build_module_and_program_file() -> ProcessedFile:
    """Free-form Fortran file with a module and a program, each above merge threshold."""
    mod_body = "\n".join([f"  real, parameter :: c{i} = {i}.0" for i in range(1, 30)])
    prog_body = "\n".join([f"  print *, c{i}" for i in range(1, 30)])
    return ProcessedFile(
        code=(
            "module constants\n"
            "  implicit none\n"
            f"{mod_body}\n"
            "end module constants\n"
            "\n"
            "program main\n"
            "  use constants\n"
            f"{prog_body}\n"
            "end program main\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/modprog.f90",
        encoding="utf-8",
    )


def _build_dependency_rich_file() -> ProcessedFile:
    """Fortran file with CALL, USE, and INCLUDE dependencies."""
    return ProcessedFile(
        code=(
            "SUBROUTINE DRIVER(N, A, LDA)\n"
            "      USE ISO_FORTRAN_ENV\n"
            "      USE MPI_MODULE\n"
            "      INCLUDE 'mpif.h'\n"
            "      INTEGER N, LDA\n"
            "      CALL DGEMM('N', 'N', N, N, N, 1.0D0, A, LDA, A, LDA, 0.0D0, A, LDA)\n"
            "      CALL XERBLA('DRIVER', 1)\n"
            "      CALL DGEMM('N', 'N', N, N, N, 1.0D0, A, LDA, A, LDA, 0.0D0, A, LDA)\n"
            "      END SUBROUTINE DRIVER\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/driver.f90",
        encoding="utf-8",
    )


def _build_no_dependency_file() -> ProcessedFile:
    """Fortran file with no CALL/USE/INCLUDE statements."""
    return ProcessedFile(
        code=(
            "SUBROUTINE SIMPLE(X, Y)\n"
            "      DOUBLE PRECISION X, Y\n"
            "      Y = X * 2.0D0\n"
            "      END SUBROUTINE SIMPLE\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/simple.f",
        encoding="utf-8",
    )


def _build_noisy_dependency_file() -> ProcessedFile:
    """Malformed dependency-like lines should not crash extraction."""
    return ProcessedFile(
        code=(
            "SUBROUTINE NOISY(X)\n"
            "      CALL\n"
            "      USE\n"
            "      INCLUDE\n"
            "      X = 1.0\n"
            "      END SUBROUTINE NOISY\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/noisy.f",
        encoding="utf-8",
    )


def _build_no_units_file() -> ProcessedFile:
    """Fortran code with no program unit boundaries — fallback needed."""
    return ProcessedFile(
        code=(
            "      IMPLICIT NONE\n"
            "      INTEGER X\n"
            "      X = 42\n"
            "      PRINT *, X\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/fragment.f",
        encoding="utf-8",
    )


def _build_empty_file() -> ProcessedFile:
    """Empty preprocessed Fortran file."""
    return ProcessedFile(
        code="",
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/empty.f90",
        encoding="utf-8",
    )


def _build_block_data_file() -> ProcessedFile:
    """Fortran file with BLOCK DATA unit."""
    return ProcessedFile(
        code=(
            "BLOCK DATA BLKDAT\n"
            "      IMPLICIT NONE\n"
            "      COMMON /SHARED/ X, Y\n"
            "      DATA X /1.0/, Y /2.0/\n"
            "      END BLOCK DATA BLKDAT\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/blkdat.f",
        encoding="utf-8",
    )


def _build_recursive_subroutine_file() -> ProcessedFile:
    """Fortran file with RECURSIVE prefix on subroutine."""
    return ProcessedFile(
        code=(
            "RECURSIVE SUBROUTINE XERBLA(SRNAME, INFO)\n"
            "      CHARACTER SRNAME\n"
            "      INTEGER INFO\n"
            "      END SUBROUTINE XERBLA\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/xerbla.f",
        encoding="utf-8",
    )


def _build_oversized_subroutine() -> ProcessedFile:
    """Fortran subroutine with enough lines to exceed CHUNK_MAX_TOKENS (768)."""
    body_lines = [f"      X({i}) = {i}.0D0" for i in range(1, 501)]
    code = (
        "SUBROUTINE BIGONE(X, N)\n"
        "      INTEGER N\n"
        "      DOUBLE PRECISION X(N)\n"
        + "\n".join(body_lines)
        + "\n      END SUBROUTINE BIGONE\n"
    )
    return ProcessedFile(
        code=code,
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/bigone.f",
        encoding="utf-8",
    )


def _build_tiny_adjacent_units() -> ProcessedFile:
    """Multiple tiny subroutines that should get merged."""
    return ProcessedFile(
        code=(
            "SUBROUTINE A(X)\n"
            "      X = 1\n"
            "      END\n"
            "\n"
            "SUBROUTINE B(Y)\n"
            "      Y = 2\n"
            "      END\n"
            "\n"
            "SUBROUTINE C(Z)\n"
            "      Z = 3\n"
            "      END\n"
        ),
        comments=[],
        language="fortran",
        file_path="data/raw/gfortran/tiny.f",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Unit boundary detection tests
# ---------------------------------------------------------------------------


class TestUnitBoundaryDetection:
    """Validates detection of Fortran program unit boundaries."""

    def test_subroutine_detected_with_correct_name(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        assert len(chunks) >= 1
        sub_chunks = [c for c in chunks if c.chunk_type == "subroutine"]
        assert len(sub_chunks) >= 1
        assert sub_chunks[0].name == "DGEMM"

    def test_function_detected_with_correct_name(self) -> None:
        chunks = chunk_fortran(_build_single_function_file())
        assert len(chunks) >= 1
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(func_chunks) >= 1
        assert func_chunks[0].name == "DNRM2"

    def test_program_detected_with_correct_name(self) -> None:
        chunks = chunk_fortran(_build_program_file())
        assert len(chunks) >= 1
        prog_chunks = [c for c in chunks if c.chunk_type == "program"]
        assert len(prog_chunks) >= 1
        assert prog_chunks[0].name == "MAIN"

    def test_module_detected_with_correct_name(self) -> None:
        chunks = chunk_fortran(_build_module_file())
        assert len(chunks) >= 1
        mod_chunks = [c for c in chunks if c.chunk_type == "module"]
        assert len(mod_chunks) >= 1
        assert mod_chunks[0].name == "CONSTANTS"

    def test_block_data_detected_with_correct_name(self) -> None:
        chunks = chunk_fortran(_build_block_data_file())
        assert len(chunks) >= 1
        bd_chunks = [c for c in chunks if c.chunk_type == "block_data"]
        assert len(bd_chunks) >= 1
        assert bd_chunks[0].name == "BLKDAT"

    def test_typed_function_detected(self) -> None:
        chunks = chunk_fortran(_build_typed_function_file())
        assert len(chunks) >= 1
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(func_chunks) >= 1
        assert func_chunks[0].name == "ILAENV"

    def test_double_precision_function_detected(self) -> None:
        chunks = chunk_fortran(_build_double_precision_function_file())
        assert len(chunks) >= 1
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(func_chunks) >= 1
        assert func_chunks[0].name == "DDOT"

    def test_recursive_subroutine_detected(self) -> None:
        chunks = chunk_fortran(_build_recursive_subroutine_file())
        assert len(chunks) >= 1
        sub_chunks = [c for c in chunks if c.chunk_type == "subroutine"]
        assert len(sub_chunks) >= 1
        assert sub_chunks[0].name == "XERBLA"

    def test_end_statement_closes_unit(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        sub_chunks = [c for c in chunks if c.chunk_type == "subroutine"]
        assert len(sub_chunks) >= 1
        assert "END" in sub_chunks[0].content.upper()

    def test_multiple_units_produce_multiple_chunks(self) -> None:
        chunks = chunk_fortran(_build_multi_unit_file())
        sub_chunks = [c for c in chunks if c.chunk_type == "subroutine"]
        assert len(sub_chunks) >= 2
        names = [c.name for c in sub_chunks]
        assert "DGETRF" in names
        assert "DGETRS" in names

    def test_module_and_program_in_same_file(self) -> None:
        chunks = chunk_fortran(_build_module_and_program_file())
        types = {c.chunk_type for c in chunks}
        assert "module" in types
        assert "program" in types


# ---------------------------------------------------------------------------
# Chunk contract tests
# ---------------------------------------------------------------------------


class TestChunkContractAndMetadata:
    """Validates chunk contract and metadata schema completeness."""

    def test_returns_list_of_chunk_dataclasses(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        assert isinstance(chunks, list)
        assert chunks
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_required_chunk_fields_populated(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file(), codebase="blas")
        for chunk in chunks:
            assert chunk.file_path
            assert chunk.line_start >= 1
            assert chunk.line_end >= chunk.line_start
            assert chunk.chunk_type in (
                "subroutine",
                "function",
                "program",
                "module",
                "block_data",
                "file_block",
            )
            assert chunk.language == "fortran"
            assert chunk.codebase == "blas"
            assert chunk.name.strip() != ""
            assert chunk.token_count > 0

    def test_language_is_fortran(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        for chunk in chunks:
            assert chunk.language == "fortran"

    def test_chunk_type_matches_unit_type(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        sub_chunks = [c for c in chunks if c.name == "DGEMM"]
        assert sub_chunks
        assert sub_chunks[0].chunk_type == "subroutine"

    def test_name_is_uppercase(self) -> None:
        chunks = chunk_fortran(_build_module_and_program_file())
        for chunk in chunks:
            assert chunk.name == chunk.name.upper()

    def test_line_ranges_valid(self) -> None:
        processed_file = _build_multi_unit_file()
        chunks = chunk_fortran(processed_file)
        source_lines = processed_file.code.splitlines()
        for chunk in chunks:
            assert 1 <= chunk.line_start <= len(source_lines)
            assert 1 <= chunk.line_end <= len(source_lines)
            assert chunk.line_start <= chunk.line_end

    def test_required_metadata_schema_keys_present(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        required_keys = {
            "paragraph_name",
            "division",
            "file_path",
            "line_start",
            "line_end",
            "chunk_type",
            "language",
            "codebase",
        }
        for chunk in chunks:
            assert required_keys.issubset(set(chunk.metadata.keys()))

    def test_metadata_values_match_chunk_fields(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        for chunk in chunks:
            assert chunk.metadata["paragraph_name"] == chunk.name
            assert chunk.metadata["division"] == chunk.division
            assert chunk.metadata["file_path"] == chunk.file_path
            assert chunk.metadata["chunk_type"] == chunk.chunk_type
            assert chunk.metadata["language"] == chunk.language
            assert chunk.metadata["codebase"] == chunk.codebase
            assert _to_int(chunk.metadata["line_start"]) == chunk.line_start
            assert _to_int(chunk.metadata["line_end"]) == chunk.line_end

    def test_paragraph_name_key_used_not_unit_name(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        for chunk in chunks:
            assert "paragraph_name" in chunk.metadata
            assert "unit_name" not in chunk.metadata

    def test_division_set_to_unit_type(self) -> None:
        chunks = chunk_fortran(_build_single_subroutine_file())
        sub_chunks = [c for c in chunks if c.name == "DGEMM"]
        assert sub_chunks
        assert sub_chunks[0].division == "SUBROUTINE"

    def test_module_division(self) -> None:
        chunks = chunk_fortran(_build_module_file())
        mod_chunks = [c for c in chunks if c.chunk_type == "module"]
        assert mod_chunks
        assert mod_chunks[0].division == "MODULE"

    def test_function_division(self) -> None:
        chunks = chunk_fortran(_build_single_function_file())
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert func_chunks
        assert func_chunks[0].division == "FUNCTION"


# ---------------------------------------------------------------------------
# Dependency extraction tests
# ---------------------------------------------------------------------------


class TestDependencyExtraction:
    """Validates CALL/USE/INCLUDE dependency extraction and normalization."""

    def test_extracts_call_targets(self) -> None:
        chunks = chunk_fortran(_build_dependency_rich_file())
        dependencies = _collect_dependencies(chunks)
        assert "DGEMM" in dependencies
        assert "XERBLA" in dependencies

    def test_extracts_use_module_dependencies(self) -> None:
        chunks = chunk_fortran(_build_dependency_rich_file())
        dependencies = _collect_dependencies(chunks)
        assert "ISO_FORTRAN_ENV" in dependencies
        assert "MPI_MODULE" in dependencies

    def test_extracts_include_file_dependencies(self) -> None:
        chunks = chunk_fortran(_build_dependency_rich_file())
        dependencies = _collect_dependencies(chunks)
        assert "mpif.h" in dependencies

    def test_dependencies_deduplicated_preserving_first_seen_order(self) -> None:
        chunks = chunk_fortran(_build_dependency_rich_file())
        dependencies = _collect_dependencies(chunks)
        assert dependencies.count("DGEMM") == 1

    def test_no_dependency_statements_yield_empty_list(self) -> None:
        chunks = chunk_fortran(_build_no_dependency_file())
        assert chunks
        for chunk in chunks:
            assert chunk.dependencies == []

    def test_noisy_dependency_like_statements_do_not_crash(self) -> None:
        chunks = chunk_fortran(_build_noisy_dependency_file())
        assert chunks
        for chunk in chunks:
            assert isinstance(chunk.dependencies, list)


# ---------------------------------------------------------------------------
# Size enforcement tests
# ---------------------------------------------------------------------------


class TestSizeEnforcement:
    """Validates adaptive chunk size enforcement (merge/split)."""

    def test_empty_processed_file_returns_empty_list(self) -> None:
        chunks = chunk_fortran(_build_empty_file())
        assert chunks == []

    def test_small_adjacent_chunks_get_merged(self) -> None:
        pf = _build_tiny_adjacent_units()
        chunks = chunk_fortran(pf)
        initial_unit_count = 3
        assert len(chunks) < initial_unit_count

    def test_oversized_chunks_get_split(self) -> None:
        pf = _build_oversized_subroutine()
        chunks = chunk_fortran(pf)
        assert len(chunks) > 1
        from src.config import CHUNK_MAX_TOKENS

        for chunk in chunks:
            assert chunk.token_count <= CHUNK_MAX_TOKENS + 10


# ---------------------------------------------------------------------------
# Fallback behavior tests
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    """Validates fallback chunking for code not inside program units."""

    def test_no_units_produces_fallback_chunk(self) -> None:
        chunks = chunk_fortran(_build_no_units_file())
        assert len(chunks) >= 1
        assert all(c.chunk_type == "file_block" for c in chunks)

    def test_fallback_chunk_has_deterministic_name_and_division(self) -> None:
        chunks = chunk_fortran(_build_no_units_file())
        assert chunks
        for chunk in chunks:
            assert chunk.name != ""
            assert chunk.division != ""
