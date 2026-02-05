"""/show-tables command."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord

from ..storage import load_active_tables
from ..ui import create_table_embed
from ..views import SignupView
from ..discord_utils import safe_followup_send, safe_response_send
from .utils import check_guild_rate_limit, check_user_rate_limit, filter_tables_for_dm, resolve_resolvable_ids

logger = logging.getLogger(__name__)


def register_show_tables(tree: discord.app_commands.CommandTree) -> None:
    @tree.command(name="show-tables", description="Shows all active tables.")
    async def show_tables(interaction: discord.Interaction) -> None:
        user = interaction.user
        channel = interaction.channel
        logger.info("Command /show-tables invoked by %s (%s).", user, user.id)

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
        is_guild_channel = isinstance(channel, discord.TextChannel)
        channel_id = getattr(channel, "id", 0)
        channel_name = getattr(channel, "name", "DM") if is_guild_channel else "DM"
        scope_label = (
            f"channel {channel_name} ({channel_id})" if is_guild_channel else f"DM ({channel_id})"
        )

        channel_tables = (
            {
                table_id: info
                for table_id, info in active_tables.items()
                if info["channel_id"] == channel_id
            }
            if is_guild_channel and channel is not None
            else await filter_tables_for_dm(interaction, active_tables)
        )

        if not channel_tables:
            logger.info(
                "No active tables found for %s requested by %s (%s).",
                scope_label,
                user,
                user.id,
            )
            await safe_response_send(
                interaction,
                "There are currently no active tables in this context.",
                ephemeral=is_guild_channel,
            )
            return

        await safe_response_send(
            interaction,
            (
                f"Found {len(channel_tables)} active table(s) in this channel. Sending them to you now..."
                if is_guild_channel
                else f"Found {len(channel_tables)} active table(s) you can access across your servers."
            ),
            ephemeral=is_guild_channel,
        )

        for table_id, table_data in channel_tables.items():
            resolvable_ids = await resolve_resolvable_ids(interaction.guild, table_data)
            embed = create_table_embed(table_data, table_id, resolvable_ids=resolvable_ids)
            view = SignupView(table_id, table_data["max_players"])
            await safe_followup_send(
                interaction,
                "",
                embed=embed,
                view=view,
                ephemeral=is_guild_channel,
            )

        logger.info(
            "Displayed %s active tables for %s to %s (%s).",
            len(channel_tables),
            scope_label,
            user,
            user.id,
        )
