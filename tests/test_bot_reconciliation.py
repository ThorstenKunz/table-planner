import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from table_planner import bot as bot_module
from table_planner.types import TableData


def _table() -> TableData:
    return {
        "system": "Test",
        "infos": "Restart reconciliation",
        "schedule": "Soon",
        "created_at": None,
        "max_players": 2,
        "players": [
            {"id": 1, "joined_at": "2026-01-01T00:00:00+00:00", "display_name": "Player"},
            {"id": 3, "joined_at": "2026-01-01T00:00:00+00:00", "display_name": "Player 2"},
        ],
        "waitlist": [
            {"id": 2, "joined_at": "2026-01-01T00:00:01+00:00", "display_name": "Waiting"}
        ],
        "creator_id": 10,
        "gm_id": 10,
        "message_id": 20,
        "channel_id": 30,
        "guild_id": 40,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


class _Guild:
    id = 40

    def get_member(self, _user_id: int):
        return None


class _Message:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit(self, **kwargs) -> None:
        self.edits.append(kwargs)


class _TextChannel:
    def __init__(self, message: _Message) -> None:
        self.guild = _Guild()
        self.message = message

    async def fetch_message(self, message_id: int) -> _Message:
        assert message_id == 20
        return self.message


class _Tree:
    def __init__(self) -> None:
        self.sync = AsyncMock()


class _Bot:
    setup_hook = bot_module.TablePlannerBot.setup_hook

    def __init__(self, channel: _TextChannel) -> None:
        self.channel = channel
        self.tree = _Tree()
        self.views = []

    def get_channel(self, channel_id: int) -> _TextChannel:
        assert channel_id == 30
        return self.channel

    async def fetch_channel(self, _channel_id: int) -> _TextChannel:
        return self.channel

    def add_view(self, view) -> None:
        self.views.append(view)


def test_setup_hook_resyncs_original_table_message(monkeypatch, caplog) -> None:
    message = _Message()
    channel = _TextChannel(message)
    test_bot = _Bot(channel)
    monkeypatch.setattr(bot_module.discord, "TextChannel", _TextChannel)
    monkeypatch.setattr(bot_module, "load_active_tables", lambda: {"table-1": _table()})
    monkeypatch.setattr(bot_module, "refresh_table_members", AsyncMock(return_value=(set(), {})))

    with caplog.at_level(logging.INFO):
        asyncio.run(test_bot.setup_hook())

    assert len(test_bot.views) == 1
    assert len(message.edits) == 1
    embed = message.edits[0]["embed"]
    assert embed.fields[3].name == "Players (2/2)"
    assert embed.fields[4].name == "Waitlist (1)"
    assert message.edits[0]["view"] is test_bot.views[0]
    assert test_bot.views[0].join_btn.label == "Join Waitlist"
    assert test_bot.views[0].join_btn.style == bot_module.discord.ButtonStyle.grey
    test_bot.tree.sync.assert_awaited_once_with()
    assert "Synchronized original embed for table table-1" in caplog.text
    assert "active=1, views_registered=1, embeds_synced=1" in caplog.text


def test_setup_hook_does_not_archive_on_temporary_discord_error(monkeypatch) -> None:
    class TemporaryDiscordError(Exception):
        pass

    class UnavailableBot(_Bot):
        def get_channel(self, _channel_id: int):
            return None

        async def fetch_channel(self, _channel_id: int):
            raise TemporaryDiscordError("temporary outage")

    archive_tables = Mock(return_value=0)
    test_bot = UnavailableBot(_TextChannel(_Message()))
    monkeypatch.setattr(bot_module.discord, "HTTPException", TemporaryDiscordError)
    monkeypatch.setattr(bot_module, "load_active_tables", lambda: {"table-1": _table()})
    monkeypatch.setattr(bot_module, "archive_tables", archive_tables)

    asyncio.run(test_bot.setup_hook())

    assert len(test_bot.views) == 1
    archive_tables.assert_not_called()
    test_bot.tree.sync.assert_awaited_once_with()
