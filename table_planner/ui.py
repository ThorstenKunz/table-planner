"""UI helpers for table embeds."""

import discord
from discord.utils import escape_markdown, escape_mentions

from .types import TableData


def create_table_embed(table_data: TableData, table_id: str, resolvable_ids: set[int] | None = None) -> discord.Embed:
    """Creates a standardized embed for a table."""
    safe_system = escape_mentions(escape_markdown(table_data["system"]))
    safe_schedule = escape_mentions(escape_markdown(table_data["schedule"]))
    safe_infos = escape_mentions(escape_markdown(table_data["infos"]))

    embed = discord.Embed(title=f"🎲 {safe_system}", color=discord.Color.dark_purple())
    embed.add_field(name="⏰ Schedule", value=safe_schedule, inline=True)
    embed.add_field(name="🧙 GM", value=f"<@{table_data['creator_id']}>", inline=True)
    embed.add_field(name="📜 Infos", value=safe_infos, inline=False)

    players = table_data["players"]
    player_mentions = []
    for entry in players:
        display_name = entry.get("display_name")
        user_id = entry.get("id")
        if isinstance(user_id, int) and user_id > 0 and (resolvable_ids is None or user_id in resolvable_ids):
            player_mentions.append(f"• <@{user_id}>")
        elif isinstance(display_name, str) and display_name.strip():
            safe_name = escape_mentions(escape_markdown(display_name.strip()))
            player_mentions.append(f"• {safe_name}")
        else:
            player_mentions.append("• Unknown user")
    player_list = "\n".join(player_mentions) if player_mentions else "No players yet."
    embed.add_field(name=f"Players ({len(players)}/{table_data['max_players']})", value=player_list, inline=False)

    waitlist = table_data.get("waitlist", [])
    waitlist_mentions = []
    for entry in waitlist:
        display_name = entry.get("display_name")
        user_id = entry.get("id")
        if isinstance(user_id, int) and user_id > 0 and (resolvable_ids is None or user_id in resolvable_ids):
            waitlist_mentions.append(f"• <@{user_id}>")
        elif isinstance(display_name, str) and display_name.strip():
            safe_name = escape_mentions(escape_markdown(display_name.strip()))
            waitlist_mentions.append(f"• {safe_name}")
        else:
            waitlist_mentions.append("• Unknown user")
    waitlist_value = "\n".join(waitlist_mentions) if waitlist_mentions else "No one waiting."
    embed.add_field(name=f"Waitlist ({len(waitlist)})", value=waitlist_value, inline=False)

    embed.set_footer(text=f"Table ID: {table_id}")
    return embed
