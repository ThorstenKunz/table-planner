"""/edit-table command."""

from __future__ import annotations

import logging

import discord

from ..discord_utils import safe_response_send
from ..storage import load_active_tables
from ..types import TableData
from ..views import EditTableView

logger = logging.getLogger(__name__)


def register_edit_table(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="edit-table", description="Select one of your tables to edit it.")
    async def edit_table(interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("Command /edit-table invoked by %s (%s).", user, user.id)
        if interaction.guild is None or interaction.channel is None:
            await safe_response_send(
                interaction,
                "This command can only be used in a server channel.",
                ephemeral=True,
            )
            return
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
            logger.info("User %s (%s) tried to edit but lacks eligible tables.", user, user.id)
            await safe_response_send(
                interaction,
                "You have no active tables you can edit.",
                ephemeral=True,
            )
            return

        view = EditTableView(bot, user_tables, user.id)
        await safe_response_send(
            interaction,
            "Please select one of your tables to edit:",
            view=view,
            ephemeral=True,
        )
        logger.info("Displayed edit selector for %s tables to %s (%s).", len(user_tables), user, user.id)
