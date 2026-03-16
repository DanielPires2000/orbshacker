"""Tests for updater.py – pure helper functions."""

from pathlib import Path

from orbshacker.updater import _sha256


class TestSha256:
    def test_consistent_hash(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        h1 = _sha256(f)
        h2 = _sha256(f)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest length

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaa")
        f2.write_text("bbb")
        assert _sha256(f1) != _sha256(f2)
