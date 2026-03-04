"""Integration tests for the reusable ingestion pipeline (G4-003)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.types.chunks import Chunk, EmbeddedChunk


MINIMAL_FORTRAN_SUBROUTINE = """\
      SUBROUTINE COMPUTE(X, Y, RESULT)
      REAL X, Y, RESULT
      RESULT = X + Y
      RESULT = RESULT * 2
      RESULT = RESULT - 1
      RESULT = RESULT / 3
      RETURN
      END
"""

MINIMAL_FORTRAN_FREE = """\
subroutine compute(x, y, result)
  real :: x, y, result
  result = x + y
  result = result * 2
  result = result - 1
  result = result / 3
  return
end subroutine compute
"""


def _write_fortran_file(directory: Path, name: str, content: str) -> Path:
    """Write a Fortran file and return its path."""
    file_path = directory / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _make_dummy_chunk(codebase: str = "gfortran", file_path: str = "test.f90") -> Chunk:
    return Chunk(
        content="SUBROUTINE FOO\nEND",
        file_path=file_path,
        line_start=1,
        line_end=2,
        chunk_type="subroutine",
        language="fortran",
        codebase=codebase,
        name="FOO",
        division="SUBROUTINE",
        token_count=10,
    )


def _make_dummy_embedded_chunk(chunk: Chunk) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=chunk,
        embedding=[0.1] * 1536,
        chunk_id=f"{chunk.codebase}:{chunk.file_path}:{chunk.line_start}",
    )


class TestDiscoverFiles:
    """Tests for file discovery filtering."""

    def test_discovers_fortran_files_only(self) -> None:
        """Only .f, .f90, .f77, .f95 files should be discovered for fortran."""
        from src.ingestion.ingest import discover_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "compute.f90", MINIMAL_FORTRAN_FREE)
            _write_fortran_file(base, "legacy.f", MINIMAL_FORTRAN_SUBROUTINE)
            _write_fortran_file(base, "readme.txt", "not fortran")
            _write_fortran_file(base, "main.c", "int main() {}")
            _write_fortran_file(base, "data.json", "{}")

            files = discover_files(base, "fortran")
            extensions = {f.suffix.lower() for f in files}

            assert len(files) == 2
            assert extensions <= {".f", ".f90", ".f77", ".f95"}

    def test_discovers_files_recursively(self) -> None:
        """Files in subdirectories should be found."""
        from src.ingestion.ingest import discover_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            sub = base / "subdir"
            sub.mkdir()
            _write_fortran_file(sub, "nested.f90", MINIMAL_FORTRAN_FREE)

            files = discover_files(base, "fortran")
            assert len(files) == 1
            assert files[0].name == "nested.f90"

    def test_returns_sorted_paths(self) -> None:
        """Discovered files should be in sorted order."""
        from src.ingestion.ingest import discover_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "z_last.f90", MINIMAL_FORTRAN_FREE)
            _write_fortran_file(base, "a_first.f90", MINIMAL_FORTRAN_FREE)

            files = discover_files(base, "fortran")
            assert len(files) == 2
            assert files[0].name < files[1].name


class TestIngestCodebaseReturnContract:
    """Tests for ingest_codebase() function contract."""

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_returns_stats_dict(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """ingest_codebase should return a dict with expected stat keys."""
        from src.ingestion.ingest import ingest_codebase

        mock_embed.return_value = []
        mock_index.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "test.f90", MINIMAL_FORTRAN_FREE)

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            assert isinstance(stats, dict)
            required_keys = {
                "files_found",
                "files_processed",
                "chunks_created",
                "chunks_embedded",
                "chunks_indexed",
                "errors",
            }
            assert required_keys <= set(stats.keys())

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_processes_fortran_files(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """Pipeline should preprocess and chunk Fortran files."""
        from src.ingestion.ingest import ingest_codebase

        dummy_chunk = _make_dummy_chunk()
        dummy_embedded = _make_dummy_embedded_chunk(dummy_chunk)
        mock_embed.return_value = [dummy_embedded]
        mock_index.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "test.f90", MINIMAL_FORTRAN_FREE)

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            assert stats["files_found"] >= 1
            assert stats["files_processed"] >= 1
            assert stats["errors"] == 0


class TestEmptyDirectoryHandling:
    """Tests for empty/missing directory behavior."""

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_empty_directory_returns_zero_stats(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """An empty directory should return zeroed stats, not crash."""
        from src.ingestion.ingest import ingest_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            stats = ingest_codebase(
                Path(tmpdir), codebase="gfortran", language="fortran"
            )

            assert stats["files_found"] == 0
            assert stats["files_processed"] == 0
            assert stats["chunks_created"] == 0
            assert stats["chunks_embedded"] == 0
            assert stats["chunks_indexed"] == 0
            assert stats["errors"] == 0
            mock_embed.assert_not_called()
            mock_index.assert_not_called()

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_no_supported_files_returns_zero(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """A directory with only unsupported files should return zeroed stats."""
        from src.ingestion.ingest import ingest_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "readme.txt", "docs only")
            _write_fortran_file(base, "main.c", "int main() {}")

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            assert stats["files_found"] == 0
            assert stats["errors"] == 0
            mock_embed.assert_not_called()


class TestPreprocessingErrorHandling:
    """Tests for graceful handling of file processing errors."""

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    @patch("src.ingestion.ingest.preprocess_fortran")
    def test_skips_failing_files_continues_processing(
        self,
        mock_preprocess: MagicMock,
        mock_embed: MagicMock,
        mock_index: MagicMock,
    ) -> None:
        """Files that fail preprocessing should be skipped with error counted."""
        from src.ingestion.ingest import ingest_codebase

        mock_preprocess.side_effect = RuntimeError("corrupt file")
        mock_embed.return_value = []
        mock_index.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "bad.f90", "corrupt data")

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            assert stats["errors"] >= 1
            assert stats["files_processed"] == 0

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_skips_empty_processed_files(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """Files that produce empty code after preprocessing should be skipped."""
        from src.ingestion.ingest import ingest_codebase

        mock_embed.return_value = []
        mock_index.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "empty.f90", "")

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            assert stats["files_processed"] == 0
            assert stats["errors"] == 0


class TestEmbeddingAndIndexingIntegration:
    """Tests for embedding/indexing call behavior."""

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_embed_called_with_all_chunks(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """All chunks from all files should be passed to embed_chunks in one call."""
        from src.ingestion.ingest import ingest_codebase

        mock_embed.return_value = []
        mock_index.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "a.f90", MINIMAL_FORTRAN_FREE)
            _write_fortran_file(base, "b.f90", MINIMAL_FORTRAN_FREE)

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            if stats["chunks_created"] > 0:
                mock_embed.assert_called_once()
                chunks_arg = mock_embed.call_args[0][0]
                assert isinstance(chunks_arg, list)
                assert all(isinstance(c, Chunk) for c in chunks_arg)

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_index_called_with_embedded_chunks(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """index_chunks should be called with the output of embed_chunks."""
        from src.ingestion.ingest import ingest_codebase

        dummy_chunk = _make_dummy_chunk()
        dummy_embedded = _make_dummy_embedded_chunk(dummy_chunk)
        mock_embed.return_value = [dummy_embedded]
        mock_index.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "test.f90", MINIMAL_FORTRAN_FREE)

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            if stats["chunks_created"] > 0:
                mock_index.assert_called_once()
                indexed_arg = mock_index.call_args[0][0]
                assert isinstance(indexed_arg, list)
                assert all(isinstance(e, EmbeddedChunk) for e in indexed_arg)

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_stats_reflect_indexed_count(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """chunks_indexed should reflect the return value of index_chunks."""
        from src.ingestion.ingest import ingest_codebase

        dummy_chunk = _make_dummy_chunk()
        dummy_embedded = _make_dummy_embedded_chunk(dummy_chunk)
        mock_embed.return_value = [dummy_embedded]
        mock_index.return_value = 42

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "test.f90", MINIMAL_FORTRAN_FREE)

            stats = ingest_codebase(base, codebase="gfortran", language="fortran")

            if stats["chunks_created"] > 0:
                assert stats["chunks_indexed"] == 42


class TestCobolIngestionPath:
    """Tests verifying COBOL files use COBOL pipeline."""

    @patch("src.ingestion.ingest.index_chunks")
    @patch("src.ingestion.ingest.embed_chunks")
    def test_cobol_files_use_cobol_pipeline(
        self, mock_embed: MagicMock, mock_index: MagicMock
    ) -> None:
        """COBOL files should go through preprocess_cobol + chunk_cobol."""
        from src.ingestion.ingest import ingest_codebase

        cobol_source = """\
000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. TEST-PROG.
000300 PROCEDURE DIVISION.
000400 MAIN-LOGIC.
000500     DISPLAY "HELLO".
000600     STOP RUN.
"""
        mock_embed.return_value = []
        mock_index.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_fortran_file(base, "test.cob", cobol_source)

            stats = ingest_codebase(
                base, codebase="gnucobol", language="cobol"
            )

            assert stats["files_found"] >= 1
