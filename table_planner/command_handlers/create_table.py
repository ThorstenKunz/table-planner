"""/create-table command."""

from __future__ import annotations

import logging

import discord

from ..modals import NewTableModal
from ..discord_utils import safe_response_send

logger = logging.getLogger(__name__)


def register_create_table(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="create-table", description="Opens a form to create a new game table.")
    async def create_table(interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("Command /create-table invoked by %s (%s).", user, user.id)
        if interaction.guild is None or interaction.channel is None:
            await safe_response_send(
                interaction,
                "This command can only be used in a server channel.",
                ephemeral=True,
            )
            return
        modal = NewTableModal(bot)
        await interaction.response.send_modal(modal)
