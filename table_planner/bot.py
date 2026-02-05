"""Discord client implementation for the table planner bot."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from .storage import archive_tables, load_active_tables, remove_tables_for_channel, remove_tables_for_guild
from .types import ArchiveReason
from .views import SignupView

logger = logging.getLogger(__name__)


class TablePlannerBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        logger.info("Loading saved tables...")
        active_tables = load_active_tables()
        tables_to_archive: list[str] = []
        count = 0

        for table_id, info in active_tables.items():
            try:
                guild_id = int(info["guild_id"])
                channel_id = int(info["channel_id"])
            except (KeyError, TypeError, ValueError):
                tables_to_archive.append(table_id)
                continue

            if not guild_id or not channel_id:
                tables_to_archive.append(table_id)
                continue

            channel = self.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.fetch_channel(channel_id)
                except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                    channel = None

            if channel is None or not isinstance(channel, discord.TextChannel):
                tables_to_archive.append(table_id)
                continue

            if channel.guild.id != guild_id:
                tables_to_archive.append(table_id)
                continue

            view = SignupView(table_id, info["max_players"])
            self.add_view(view)
            count += 1

        if tables_to_archive:
            archived = archive_tables(tables_to_archive, ArchiveReason.NO_ACCESS)
            logger.warning(
                "Archived %s table(s) referencing inaccessible guilds/channels: %s",
                archived,
                ", ".join(tables_to_archive),
            )

        logger.info("%s active tables restored. Syncing commands...", count)
        await self.tree.sync()
        logger.info("Command tree synced.")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info("Received guild removal for %s (%s).", guild.name, guild.id)
        removed = remove_tables_for_guild(guild.id)
        if removed:
            logger.info(
                "Archived %s table(s) after leaving guild %s (%s).",
                removed,
                guild.name,
                guild.id,
            )
        else:
            logger.info("No stored tables required cleanup for guild %s (%s).", guild.name, guild.id)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        logger.info(
            "Received channel deletion for %s (%s) in guild %s.",
            getattr(channel, "name", "unknown"),
            channel.id,
            getattr(channel.guild, "id", "unknown"),
        )
        removed = remove_tables_for_channel(channel.id)
        if removed:
            logger.info(
                "Archived %s table(s) for deleted channel %s (%s).",
                removed,
                getattr(channel, "name", "unknown"),
                channel.id,
            )
        else:
            logger.info("No stored tables tied to deleted channel %s (%s).", getattr(channel, "name", "unknown"), channel.id)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined guild %s (%s) with %s members.", guild.name, guild.id, guild.member_count)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        logger.info(
            "Channel %s (%s) created in guild %s.",
            getattr(channel, "name", "unknown"),
            channel.id,
            getattr(channel.guild, "id", "unknown"),
        )
