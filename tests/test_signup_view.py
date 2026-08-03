import asyncio
import logging
from pathlib import Path

from table_planner import storage, views
from table_planner.types import TableData


class _Response:
    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self) -> None:
        self.done = True

    async def send_message(self, *_args, **_kwargs) -> None:
        self.done = True


class _Followup:
    async def send(self, *_args, **_kwargs) -> None:
        return None


class _Message:
    def __init__(self, message_id: int) -> None:
        self.id = message_id
        self.edits: list[dict] = []

    async def edit(self, **kwargs) -> None:
        await asyncio.sleep(0)
        self.edits.append(kwargs)


class _User:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.name = f"user-{user_id}"
        self.display_name = self.name
        self.messages: list[str] = []

    async def send(self, content: str) -> None:
        self.messages.append(content)

    def __str__(self) -> str:
        return self.name


class _Client:
    def __init__(self, users: dict[int, _User]) -> None:
        self.users = users

    def get_user(self, user_id: int) -> _User | None:
        return self.users.get(user_id)

    async def fetch_user(self, user_id: int) -> _User:
        return self.users[user_id]

    def get_channel(self, _channel_id: int):
        return None

    async def fetch_channel(self, _channel_id: int):
        return None


class _Interaction:
    def __init__(self, user: _User, message: _Message, client: _Client) -> None:
        self.user = user
        self.message = message
        self.client = client
        self.response = _Response()
        self.followup = _Followup()
        self.guild = None
        self.channel = None


def _table(players: list[dict], waitlist: list[dict], max_players: int) -> TableData:
    return {
        "system": "Test",
        "infos": "Concurrency test",
        "schedule": "Soon",
        "created_at": None,
        "max_players": max_players,
        "players": players,
        "waitlist": waitlist,
        "creator_id": 100,
        "gm_id": 100,
        "message_id": 200,
        "channel_id": 300,
        "guild_id": 400,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


def _configure_storage(tmp_path: Path, monkeypatch, table: TableData) -> None:
    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(tmp_path / "active.json"))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(tmp_path / "archived.json"))
    storage.save_tables({"table-1": table}, {})
    views._TABLE_UPDATE_LOCKS.clear()


def test_concurrent_joins_do_not_lose_the_waitlist(tmp_path: Path, monkeypatch) -> None:
    _configure_storage(tmp_path, monkeypatch, _table([], [], 1))
    users = {user_id: _User(user_id) for user_id in (1, 2)}
    client = _Client(users)
    message = _Message(200)

    async def run() -> None:
        await asyncio.gather(*(
            views.SignupView("table-1", 1).join_callback(_Interaction(user, message, client))
            for user in users.values()
        ))

    asyncio.run(run())

    table = storage.load_active_tables()["table-1"]
    assert len(table["players"]) == 1
    assert len(table["waitlist"]) == 1
    assert {table["players"][0]["id"], table["waitlist"][0]["id"]} == {1, 2}
    assert message.edits[-1]["embed"].fields[4].name == "Waitlist (1)"


def test_concurrent_leaves_promote_each_waiting_player(tmp_path: Path, monkeypatch) -> None:
    players = [
        {"id": 1, "joined_at": "2026-01-01T00:00:01+00:00", "display_name": "One"},
        {"id": 2, "joined_at": "2026-01-01T00:00:02+00:00", "display_name": "Two"},
    ]
    waitlist = [
        {"id": 3, "joined_at": "2026-01-01T00:00:03+00:00", "display_name": "Three"},
        {"id": 4, "joined_at": "2026-01-01T00:00:04+00:00", "display_name": "Four"},
    ]
    _configure_storage(tmp_path, monkeypatch, _table(players, waitlist, 2))
    users = {user_id: _User(user_id) for user_id in (1, 2, 3, 4)}
    client = _Client(users)
    message = _Message(200)

    async def run() -> None:
        await asyncio.gather(*(
            views.SignupView("table-1", 2).leave_callback(_Interaction(users[user_id], message, client))
            for user_id in (1, 2)
        ))

    asyncio.run(run())

    table = storage.load_active_tables()["table-1"]
    assert {entry["id"] for entry in table["players"]} == {3, 4}
    assert table["waitlist"] == []
    assert message.edits[-1]["embed"].fields[4].name == "Waitlist (0)"


def test_signup_view_error_handler_returns_reference(caplog) -> None:
    user = _User(1)
    interaction = _Interaction(user, _Message(200), _Client({1: user}))
    interaction.response.done = True
    sent_messages: list[str] = []

    async def capture(content: str, **_kwargs) -> None:
        sent_messages.append(content)

    interaction.followup.send = capture

    async def run() -> None:
        view = views.SignupView("table-1", 1)
        item = view.children[0]
        await view.on_error(interaction, ValueError("injected"), item)

    with caplog.at_level(logging.ERROR):
        asyncio.run(run())

    assert len(sent_messages) == 1
    assert "reference:" in sent_messages[0]
    assert "table=table-1" in caplog.text
