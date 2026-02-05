"""/my-tables command."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.utils import escape_markdown, escape_mentions

from ..config import get_my_table_column_widths
from ..discord_utils import safe_response_send
from ..storage import load_active_tables
from ..types import TableData
from .utils import check_guild_rate_limit, check_user_rate_limit, format_cell, resolve_gm_name

logger = logging.getLogger(__name__)


def register_my_tables(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="my-tables", description="Shows tables you run or play in.")
    async def my_tables(interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("Command /my-tables invoked by %s (%s).", user, user.id)

        now = datetime.now(tz=timezone.utc)
        allowed, wait_seconds = check_user_rate_limit(user.id, now)
        if not allowed:
            await safe_response_send(
                interaction,
                f"Please wait {wait_seconds} more second(s) before running this command again.",
                ephemeral=True,
            )
            return

        if interaction.guild is not None:
            guild_allowed, guild_wait = check_guild_rate_limit(interaction.guild.id, now)
            if not guild_allowed:
                await safe_response_send(
                    interaction,
                    f"This server is busy. Please wait {guild_wait} more second(s) before trying again.",
                    ephemeral=True,
                )
                return

        active_tables = load_active_tables()
        relevant: dict[str, tuple[TableData, str]] = {}

        for table_id, info in active_tables.items():
            status: Optional[str] = None
            if info["creator_id"] == user.id:
                status = "DM"
            elif any(entry["id"] == user.id for entry in info["players"]):
                status = "Player"
            elif any(entry["id"] == user.id for entry in info.get("waitlist", [])):
                status = "Waiting"

            if status:
                relevant[table_id] = (info, status)

        if interaction.guild is not None:
            relevant = {
                table_id: entry
                for table_id, entry in relevant.items()
                if entry[0]["guild_id"] == interaction.guild.id
            }
        else:
            guild_ids = {entry[0]["guild_id"] for entry in relevant.values()}
            if len(guild_ids) > 1:
                await safe_response_send(
                    interaction,
                    "You have tables on multiple servers. Please run /my-tables in the server you want to see.",
                    ephemeral=True,
                )
                return
            if guild_ids:
                target_guild_id = next(iter(guild_ids))
                relevant = {
                    table_id: entry
                    for table_id, entry in relevant.items()
                    if entry[0]["guild_id"] == target_guild_id
                }

        if not relevant:
            await safe_response_send(
                interaction,
                "You are not currently running or signed up for any tables.",
                ephemeral=True,
            )
            return

        sorted_items = sorted(relevant.items(), key=lambda item: item[1][0]["schedule"])

        widths = get_my_table_column_widths()
        system_width = max(4, widths.get("system", 20))
        schedule_width = max(4, widths.get("schedule", 24))
        gm_width = max(4, widths.get("gm", 24))
        players_width = max(4, widths.get("players", 10))
        status_width = max(4, widths.get("status", 8))

        header = (
            f"{'System':<{system_width}} "
            f"{'Schedule':<{schedule_width}} "
            f"{'GM':<{gm_width}} "
            f"{'Players':<{players_width}} "
            f"{'Status':<{status_width}}"
        )
        rows: list[str] = [header, "-" * len(header)]

        gm_name_cache: dict[int, str] = {}

        for table_id, (info, status) in sorted_items:
            safe_system = escape_mentions(escape_markdown(info["system"]))
            safe_schedule = escape_mentions(escape_markdown(info["schedule"]))
            gm_display = await resolve_gm_name(bot, info["creator_id"], info["guild_id"], gm_name_cache)
            wait_count = len(info.get("waitlist", []))
            seats = f"{len(info['players'])}/{info['max_players']}"
            if wait_count:
                seats = f"{seats} (+{wait_count})"

            system_cell = format_cell(safe_system, system_width)
            schedule_cell = format_cell(safe_schedule, schedule_width)
            gm_cell = format_cell(gm_display, gm_width)
            players_cell = format_cell(seats, players_width)
            status_cell = format_cell(status, status_width)

            rows.append(f"{system_cell} {schedule_cell} {gm_cell} {players_cell} {status_cell}")

        table_output = "\n".join(rows)
        content = f"```\n{table_output}\n```"

        await safe_response_send(interaction, content, ephemeral=True)
        logger.info(
            "Displayed %s table(s) for /my-tables to %s (%s).",
            len(relevant),
            user,
            user.id,
        )
