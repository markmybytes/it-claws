"""Tests for manifest hash computation (engine._compute_hashes / _frame)."""

import hashlib
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from it_claws.engine import ConcurrentPipeline, _compute_hashes, _frame

CJK_ARCNAME = "drivers/\u4e2d\u6587/\u0444\u0430\u0439\u043b.bin"


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def _write(root: Path, arcname: str, content: bytes) -> tuple[Path, str]:
    path = root / arcname
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return (path, arcname)


class TestComputeHashes:
    """Tests for _compute_hashes()."""

    def test_deterministic_fold_with_cjk_arcname(self, tmp_path):
        """Exact hex for a fixture tree that includes a CJK arcname."""
        entries = [
            _write(tmp_path, "conf/setting.json", b'{"theme":"dark"}\n'),
            _write(tmp_path, "conf/data.db", b"SQLite format 3\x00"),
            _write(tmp_path, CJK_ARCNAME, b"CJK-BYTES"),
            _write(tmp_path, "drivers/gpu/amd.bin", b"AMD-DRIVER"),
        ]

        assert _compute_hashes(entries) == {
            "settings": "238d439d319aa77425457bf63cbeb3c48c9e91fa",
            "data": "cb58163e3c641021b923f1268ff49f09eb8082e5",
        }

    def test_duplicate_arcname_last_occurrence_wins(self, tmp_path):
        """Dedupe by arcname keeping the last; never double-counted."""
        first = _write(tmp_path / "a", "drivers/dup.bin", b"FIRST")
        last = _write(tmp_path / "b", "drivers/dup.bin", b"SECOND")

        duplicated = _compute_hashes([first, last])
        only_last = _compute_hashes([last])
        only_first = _compute_hashes([first])

        assert duplicated["data"] == only_last["data"]
        assert duplicated["data"] != only_first["data"]

    def test_missing_setting_key_omitted(self, tmp_path):
        """No conf/setting.json entry -> no 'settings' key."""
        entries = [_write(tmp_path, "drivers/x.bin", b"X")]

        hashes = _compute_hashes(entries)
        assert "settings" not in hashes
        assert "data" in hashes

    def test_data_omitted_when_no_data_entries(self, tmp_path):
        """No db and no drivers/ entries -> no 'data' key (never sha1(''))."""
        entries = [_write(tmp_path, "conf/setting.json", b"{}")]

        hashes = _compute_hashes(entries)
        assert hashes == {"settings": _sha1(b"{}")}
        assert "data" not in hashes
        assert _compute_hashes([]) == {}

    def test_cjk_frame_uses_byte_length_not_codepoint_length(self):
        """Frame prefix is the UTF-8 byte length, not the codepoint length."""
        digest = "0" * 40
        frame = _frame(CJK_ARCNAME, digest)

        assert len(CJK_ARCNAME) == 19
        assert len(CJK_ARCNAME.encode("utf-8")) == 27
        assert frame == f"27:{CJK_ARCNAME}:{digest}\n"

    def test_hash_stable_across_reruns(self, tmp_path):
        """Repeated computation is deterministic; mtimes don't leak in."""
        entries = [
            _write(tmp_path, "conf/data.db", b"D"),
            _write(tmp_path, "drivers/a.bin", b"A"),
        ]

        first = _compute_hashes(entries)
        for filepath, _ in entries:
            filepath.touch()

        assert _compute_hashes(entries) == first


class TestManifestHashesIntegration:
    """End-to-end: execute() writes hashes into manifest.json, last in zip."""

    def test_manifest_has_hashes_and_is_last_entry(self, tmp_path):
        output_root = tmp_path / "out"
        (output_root / "conf").mkdir(parents=True)
        (output_root / "conf" / "setting.json").write_bytes(b'{"theme":"dark"}\n')
        (output_root / "drivers").mkdir()
        (output_root / "drivers" / "a.bin").write_bytes(b"A")

        zip_path = tmp_path / "pack.zip"
        with patch("it_claws.engine.UserAgent") as ua:
            ua.return_value.chrome = "test-ua"
            ConcurrentPipeline().execute([], output_root, zip_path=zip_path, manifest=True)

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))

        assert names[-1] == "manifest.json"
        assert manifest["format_version"] == 1
        assert manifest["hashes"]["settings"] == _sha1(b'{"theme":"dark"}\n')
        assert "data" in manifest["hashes"]
