"""Unit tests for COBOL chunking and metadata extraction (MVP-006)."""

from __future__ import annotations

from src.ingestion.cobol_chunker import chunk_cobol
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


def _build_metadata_rich_processed_file() -> ProcessedFile:
    """Representative preprocessed COBOL file with dependency statements."""
    return ProcessedFile(
        code=(
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. TEST.\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-LOGIC.\n"
            "    PERFORM INIT-DATA.\n"
            "    PERFORM PROCESS-ITEM THRU PROCESS-END.\n"
            "    CALL \"RATE-SVC\".\n"
            "    COPY CUSTCOPY.\n"
            "    STOP RUN.\n"
            "INIT-DATA.\n"
            "    MOVE 1 TO WS-COUNT.\n"
            "PROCESS-ITEM.\n"
            "    DISPLAY \"ITEM\".\n"
            "PROCESS-END.\n"
            "    EXIT.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/sample.cob",
        encoding="utf-8",
    )


def _build_duplicate_dependency_processed_file() -> ProcessedFile:
    """COBOL file with repeated dependency references for dedupe checks."""
    return ProcessedFile(
        code=(
            "PROCEDURE DIVISION.\n"
            "MAIN.\n"
            "    PERFORM INIT-DATA.\n"
            "    PERFORM INIT-DATA.\n"
            "    CALL \"RATE-SVC\".\n"
            "    CALL 'RATE-SVC'.\n"
            "    COPY CUSTCOPY.\n"
            "    COPY CUSTCOPY.\n"
            "    STOP RUN.\n"
            "INIT-DATA.\n"
            "    EXIT.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/dupes.cob",
        encoding="utf-8",
    )


def _build_non_procedure_processed_file() -> ProcessedFile:
    """COBOL-like content with no PROCEDURE DIVISION for fallback behavior."""
    return ProcessedFile(
        code=(
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. NO-PROC.\n"
            "DATA DIVISION.\n"
            "WORKING-STORAGE SECTION.\n"
            "01 WS-COUNT PIC 9(4).\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/no_proc.cpy",
        encoding="utf-8",
    )


def _build_dependency_free_processed_file() -> ProcessedFile:
    """PROCEDURE DIVISION with no PERFORM/CALL/COPY statements."""
    return ProcessedFile(
        code=(
            "PROCEDURE DIVISION.\n"
            "MAIN.\n"
            "    MOVE 1 TO WS-COUNT.\n"
            "    ADD 1 TO WS-COUNT.\n"
            "    STOP RUN.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/no_deps.cob",
        encoding="utf-8",
    )


def _build_noisy_dependency_processed_file() -> ProcessedFile:
    """Malformed dependency-like lines should not crash extraction."""
    return ProcessedFile(
        code=(
            "PROCEDURE DIVISION.\n"
            "MAIN.\n"
            "    PERFORM.\n"
            "    CALL .\n"
            "    COPY.\n"
            "    STOP RUN.\n"
        ),
        comments=[],
        language="cobol",
        file_path="data/raw/gnucobol/noisy.cob",
        encoding="utf-8",
    )


class TestChunkContractAndMetadata:
    """Validates chunk contract and metadata schema completeness."""

    def test_returns_list_of_chunk_dataclasses(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        assert isinstance(chunks, list)
        assert chunks
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_required_chunk_fields_populated(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file(), codebase="gnucobol")
        for chunk in chunks:
            assert chunk.file_path
            assert chunk.line_start >= 1
            assert chunk.line_end >= chunk.line_start
            assert chunk.chunk_type == "paragraph"
            assert chunk.language == "cobol"
            assert chunk.codebase == "gnucobol"
            assert chunk.name.strip() != ""
            assert chunk.token_count > 0

    def test_required_metadata_schema_keys_present(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
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
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        for chunk in chunks:
            assert chunk.metadata["paragraph_name"] == chunk.name
            assert chunk.metadata["division"] == chunk.division
            assert chunk.metadata["file_path"] == chunk.file_path
            assert chunk.metadata["chunk_type"] == chunk.chunk_type
            assert chunk.metadata["language"] == chunk.language
            assert chunk.metadata["codebase"] == chunk.codebase
            assert _to_int(chunk.metadata["line_start"]) == chunk.line_start
            assert _to_int(chunk.metadata["line_end"]) == chunk.line_end

    def test_line_ranges_match_content_boundaries(self) -> None:
        processed_file = _build_metadata_rich_processed_file()
        chunks = chunk_cobol(processed_file)
        source_lines = processed_file.code.splitlines()

        for chunk in chunks:
            assert 1 <= chunk.line_start <= len(source_lines)
            assert 1 <= chunk.line_end <= len(source_lines)
            expected = "\n".join(source_lines[chunk.line_start - 1 : chunk.line_end]).strip()
            assert chunk.content.strip() == expected

    def test_procedure_division_chunks_report_procedure_division(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        assert chunks
        for chunk in chunks:
            assert chunk.division == "PROCEDURE"
            assert chunk.metadata["division"] == "PROCEDURE"

    def test_non_procedure_fallback_division_is_deterministic(self) -> None:
        chunks = chunk_cobol(_build_non_procedure_processed_file())
        assert chunks
        for chunk in chunks:
            assert chunk.division == "UNKNOWN"
            assert chunk.metadata["division"] == "UNKNOWN"


class TestDependencyExtraction:
    """Validates PERFORM/CALL/COPY dependency extraction and normalization."""

    def test_extracts_perform_target(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        dependencies = _collect_dependencies(chunks)
        assert "INIT-DATA" in dependencies

    def test_extracts_perform_thru_dependency(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        dependencies = _collect_dependencies(chunks)
        assert "PROCESS-ITEM THRU PROCESS-END" in dependencies

    def test_extracts_call_and_copy_targets(self) -> None:
        chunks = chunk_cobol(_build_metadata_rich_processed_file())
        dependencies = _collect_dependencies(chunks)
        assert "RATE-SVC" in dependencies
        assert "CUSTCOPY" in dependencies

    def test_deduplicates_dependencies_preserving_first_seen_order(self) -> None:
        chunks = chunk_cobol(_build_duplicate_dependency_processed_file())
        dependencies = _collect_dependencies(chunks)
        assert dependencies.count("INIT-DATA") == 1
        assert dependencies.count("RATE-SVC") == 1
        assert dependencies.count("CUSTCOPY") == 1
        assert dependencies == ["INIT-DATA", "RATE-SVC", "CUSTCOPY"]

    def test_no_dependency_statements_yield_empty_dependencies(self) -> None:
        chunks = chunk_cobol(_build_dependency_free_processed_file())
        assert chunks
        for chunk in chunks:
            assert chunk.dependencies == []

    def test_noisy_dependency_like_statements_do_not_crash(self) -> None:
        chunks = chunk_cobol(_build_noisy_dependency_processed_file())
        assert chunks
        for chunk in chunks:
            assert isinstance(chunk.dependencies, list)
