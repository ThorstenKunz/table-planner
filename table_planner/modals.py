"""Modal definitions for creating tables."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import discord

from .discord_utils import safe_followup_send
from .storage import load_tables, save_tables
from .types import PlayerEntry, TableData
from .ui import create_table_embed
from .views import SignupView

logger = logging.getLogger(__name__)


class NewTableModal(discord.ui.Modal, title="Create a New Game Table"):
    system = discord.ui.TextInput(
        label="System",
        placeholder="e.g., Warhammer 40k, D&D 5e, Call of Cthulhu, Pathfinder"
    )
    schedule = discord.ui.TextInput(
        label="Schedule",
        placeholder="e.g., Every Friday at 20:00 CET"
    )
    max_players = discord.ui.TextInput(
        label="Max Number of Players",
        placeholder="e.g., 5"
    )
    infos = discord.ui.TextInput(
        label="Infos",
        style=discord.TextStyle.long,
        placeholder="A short description of the adventure, theme, and tone.",
        max_length=1000
    )

    def __init__(self, bot: discord.Client) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        await interaction.response.defer(ephemeral=True, thinking=True)

        system_value = self.system.value.strip()
        schedule_value = self.schedule.value.strip()
        infos_value = self.infos.value.strip()

        try:
            max_players_int = int(self.max_players.value.strip())
            if max_players_int <= 0:
                raise ValueError("Player cap must be positive.")
            if max_players_int > 20:
                raise ValueError("Player cap too large.")
        except ValueError:
            logger.warning(
                "User %s (%s) entered invalid max_players value: %s",
                user,
                user.id,
                self.max_players.value,
            )
            await safe_followup_send(
                interaction,
                "The 'Max Number of Players' must be a number between 1 and 20.",
                ephemeral=True,
            )
            return

        if not system_value:
            await safe_followup_send(interaction, "System cannot be empty.", ephemeral=True)
            return

        if not schedule_value:
            await safe_followup_send(interaction, "Schedule cannot be empty.", ephemeral=True)
            return

        if not infos_value:
            await safe_followup_send(interaction, "Infos cannot be empty.", ephemeral=True)
            return

        if len(system_value) > 100:
            await safe_followup_send(interaction, "System is too long (max 100 characters).", ephemeral=True)
            return

        if len(schedule_value) > 120:
            await safe_followup_send(interaction, "Schedule is too long (max 120 characters).", ephemeral=True)
            return

        if len(infos_value) > 1024:
            await safe_followup_send(interaction, "Infos are too long (max 1024 characters).", ephemeral=True)
            return

        logger.info("Modal for /create-table submitted by %s (%s).", user, user.id)

        table_id = str(uuid.uuid4())
        active_tables, archived_tables = load_tables()

        new_table: TableData = {
            "system": system_value,
            "infos": infos_value,
            "schedule": schedule_value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "max_players": max_players_int,
            "players": [],
            "waitlist": [],
            "creator_id": user.id,
            "message_id": 0,
            "channel_id": 0,
            "guild_id": interaction.guild_id or 0,
            "archive_reason": None,
            "archived_at": None,
            "archived_by": None,
        }

        embed = create_table_embed(new_table, table_id)
        view = SignupView(table_id, max_players_int)

        if not isinstance(interaction.channel, discord.TextChannel):
            logger.error(
                "create-table command used in non-text channel by %s (%s).",
                user,
                user.id,
            )
            await interaction.followup.send(
                "This command can only be used in a server's text channel.",
                ephemeral=True,
            )
            return

        try:
            message = await interaction.channel.send(embed=embed, view=view)
        except discord.Forbidden:
            logger.warning(
                "Missing permission to send table message in channel %s (%s).",
                getattr(interaction.channel, "name", "unknown"),
                getattr(interaction.channel, "id", "unknown"),
            )
            await safe_followup_send(
                interaction,
                "I don't have permission to post in this channel. Please check my permissions.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            logger.error(
                "Failed to send table message in channel %s (%s): %s",
                getattr(interaction.channel, "name", "unknown"),
                getattr(interaction.channel, "id", "unknown"),
                exc,
            )
            await safe_followup_send(
                interaction,
                "I couldn't post the table message due to an error. Please try again later.",
                ephemeral=True,
            )
            return

        new_table["message_id"] = message.id
        new_table["channel_id"] = message.channel.id

        active_tables[table_id] = new_table
        save_tables(active_tables, archived_tables)
        logger.info("New table %s created by %s (%s).", table_id, user, user.id)

        await safe_followup_send(
            interaction,
            f"Your table '{self.infos.value[:50]}...' has been created in this channel!",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error("Error in NewTableModal: %s", error, exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await safe_followup_send(interaction, "An unexpected error occurred. Please try again later.", ephemeral=True)


class EditTableModal(discord.ui.Modal):
    def __init__(self, bot: discord.Client, table_id: str, table_data: TableData) -> None:
        super().__init__(title="Edit Game Table")
        self.bot = bot
        self.table_id = table_id
        self.original_max_players = table_data["max_players"]

        self.system = discord.ui.TextInput(
            label="System",
            default=table_data["system"],
            max_length=100
        )
        self.schedule = discord.ui.TextInput(
            label="Schedule",
            default=table_data["schedule"],
            max_length=120
        )
        self.infos = discord.ui.TextInput(
            label="Infos",
            style=discord.TextStyle.long,
            default=table_data["infos"],
            max_length=1000
        )
        self.max_players = discord.ui.TextInput(
            label="Max Number of Players",
            default=str(table_data["max_players"])
        )

        for component in (self.system, self.schedule, self.max_players, self.infos):
            self.add_item(component)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        await interaction.response.defer(ephemeral=True, thinking=True)

        system_value = self.system.value.strip()
        schedule_value = self.schedule.value.strip()
        infos_value = self.infos.value.strip()

        try:
            max_players_int = int(self.max_players.value.strip())
            if max_players_int <= 0:
                raise ValueError("Player cap must be positive.")
            if max_players_int > 20:
                raise ValueError("Player cap too large.")
        except ValueError:
            logger.warning(
                "User %s (%s) entered invalid max_players value while editing table %s: %s",
                user,
                user.id,
                self.table_id,
                self.max_players.value,
            )
            await safe_followup_send(
                interaction,
                "The 'Max Number of Players' must be a number between 1 and 20.",
                ephemeral=True,
            )
            return

        if not system_value:
            await safe_followup_send(interaction, "System cannot be empty.", ephemeral=True)
            return

        if not schedule_value:
            await safe_followup_send(interaction, "Schedule cannot be empty.", ephemeral=True)
            return

        if not infos_value:
            await safe_followup_send(interaction, "Infos cannot be empty.", ephemeral=True)
            return

        if len(system_value) > 100:
            await safe_followup_send(interaction, "System is too long (max 100 characters).", ephemeral=True)
            return

        if len(schedule_value) > 120:
            await safe_followup_send(interaction, "Schedule is too long (max 120 characters).", ephemeral=True)
            return

        if len(infos_value) > 1024:
            await safe_followup_send(interaction, "Infos are too long (max 1024 characters).", ephemeral=True)
            return

        logger.info("Modal for /edit-table submitted by %s (%s) for %s.", user, user.id, self.table_id)

        active_tables, archived_tables = load_tables()
        table_data = active_tables.get(self.table_id)

        if not table_data:
            await safe_followup_send(interaction, "This table no longer exists or was archived.", ephemeral=True)
            return

        table_data["system"] = system_value
        table_data["schedule"] = schedule_value
        table_data["infos"] = infos_value
        table_data["max_players"] = max_players_int

        moved_to_waitlist: list[PlayerEntry] = []
        players = list(table_data["players"])
        waitlist = list(table_data.get("waitlist", []))
        if len(players) > max_players_int:
            while len(players) > max_players_int:
                entry_to_move = players.pop()
                moved_to_waitlist.append(entry_to_move)

            table_data["players"] = players
            combined_waitlist = waitlist + moved_to_waitlist
            combined_waitlist.sort(key=lambda item: item["joined_at"])
            table_data["waitlist"] = combined_waitlist

        active_tables[self.table_id] = table_data
        save_tables(active_tables, archived_tables)

        embed = create_table_embed(table_data, self.table_id)
        view = SignupView(self.table_id, table_data["max_players"])

        channel = self.bot.get_channel(table_data["channel_id"])
        message_updated = False
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(table_data["message_id"])
                await message.edit(embed=embed, view=view)
                message_updated = True
            except discord.Forbidden:
                logger.warning(
                    "Missing permission to edit table message %s in channel %s.",
                    table_data.get("message_id"),
                    table_data["channel_id"],
                )
            except discord.NotFound:
                logger.warning(
                    "Table message %s for table %s no longer exists.",
                    table_data.get("message_id"),
                    self.table_id,
                )
            except discord.HTTPException as exc:
                logger.error(
                    "Failed to update table message %s in channel %s: %s",
                    self.table_id,
                    table_data["channel_id"],
                    exc,
                )

            if moved_to_waitlist:
                waitlist_mentions = ", ".join(f"<@{entry['id']}>" for entry in moved_to_waitlist)
                try:
                    await channel.send(
                        f"The table '{table_data['infos'][:50]}...' was updated and the following players were moved to the waitlist due to the new seat limit: {waitlist_mentions}"
                    )
                except discord.Forbidden:
                    logger.warning(
                        "Missing permission to notify channel %s about waitlist changes for table %s.",
                        table_data["channel_id"],
                        self.table_id,
                    )
                except discord.HTTPException as exc:
                    logger.error(
                        "Failed to notify channel %s about removed players for table %s: %s",
                        table_data["channel_id"],
                        self.table_id,
                        exc,
                    )
                for entry in moved_to_waitlist:
                    try:
                        user_obj = self.bot.get_user(entry["id"]) or await self.bot.fetch_user(entry["id"])
                        if user_obj:
                            await user_obj.send(
                                f"The table '{table_data['infos'][:50]}...' was updated and you were moved to the waitlist due to the reduced seat limit."
                            )
                    except discord.Forbidden:
                        logger.warning("Missing permission to DM demoted user %s.", entry["id"])
                    except discord.HTTPException as exc:
                        logger.error("Failed to DM demoted user %s: %s", entry["id"], exc)

        if not message_updated:
            logger.warning("Could not update message for table %s. Check channel and message IDs.", self.table_id)

        await safe_followup_send(interaction, "Table has been updated successfully.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error("Error in EditTableModal for table %s: %s", self.table_id, error, exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await safe_followup_send(interaction, "An unexpected error occurred while editing the table.", ephemeral=True)
