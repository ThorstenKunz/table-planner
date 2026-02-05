"""/archive-table command."""

from __future__ import annotations

import logging

import discord

from ..discord_utils import safe_response_send
from ..storage import load_active_tables
from ..types import TableData
from ..views import ArchiveView

logger = logging.getLogger(__name__)


def register_archive_table(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="archive-table", description="Select one of your tables to archive it.")
    async def archive_table(interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("Command /archive-table invoked by %s (%s).", user, user.id)
        data = load_active_tables()

        user_tables: dict[str, TableData] = {}
        for table_id, info in data.items():
            if info["creator_id"] == user.id:
                user_tables[table_id] = info
                continue

            channel = bot.get_channel(info["channel_id"])
            if isinstance(channel, discord.TextChannel):
                member = channel.guild.get_member(user.id)
                if member is None:
                    continue
                permissions = channel.permissions_for(member)
                if permissions.manage_messages:
                    user_tables[table_id] = info

        if not user_tables:
            logger.info("User %s (%s) tried to archive but lacks eligible tables.", user, user.id)
            await safe_response_send(
                interaction,
                "You have no active tables you can archive.",
                ephemeral=True,
            )
            return

        view = ArchiveView(bot, user_tables, user.id)
        await safe_response_send(
            interaction,
            "Please select one of your tables to archive:",
            view=view,
            ephemeral=True,
        )
        logger.info("Displayed archive selector for %s tables to %s (%s).", len(user_tables), user, user.id)
