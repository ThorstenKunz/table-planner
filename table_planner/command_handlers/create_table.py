"""/create-table command."""

from __future__ import annotations

import logging

import discord

from ..discord_utils import safe_response_send
from ..modals import NewTableModal

logger = logging.getLogger(__name__)


def register_create_table(tree: discord.app_commands.CommandTree, bot: discord.Client) -> None:
    @tree.command(name="create-table", description="Opens a form to create a new game table.")
    async def create_table(interaction: discord.Interaction, gm: discord.Member | None = None) -> None:
        user = interaction.user
        logger.info("Command /create-table invoked by %s (%s).", user, user.id)
        if interaction.guild is None or interaction.channel is None:
            await safe_response_send(
                interaction,
                "This command can only be used in a server channel.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await safe_response_send(
                interaction,
                "This command can only be used in a server text channel.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await safe_response_send(
                interaction,
                "This command can only be used by server members.",
                ephemeral=True,
            )
            return

        selected_gm = gm or interaction.user
        if selected_gm.id != interaction.user.id:
            if not interaction.channel.permissions_for(interaction.user).manage_messages:
                await safe_response_send(
                    interaction,
                    "You may only choose a different GM if you can manage messages in this channel.",
                    ephemeral=True,
                )
                return
            if not interaction.channel.permissions_for(selected_gm).view_channel:
                await safe_response_send(
                    interaction,
                    "The selected GM cannot access this channel.",
                    ephemeral=True,
                )
                return

        modal = NewTableModal(bot, creator_id=interaction.user.id, gm_id=selected_gm.id)
        await interaction.response.send_modal(modal)
