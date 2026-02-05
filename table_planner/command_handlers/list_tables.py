"""/list-tables command."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.utils import escape_markdown, escape_mentions

from ..config import get_list_table_column_widths
from ..discord_utils import safe_followup_send, safe_response_send
from ..storage import load_active_tables
from .utils import check_guild_rate_limit, check_user_rate_limit, filter_tables_for_dm, format_cell, resolve_gm_name

logger = logging.getLogger(__name__)

LIST_TABLES_COOLDOWN = timedelta(minutes=1)
_channel_rate_limits: dict[int, datetime] = {}


def register_list_tables(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="list-tables", description="Posts all active tables into the current channel.")
    async def list_tables(interaction: discord.Interaction) -> None:
        user = interaction.user
        channel = interaction.channel
        logger.info("Command /list-tables invoked by %s (%s).", user, user.id)

        is_guild_channel = isinstance(channel, discord.TextChannel)
        channel_id = getattr(channel, "id", 0)
        channel_name = getattr(channel, "name", "DM") if is_guild_channel else "DM"

        now = datetime.now(tz=timezone.utc)
        allowed, wait_seconds = check_user_rate_limit(user.id, now)
        if not allowed:
            await safe_response_send(
                interaction,
                f"Please wait {wait_seconds} more second(s) before running this command again.",
                ephemeral=is_guild_channel,
            )
            return

        if interaction.guild is not None:
            guild_allowed, guild_wait = check_guild_rate_limit(interaction.guild.id, now)
            if not guild_allowed:
                await safe_response_send(
                    interaction,
                    f"This server is busy. Please wait {guild_wait} more second(s) before trying again.",
                    ephemeral=is_guild_channel,
                )
                return

        last_run = _channel_rate_limits.get(channel_id)
        if last_run and now - last_run < LIST_TABLES_COOLDOWN:
            remaining = LIST_TABLES_COOLDOWN - (now - last_run)
            await safe_response_send(
                interaction,
                f"Please wait {int(remaining.total_seconds())} more second(s) before listing tables again.",
                ephemeral=is_guild_channel,
            )
            logger.info(
                "/list-tables throttled in channel %s (%s) for user %s (%s).",
                channel_name,
                channel_id,
                user,
                user.id,
            )
            return

        active_tables = load_active_tables()

        channel_tables = (
            {
                table_id: info
                for table_id, info in active_tables.items()
                if info["channel_id"] == channel_id
            }
            if is_guild_channel
            else await filter_tables_for_dm(interaction, active_tables)
        )

        if not channel_tables:
            await safe_response_send(
                interaction,
                "There are no active tables in this context.",
                ephemeral=is_guild_channel,
            )
            return

        sorted_items = sorted(channel_tables.items(), key=lambda item: item[1]["schedule"])

        widths = get_list_table_column_widths()
        system_width = max(4, widths.get("system", 20))
        schedule_width = max(4, widths.get("schedule", 24))
        gm_width = max(4, widths.get("gm", 24))
        players_width = max(4, widths.get("players", 10))

        header = (
            f"{'System':<{system_width}} "
            f"{'Schedule':<{schedule_width}} "
            f"{'GM':<{gm_width}} "
            f"{'Players':<{players_width}}"
        )
        rows: list[str] = [header, "-" * len(header)]

        gm_name_cache: dict[int, str] = {}

        for table_id, info in sorted_items:
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

            rows.append(f"{system_cell} {schedule_cell} {gm_cell} {players_cell}")

        table_output = "\n".join(rows)
        content = f"```\n{table_output}\n```"

        if not await safe_response_send(interaction, content, ephemeral=False):
            if interaction.response.is_done():
                await safe_followup_send(
                    interaction,
                    "I couldn't post the list due to a permission or API error.",
                    ephemeral=True,
                )
            return

        _channel_rate_limits[channel_id] = now
        logger.info(
            "Posted %s table(s) to channel %s (%s).",
            len(channel_tables),
            channel_name,
            channel_id,
        )
