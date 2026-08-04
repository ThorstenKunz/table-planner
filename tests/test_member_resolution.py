import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from table_planner import storage
from table_planner.member_resolution import (
    apply_display_name_updates,
    cached_resolvable_ids,
    refresh_table_members,
)
from table_planner.types import TableData


def _table(entries: list[dict]) -> TableData:
    return {
        "system": "Test",
        "infos": "Test",
        "schedule": "Soon",
        "created_at": None,
        "max_players": 4,
        "players": entries,
        "waitlist": [],
        "creator_id": 1,
        "gm_id": 1,
        "message_id": 2,
        "channel_id": 3,
        "guild_id": 4,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


class _Member:
    def __init__(self, user_id: int, display_name: str) -> None:
        self.id = user_id
        self.display_name = display_name


class _Guild:
    def __init__(self, cached: dict[int, _Member]) -> None:
        self.cached = cached
        self.fetch_member = AsyncMock(side_effect=lambda user_id: _Member(user_id, f"Fetched {user_id}"))

    def get_member(self, user_id: int) -> _Member | None:
        return self.cached.get(user_id)


def test_cached_resolvable_ids_never_fetches() -> None:
    guild = _Guild({1: _Member(1, "Cached")})
    table = _table([
        {"id": 1, "joined_at": "2026-01-01T00:00:00+00:00"},
        {"id": 2, "joined_at": "2026-01-01T00:00:00+00:00"},
    ])

    assert cached_resolvable_ids(guild, table) == {1}
    guild.fetch_member.assert_not_called()


def test_refresh_fetches_uncached_members_even_when_their_saved_name_is_fresh() -> None:
    guild = _Guild({1: _Member(1, "Cached")})
    table = _table([
        {"id": 1, "joined_at": "2026-01-01T00:00:00+00:00"},
        {
            "id": 2,
            "joined_at": "2026-01-01T00:00:00+00:00",
            "display_name": "Fresh",
            "display_name_updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {"id": 3, "joined_at": "2026-01-01T00:00:00+00:00", "display_name": "Old"},
    ])

    resolvable, updates = asyncio.run(refresh_table_members(guild, table))

    assert resolvable == {1, 2, 3}
    assert updates[1][0] == "Cached"
    assert updates[3][0] == "Fetched 3"
    assert 2 not in updates
    assert guild.fetch_member.await_count == 2
    assert {call.args[0] for call in guild.fetch_member.await_args_list} == {2, 3}


def test_refreshed_name_is_merged_into_latest_table(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(tmp_path / "active.json"))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(tmp_path / "archived.json"))
    storage.save_tables(
        {"table-1": _table([{"id": 1, "joined_at": "2026-01-01T00:00:00+00:00"}])},
        {},
    )

    updated = apply_display_name_updates(
        "table-1",
        {1: ("Updated", "2026-08-03T20:00:00+00:00")},
    )

    assert updated is not None
    entry = storage.load_active_tables()["table-1"]["players"][0]
    assert entry["display_name"] == "Updated"
    assert entry["display_name_updated_at"] == "2026-08-03T20:00:00+00:00"
