"""The screens of two-player play: the name in the settings, the text field, the Play panel,
the match scene (AC9, AC10 and the menu flow)."""

import json

from game import config, settings


def test_the_player_name_is_kept_cleaned_and_limited(tmp_path):
    path = tmp_path / "s.json"
    s = settings.Settings(player_name="Lan Anh")
    assert settings.save(s, path)
    assert settings.load(path).player_name == "Lan Anh"
    raw = {"player_name": "  Bình\t\n" + "x" * 50}
    path.write_text(json.dumps(raw), encoding="utf-8")
    name = settings.load(path).player_name
    assert name.startswith("Bình") and len(name) == config.NET_NAME_MAX and "\t" not in name
    path.write_text(json.dumps({"player_name": 7}), encoding="utf-8")
    assert settings.load(path).player_name == ""  # a wrong type falls back to the default
