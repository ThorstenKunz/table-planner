"""Discord client implementation for the table planner bot."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands

from .storage import archive_tables, load_active_tables, remove_tables_for_channel, remove_tables_for_guild
from .member_resolution import apply_display_name_updates, cached_resolvable_ids, refresh_table_members
from .types import ArchiveReason
from .ui import create_table_embed
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

            view = SignupView(table_id, info["max_players"])
            self.add_view(view)
            count += 1

            channel = self.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.fetch_channel(channel_id)
                except discord.NotFound:
                    tables_to_archive.append(table_id)
                    continue
                except discord.Forbidden:
                    logger.warning(
                        "Cannot access channel %s for table %s during startup reconciliation.",
                        channel_id,
                        table_id,
                    )
                    continue
                except discord.HTTPException as exc:
                    logger.warning(
                        "Temporary Discord error resolving channel %s for table %s: %s",
                        channel_id,
                        table_id,
                        exc,
                    )
                    continue

            if channel is None or not isinstance(channel, discord.TextChannel):
                tables_to_archive.append(table_id)
                continue

            if channel.guild.id != guild_id:
                tables_to_archive.append(table_id)
                continue

            try:
                message = await channel.fetch_message(info["message_id"])
                embed = create_table_embed(
                    info,
                    table_id,
                    resolvable_ids=cached_resolvable_ids(channel.guild, info),
                )
                await message.edit(embed=embed, view=view)
            except discord.NotFound:
                logger.warning(
                    "Original message %s for table %s no longer exists; persistent controls remain registered.",
                    info.get("message_id"),
                    table_id,
                )
                continue
            except discord.Forbidden:
                logger.warning(
                    "Cannot reconcile original message %s for table %s due to missing permissions.",
                    info.get("message_id"),
                    table_id,
                )
                continue
            except discord.HTTPException as exc:
                logger.warning(
                    "Temporary Discord error reconciling original message %s for table %s: %s",
                    info.get("message_id"),
                    table_id,
                    exc,
                )
                continue

            try:
                _, updates = await asyncio.wait_for(
                    refresh_table_members(channel.guild, info),
                    timeout=10,
                )
                refreshed_table = apply_display_name_updates(table_id, updates) if updates else None
                if refreshed_table is not None:
                    refreshed_embed = create_table_embed(
                        refreshed_table,
                        table_id,
                        resolvable_ids=cached_resolvable_ids(channel.guild, refreshed_table),
                    )
                    await message.edit(embed=refreshed_embed, view=view)
            except asyncio.TimeoutError:
                logger.warning("Member refresh timed out for table %s during startup.", table_id)
            except OSError as exc:
                logger.error("Could not persist refreshed member names for table %s: %s", table_id, exc)
            except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
                logger.warning("Could not apply refreshed display for table %s: %s", table_id, exc)

        if tables_to_archive:
            try:
                archived = archive_tables(tables_to_archive, ArchiveReason.NO_ACCESS)
                logger.warning(
                    "Archived %s table(s) referencing invalid or missing guilds/channels: %s",
                    archived,
                    ", ".join(tables_to_archive),
                )
            except OSError as exc:
                logger.critical("Could not archive invalid startup records: %s", exc, exc_info=True)

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
