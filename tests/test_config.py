import json
from pathlib import Path

from table_planner import config


def test_get_user_command_rate_limit_defaults(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(config, "_user_command_rate_limit_cache", None)

    max_commands, window_seconds = config.get_user_command_rate_limit()
    assert max_commands == 3
    assert window_seconds == 10


def test_get_user_command_rate_limit_override(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    payload = {
        "rate_limits": {
            "user_command_limit": 5,
            "user_command_window_seconds": 20,
        }
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(config, "_user_command_rate_limit_cache", None)

    max_commands, window_seconds = config.get_user_command_rate_limit()
    assert max_commands == 5
    assert window_seconds == 20


def test_get_guild_command_rate_limit_override(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    payload = {
        "rate_limits": {
            "guild_command_limit": 7,
            "guild_command_window_seconds": 15,
        }
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(config, "_guild_command_rate_limit_cache", None)

    max_commands, window_seconds = config.get_guild_command_rate_limit()
    assert max_commands == 7
    assert window_seconds == 15
