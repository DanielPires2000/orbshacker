"""Tests for bake.py – embedded-config marker round-trip."""


from orbshacker.bake import (
    MARKER,
    bake_config,
    has_baked_config,
    is_faked_game,
    load_baked_config,
)


class TestBakeRoundTrip:
    def test_round_trip_binary_file(self, tmp_path):
        target = tmp_path / "TslGame.exe"
        target.write_bytes(b"MZ fake exe content")
        cfg = {
            "TIMER_MINUTES": 45,
            "AUTO_DELETE_ON_TIMER_END": True,
            "STEAM_MANIFEST_PATH": "C:/Steam/steamapps/appmanifest_123.acf",
            "CLEANUP_DIRS": ["C:/Desktop/Win64"],
        }
        bake_config(target, cfg)

        loaded = load_baked_config(target)
        assert loaded == cfg

    def test_round_trip_survives_tail_junk(self, tmp_path):
        target = tmp_path / "TslGame.exe"
        target.write_bytes(b"MZ")
        bake_config(target, {"TIMER_MINUTES": 7})
        with open(target, "ab") as fh:
            fh.write(b"\x00\x01trailing junk")
        assert load_baked_config(target) == {"TIMER_MINUTES": 7}

    def test_missing_marker_returns_none(self, tmp_path):
        target = tmp_path / "plain.exe"
        target.write_bytes(b"MZ just a normal program")
        assert load_baked_config(target) is None
        assert not has_baked_config(target)

    def test_corrupt_json_returns_none(self, tmp_path):
        target = tmp_path / "broken.exe"
        target.write_bytes(b"MZ" + MARKER + b"{not json" + MARKER)
        assert load_baked_config(target) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert load_baked_config(tmp_path / "nope.exe") is None

    def test_double_bake_keeps_last_config(self, tmp_path):
        target = tmp_path / "Game.exe"
        target.write_bytes(b"MZ")
        bake_config(target, {"TIMER_MINUTES": 1})
        bake_config(target, {"TIMER_MINUTES": 2})
        assert load_baked_config(target) == {"TIMER_MINUTES": 2}

    def test_is_faked_game_uses_marker_not_name(self, tmp_path):
        faked = tmp_path / "TotallyLegitName.exe"
        faked.write_bytes(b"MZ")
        assert not is_faked_game(faked)
        bake_config(faked, {"TIMER_MINUTES": 15})
        assert is_faked_game(faked)

        renamed_tool = tmp_path / "TslGame.exe"
        renamed_tool.write_bytes(b"MZ no marker")
        assert not is_faked_game(renamed_tool)
