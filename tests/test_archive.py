"""Tests for archive.py."""

import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from it_claws import archive
from it_claws.archive import _find_7z, unzip


class TestUnzip:
    """Tests for unzip()."""

    def test_calls_7z_with_correct_args(self):
        with patch("it_claws.archive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            source = Path("test.zip")
            target = Path("output")
            result = unzip(source, target)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "x" in args
            assert str(source) in args
            assert f"-o{str(target)}" in args
            assert "-y" in args
            assert result == 0

    def test_returns_7z_returncode(self):
        with patch("it_claws.archive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 7
            result = unzip(Path("a.7z"), Path("out"))
            assert result == 7

    def test_silent_suppresses_output(self):
        with patch("it_claws.archive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            unzip(Path("a.zip"), Path("out"), silent=True)
            assert mock_run.call_args[1]["stdout"] == subprocess.DEVNULL
            assert mock_run.call_args[1]["stderr"] == subprocess.DEVNULL

    def test_nonsilent_passes_none(self):
        with patch("it_claws.archive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            unzip(Path("a.zip"), Path("out"), silent=False)
            assert mock_run.call_args[1]["stdout"] is None
            assert mock_run.call_args[1]["stderr"] is None


class TestZip:
    """Tests for zip()."""

    def test_creates_zipfile_with_correct_args(self):
        """Verify ZipFile is opened with the expected target, mode, compression, and level."""
        with patch("it_claws.archive.zipfile.ZipFile") as mock_zf_cls:
            mock_instance = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_instance
            mock_zf_cls.return_value.__exit__.return_value = False

            entries = [(Path("file.txt"), "file.txt")]
            archive.zip(Path("out.zip"), entries)

            mock_zf_cls.assert_called_once_with(
                Path("out.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=5
            )

    def test_compression_level_is_applied(self):
        """Verify the *level* parameter propagates to ZipFile(compresslevel=...)."""
        with patch("it_claws.archive.zipfile.ZipFile") as mock_zf_cls:
            mock_instance = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_instance
            mock_zf_cls.return_value.__exit__.return_value = False

            entries = [(Path("file.txt"), "file.txt")]
            archive.zip(Path("out.zip"), entries, level=9)

            mock_zf_cls.assert_called_once_with(
                Path("out.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=9
            )

    def test_writes_each_entry_with_correct_arcname(self):
        """Verify each entry is written with the correct (filepath, arcname) pair."""
        with patch("it_claws.archive.zipfile.ZipFile") as mock_zf_cls:
            mock_instance = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_instance
            mock_zf_cls.return_value.__exit__.return_value = False

            entries = [
                (Path("dir/file.txt"), "renamed.txt"),
                (Path("other.txt"), "path/to/other.txt"),
            ]
            archive.zip(Path("out.zip"), entries)

            calls = mock_instance.write.call_args_list
            assert len(calls) == 2
            assert calls[0][0] == (str(Path("dir/file.txt")), "renamed.txt")
            assert calls[1][0] == (str(Path("other.txt")), "path/to/other.txt")

    def test_empty_entries_produces_empty_zip(self):
        """An empty entries iterable should result in no files written to the archive."""
        with patch("it_claws.archive.zipfile.ZipFile") as mock_zf_cls:
            mock_instance = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_instance
            mock_zf_cls.return_value.__exit__.return_value = False

            archive.zip(Path("out.zip"), [])
            mock_instance.write.assert_not_called()

    def test_converts_target_to_path(self):
        """Verify a string target is converted to Path before being passed to ZipFile."""
        with patch("it_claws.archive.zipfile.ZipFile") as mock_zf_cls:
            mock_instance = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_instance
            mock_zf_cls.return_value.__exit__.return_value = False

            archive.zip("out.zip", [])
            # The function does Path("out.zip"), so the call should receive a Path
            called_target = mock_zf_cls.call_args[0][0]
            assert isinstance(called_target, Path)


class TestWalk:
    """Tests for walk()."""

    def test_yields_files_from_root(self, tmp_path):
        (tmp_path / "sub" / "a.txt").parent.mkdir()
        (tmp_path / "sub" / "a.txt").write_text("a")
        base = tmp_path
        prefix = None
        result = list(archive.walk(tmp_path, base, prefix))
        assert len(result) == 1
        assert result[0][0].name == "a.txt"
        assert result[0][1] == "sub/a.txt"

    def test_prefix_prepended(self, tmp_path):
        (tmp_path / "sub" / "a.txt").parent.mkdir()
        (tmp_path / "sub" / "a.txt").write_text("a")
        result = list(archive.walk(tmp_path, tmp_path, "pkg"))
        assert result[0][1] == "pkg/sub/a.txt"

    def test_skips_directories(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "a.txt").write_text("a")
        result = list(archive.walk(tmp_path, tmp_path, None))
        assert len(result) == 1
        assert result[0][0].name == "a.txt"

    def test_empty_dir(self, tmp_path):
        result = list(archive.walk(tmp_path, tmp_path, None))
        assert result == []


class TestFind7z:
    """Minimal smoke tests for _find_7z()."""

    def test_returns_string(self):
        """_find_7z should always return a non-empty string."""
        result = _find_7z()
        assert isinstance(result, str)
        assert len(result) > 0
