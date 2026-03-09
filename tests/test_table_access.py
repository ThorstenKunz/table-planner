from table_planner.table_access import get_gm_id, is_table_owner, normalize_table_record, parse_user_reference
from table_planner.command_handlers.utils import table_owner_status
from table_planner.types import TableData


def _sample_table() -> TableData:
    return {
        "system": "Test System",
        "infos": "Test",
        "schedule": "Soon",
        "created_at": "2025-01-01T00:00:00Z",
        "max_players": 4,
        "players": [],
        "waitlist": [],
        "creator_id": 123,
        "gm_id": 456,
        "message_id": 789,
        "channel_id": 101112,
        "guild_id": 131415,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


def test_get_gm_id_falls_back_to_creator() -> None:
    table = _sample_table()
    table["gm_id"] = 0

    assert get_gm_id(table) == 123


def test_normalize_table_record_sets_missing_gm_id() -> None:
    table = dict(_sample_table())
    table.pop("gm_id")

    normalized = normalize_table_record(table)

    assert normalized["gm_id"] == 123


def test_is_table_owner_accepts_creator_and_gm() -> None:
    table = _sample_table()

    assert is_table_owner(123, table)
    assert is_table_owner(456, table)
    assert not is_table_owner(999, table)


def test_table_owner_status_distinguishes_owner_roles() -> None:
    table = _sample_table()

    assert table_owner_status(123, table) == "Owner"
    assert table_owner_status(456, table) == "GM"
    assert table_owner_status(999, table) is None


def test_parse_user_reference_accepts_mentions_and_ids() -> None:
    assert parse_user_reference("12345") == 12345
    assert parse_user_reference("<@12345>") == 12345
    assert parse_user_reference("<@!12345>") == 12345
    assert parse_user_reference("not-a-user") is None