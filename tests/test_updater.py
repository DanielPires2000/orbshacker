"""Tests for updater.py – pure helper functions (no network calls)."""

from unittest.mock import patch

import pytest

from orbshacker.updater import (
    ChecksumError,
    _find_checksum_asset,
    _find_exe_asset,
    _parse_version,
    _sha256,
    _verify_sha256,
    parse_sha256sums,
)


class TestSha256:
    def test_consistent_hash(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        h1 = _sha256(f)
        h2 = _sha256(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaa")
        f2.write_text("bbb")
        assert _sha256(f1) != _sha256(f2)


class TestParseSha256sums:
    def test_parses_standard_lines(self):
        text = (
            "a" * 64 + "  orbshacker.exe\n"
            + "b" * 64 + " *other.bin\n"
        )
        sums = parse_sha256sums(text)
        assert sums["orbshacker.exe"] == "a" * 64
        assert sums["other.bin"] == "b" * 64

    def test_ignores_malformed_lines(self):
        text = "short  orbshacker.exe\n\nnot-a-hash  x\n" + "c" * 64 + "  ok.bin\n"
        sums = parse_sha256sums(text)
        assert sums == {"ok.bin": "c" * 64}

    def test_normalizes_case(self):
        text = "A" * 64 + "  orbshacker.exe\n"
        assert parse_sha256sums(text)["orbshacker.exe"] == "a" * 64


class TestVerifySha256:
    def test_matching_digest_passes(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"payload")
        _verify_sha256(f, "x.bin", {"x.bin": _sha256(f)})

    def test_mismatch_raises(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"payload")
        with pytest.raises(ChecksumError):
            _verify_sha256(f, "x.bin", {"x.bin": "0" * 64})

    def test_missing_entry_raises(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"payload")
        with pytest.raises(ChecksumError):
            _verify_sha256(f, "x.bin", {})


class TestScheduleDelete:
    def test_bounded_retries(self, tmp_path):
        from orbshacker.updater import _schedule_delete

        target = tmp_path / "orbshacker.old"
        target.touch()
        with patch("orbshacker.updater.spawn_self_destruct") as mock_spawn:
            _schedule_delete(target)
        mock_spawn.assert_called_once()
        assert mock_spawn.call_args.kwargs["max_attempts"] == 15

    def test_noop_when_missing(self, tmp_path):
        from orbshacker.updater import _schedule_delete

        with patch("orbshacker.updater.spawn_self_destruct") as mock_spawn:
            _schedule_delete(tmp_path / "nope.old")
        mock_spawn.assert_not_called()


class TestAssetLookup:
    def test_find_exe_asset(self):
        assets = [
            {"name": "SHA256SUMS", "browser_download_url": "u1"},
            {"name": "orbshacker.exe", "browser_download_url": "u2"},
        ]
        asset = _find_exe_asset(assets)
        assert asset["name"] == "orbshacker.exe"

    def test_find_checksum_asset(self):
        assets = [
            {"name": "orbshacker.exe", "browser_download_url": "u2"},
            {"name": "SHA256SUMS", "browser_download_url": "u1"},
        ]
        asset = _find_checksum_asset(assets)
        assert asset["browser_download_url"] == "u1"

    def test_missing_checksum_asset(self):
        assert _find_checksum_asset([{"name": "orbshacker.exe", "browser_download_url": "u2"}]) is None


class TestParseVersion:
    def test_accepts_v_prefix(self):
        assert str(_parse_version("v2.1.0")) == "2.1.0"

    def test_accepts_bare(self):
        assert str(_parse_version("2.1.0")) == "2.1.0"
