"""UI helpers for table embeds."""

import discord
from discord.utils import escape_markdown, escape_mentions

from .table_access import get_gm_id
from .types import TableData


def _format_member_entry(entry: object, resolvable_ids: set[int] | None) -> str:
    """Prefer a confirmed mention, then a stored name, then a plain user ID."""
    if not isinstance(entry, dict):
        return "Unknown user"

    user_id = entry.get("id")
    if isinstance(user_id, int) and user_id > 0 and resolvable_ids is not None and user_id in resolvable_ids:
        return f"<@{user_id}>"

    display_name = entry.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        return escape_mentions(escape_markdown(display_name.strip()))

    if isinstance(user_id, int) and user_id > 0:
        return str(user_id)
    return "Unknown user"


def create_table_embed(table_data: TableData, table_id: str, resolvable_ids: set[int] | None = None) -> discord.Embed:
    """Creates a standardized embed for a table."""
    safe_system = escape_mentions(escape_markdown(table_data["system"]))
    safe_schedule = escape_mentions(escape_markdown(table_data["schedule"]))
    safe_infos = escape_mentions(escape_markdown(table_data["infos"]))

    embed = discord.Embed(title=f"🎲 {safe_system}", color=discord.Color.dark_purple())
    embed.add_field(name="⏰ Schedule", value=safe_schedule, inline=True)
    embed.add_field(name="🧙 GM", value=f"<@{get_gm_id(table_data)}>", inline=True)
    embed.add_field(name="📜 Infos", value=safe_infos, inline=False)

    players = table_data["players"]
    player_mentions = [f"• {_format_member_entry(entry, resolvable_ids)}" for entry in players]
    player_list = "\n".join(player_mentions) if player_mentions else "No players yet."
    embed.add_field(name=f"Players ({len(players)}/{table_data['max_players']})", value=player_list, inline=False)

    waitlist = table_data.get("waitlist", [])
    waitlist_mentions = [f"• {_format_member_entry(entry, resolvable_ids)}" for entry in waitlist]
    waitlist_value = "\n".join(waitlist_mentions) if waitlist_mentions else "No one waiting."
    embed.add_field(name=f"Waitlist ({len(waitlist)})", value=waitlist_value, inline=False)

    embed.set_footer(text=f"Table ID: {table_id}")
    return embed
