from table_planner.types import TableData
from table_planner.ui import create_table_embed


def _table() -> TableData:
    return {
        "system": "Test",
        "infos": "Mention fallback test",
        "schedule": "Soon",
        "created_at": None,
        "max_players": 3,
        "players": [
            {"id": 1, "joined_at": "now", "display_name": "Mentioned"},
            {"id": 2, "joined_at": "now", "display_name": "Saved Name"},
            {"id": 3, "joined_at": "now"},
        ],
        "waitlist": [],
        "creator_id": 10,
        "gm_id": 10,
        "gm_display_name": "Game Master",
        "message_id": 20,
        "channel_id": 30,
        "guild_id": 40,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


def test_member_display_prefers_name_then_plain_id_without_mention_syntax() -> None:
    embed = create_table_embed(_table(), "table-1")

    assert embed.fields[1].value == "Game Master"
    assert embed.fields[3].value == "• Mentioned\n• Saved Name\n• 3"


def test_embed_contains_no_user_mention_syntax() -> None:
    embed = create_table_embed(_table(), "table-1")

    assert all("<@" not in str(field.value) for field in embed.fields)
