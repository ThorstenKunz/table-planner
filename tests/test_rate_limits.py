from datetime import datetime, timedelta, timezone

from table_planner.command_handlers import utils


def test_user_rate_limit_blocks_after_limit(monkeypatch) -> None:
    monkeypatch.setattr(utils, "_user_rate_limits", {})

    def fake_rate_limit() -> tuple[int, int]:
        return (2, 10)

    monkeypatch.setattr(utils, "get_user_command_rate_limit", fake_rate_limit)

    now = datetime.now(tz=timezone.utc)
    allowed, _ = utils.check_user_rate_limit(1, now)
    assert allowed is True
    allowed, _ = utils.check_user_rate_limit(1, now + timedelta(seconds=1))
    assert allowed is True
    allowed, wait_seconds = utils.check_user_rate_limit(1, now + timedelta(seconds=2))
    assert allowed is False
    assert wait_seconds >= 0


def test_guild_rate_limit_blocks_after_limit(monkeypatch) -> None:
    monkeypatch.setattr(utils, "_guild_rate_limits", {})

    def fake_rate_limit() -> tuple[int, int]:
        return (1, 5)

    monkeypatch.setattr(utils, "get_guild_command_rate_limit", fake_rate_limit)

    now = datetime.now(tz=timezone.utc)
    allowed, _ = utils.check_guild_rate_limit(99, now)
    assert allowed is True
    allowed, wait_seconds = utils.check_guild_rate_limit(99, now + timedelta(seconds=1))
    assert allowed is False
    assert wait_seconds >= 0
