from table_planner.types import TableData
from table_planner.views import _table_select_option


def _table() -> TableData:
    return {
        "system": "Daggerheart",
        "infos": "The same recurring expedition information",
        "schedule": "Friday 14 August, 18:00",
        "created_at": None,
        "max_players": 5,
        "players": [],
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


def test_table_selector_combines_system_schedule_and_infos_in_its_label() -> None:
    option = _table_select_option("table-abcd", _table())

    assert option.label == "Daggerheart | Friday 14 August, 18:00 | The same recurring expedition information"
    assert option.description == "Table ID: abcd"
    assert option.value == "table-abcd"


def test_table_selector_keeps_date_and_description_within_discord_limits() -> None:
    table = _table()
    table["schedule"] = "Date " * 40
    table["system"] = "System " * 30
    table["infos"] = "Info " * 40

    option = _table_select_option("table-1234", table)

    assert len(option.label) <= 100
    assert option.label.count(" | ") == 2
    system, schedule, infos = option.label.split(" | ")
    assert system
    assert schedule
    assert infos
    assert option.description is not None
    assert len(option.description) <= 100
