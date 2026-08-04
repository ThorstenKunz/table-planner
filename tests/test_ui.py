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
        "message_id": 20,
        "channel_id": 30,
        "guild_id": 40,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


def test_member_display_prefers_confirmed_mention_then_name_then_plain_id() -> None:
    embed = create_table_embed(_table(), "table-1", resolvable_ids={1})

    assert embed.fields[3].value == "• <@1>\n• Saved Name\n• 3"


def test_missing_resolution_context_never_creates_an_unconfirmed_mention() -> None:
    embed = create_table_embed(_table(), "table-1")

    assert embed.fields[3].value == "• Mentioned\n• Saved Name\n• 3"
