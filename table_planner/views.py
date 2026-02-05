"""discord.ui.View implementations for table planner."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord

from .discord_utils import safe_followup_send, safe_response_send
from .storage import load_tables, save_tables
from .types import ArchiveReason, PlayerEntry, TableData
from .ui import create_table_embed

logger = logging.getLogger(__name__)


def _truncate_label(value: str, max_length: int = 100) -> str:
    trimmed = value.strip()
    if len(trimmed) <= max_length:
        return trimmed or "(untitled)"
    if max_length <= 3:
        return trimmed[:max_length]
    return trimmed[: max_length - 3] + "..."


class SignupView(discord.ui.View):
    def __init__(self, table_id: str, max_players: int) -> None:
        super().__init__(timeout=None)
        self.table_id: str = table_id
        self.max_players: int = max_players

        join_button = discord.ui.Button(
            label="Sign Up",
            style=discord.ButtonStyle.green,
            custom_id=f"join_{table_id}",
            emoji="⚔️"
        )
        join_button.callback = self.join_callback
        self.add_item(join_button)
        self.join_btn = join_button

        leave_button = discord.ui.Button(
            label="Leave",
            style=discord.ButtonStyle.red,
            custom_id=f"leave_{table_id}",
            emoji="🏳️"
        )
        leave_button.callback = self.leave_callback
        self.add_item(leave_button)
        self.leave_btn = leave_button

    async def update_message(self, interaction: discord.Interaction, data: TableData) -> None:
        """Rebuilds the embed after signup or leave."""
        if interaction.message:
            await self._populate_display_names(interaction, data)
            resolvable_ids = await self._get_resolvable_ids(interaction, data)
            new_embed = create_table_embed(data, self.table_id, resolvable_ids=resolvable_ids)

            players = data["players"]
            is_full = len(players) >= self.max_players
            self.join_btn.disabled = False
            self.join_btn.label = "Join Waitlist" if is_full else "Sign Up"
            self.join_btn.style = discord.ButtonStyle.grey if is_full else discord.ButtonStyle.green

            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=new_embed, view=self)
                else:
                    await interaction.message.edit(embed=new_embed, view=self)
            except discord.Forbidden:
                logger.warning(
                    "Missing permission to edit table message %s for table %s.",
                    getattr(interaction.message, "id", "unknown"),
                    self.table_id,
                )
            except discord.NotFound:
                logger.warning(
                    "Table message %s for table %s no longer exists.",
                    getattr(interaction.message, "id", "unknown"),
                    self.table_id,
                )
            except discord.HTTPException as exc:
                logger.error(
                    "Failed to edit table message %s for table %s: %s",
                    getattr(interaction.message, "id", "unknown"),
                    self.table_id,
                    exc,
                )

        await self._update_origin_message(interaction, data)

    async def _update_origin_message(self, interaction: discord.Interaction, data: TableData) -> None:
        channel_id = data.get("channel_id")
        message_id = data.get("message_id")
        if not channel_id or not message_id:
            return

        origin_message_id = getattr(interaction.message, "id", None)
        if origin_message_id == message_id:
            return

        channel = interaction.client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                channel = None

        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(message_id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            return

        await self._populate_display_names(interaction, data)
        resolvable_ids = await self._get_resolvable_ids(interaction, data)
        new_embed = create_table_embed(data, self.table_id, resolvable_ids=resolvable_ids)
        try:
            await message.edit(embed=new_embed, view=self)
        except discord.Forbidden:
            logger.warning(
                "Missing permission to edit origin table message %s for table %s.",
                message_id,
                self.table_id,
            )
        except discord.NotFound:
            logger.warning(
                "Origin table message %s for table %s no longer exists.",
                message_id,
                self.table_id,
            )
        except discord.HTTPException as exc:
            logger.error(
                "Failed to edit origin table message %s for table %s: %s",
                message_id,
                self.table_id,
                exc,
            )

    async def _resolve_display_name(self, interaction: discord.Interaction, user_id: int) -> Optional[str]:
        if interaction.guild is not None:
            member = interaction.guild.get_member(user_id)
            if member is not None:
                return member.display_name
            try:
                member = await interaction.guild.fetch_member(user_id)
                return member.display_name
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                pass

        user_obj = interaction.client.get_user(user_id)
        if user_obj is None:
            try:
                user_obj = await interaction.client.fetch_user(user_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return None
        return getattr(user_obj, "display_name", None) or user_obj.name

    async def _populate_display_names(self, interaction: discord.Interaction, data: TableData) -> bool:
        updated = False
        for bucket in (data.get("players", []), data.get("waitlist", [])):
            for entry in bucket:
                if entry.get("display_name"):
                    continue
                display_name = await self._resolve_display_name(interaction, entry["id"])
                if display_name:
                    entry["display_name"] = display_name
                    updated = True
        return updated

    async def _get_resolvable_ids(self, interaction: discord.Interaction, data: TableData) -> set[int]:
        guild = interaction.guild
        if guild is None:
            return set()

        user_ids = {
            entry["id"]
            for bucket in (data.get("players", []), data.get("waitlist", []))
            for entry in bucket
        }
        resolvable: set[int] = set()
        for user_id in user_ids:
            member = guild.get_member(user_id)
            if member is not None:
                resolvable.add(user_id)
                continue
            try:
                await guild.fetch_member(user_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                continue
            resolvable.add(user_id)

        return resolvable

    async def join_callback(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("User %s (%s) trying to join table %s.", user, user.id, self.table_id)
        active_tables, archived_tables = load_tables()
        table_data = active_tables.get(self.table_id)

        if not table_data:
            logger.warning("User %s (%s) tried to join non-existent table %s.", user, user.id, self.table_id)
            await safe_response_send(interaction, "This table no longer exists.", ephemeral=True)
            return

        players = table_data["players"]
        waitlist = table_data.setdefault("waitlist", [])

        if any(entry["id"] == user.id for entry in players):
            logger.info("User %s (%s) already signed up for table %s.", user, user.id, self.table_id)
            await safe_response_send(interaction, "You are already signed up!", ephemeral=True)
            return

        if any(entry["id"] == user.id for entry in waitlist):
            logger.info("User %s (%s) already on waitlist for table %s.", user, user.id, self.table_id)
            await safe_response_send(interaction, "You are already on the waitlist!", ephemeral=True)
            return

        if len(players) >= table_data["max_players"]:
            logger.info("User %s (%s) could not join table %s: full.", user, user.id, self.table_id)
            waitlist.append({
                "id": user.id,
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "display_name": getattr(user, "display_name", user.name),
            })
            await self._populate_display_names(interaction, table_data)
            save_tables(active_tables, archived_tables)
            await safe_response_send(
                interaction,
                "The group is full, but you have been added to the waitlist.",
                ephemeral=True,
            )
            await self.update_message(interaction, table_data)
            try:
                await user.send(
                    f"You joined the table '{table_data['infos'][:50]}...', but all seats were taken. You are now on the waitlist."
                )
            except discord.Forbidden:
                logger.warning("Missing permission to DM user %s about waitlist join.", user.id)
            except discord.HTTPException as exc:
                logger.error("Failed to DM user %s about waitlist join: %s", user.id, exc)
            return

        players.append({
            "id": user.id,
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "display_name": getattr(user, "display_name", user.name),
        })
        await self._populate_display_names(interaction, table_data)
        save_tables(active_tables, archived_tables)
        logger.info("User %s (%s) joined table %s.", user, user.id, self.table_id)
        await self.update_message(interaction, table_data)
        try:
            await user.send(
                f"You successfully joined the table '{table_data['infos'][:50]}...'. See you at the game!"
            )
        except discord.Forbidden:
            logger.warning("Missing permission to DM user %s about signup confirmation.", user.id)
        except discord.HTTPException as exc:
            logger.error("Failed to DM user %s about signup confirmation: %s", user.id, exc)

    async def leave_callback(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        logger.info("User %s (%s) trying to leave table %s.", user, user.id, self.table_id)
        active_tables, archived_tables = load_tables()
        table_data = active_tables.get(self.table_id)

        if not table_data:
            logger.warning("User %s (%s) not signed up for table %s.", user, user.id, self.table_id)
            await safe_response_send(interaction, "You weren't signed up in the first place.", ephemeral=True)
            return

        players = table_data["players"]
        waitlist = table_data.setdefault("waitlist", [])

        if any(entry["id"] == user.id for entry in players):
            table_data["players"] = [entry for entry in players if entry["id"] != user.id]
            promoted: Optional[PlayerEntry] = None
            if waitlist:
                promoted = waitlist.pop(0)
                table_data["players"].append(promoted)
            await self._populate_display_names(interaction, table_data)
            save_tables(active_tables, archived_tables)
            logger.info("User %s (%s) left table %s.", user, user.id, self.table_id)
            await self.update_message(interaction, table_data)
            if promoted:
                dest_channel = interaction.channel
                if isinstance(dest_channel, discord.TextChannel):
                    try:
                        await dest_channel.send(
                            f"<@{promoted['id']}> has been moved from the waitlist into the table '{table_data['infos'][:50]}...'."
                        )
                    except discord.Forbidden:
                        logger.warning(
                            "Missing permission to notify channel %s about waitlist promotion for table %s.",
                            dest_channel.id,
                            self.table_id,
                        )
                    except discord.HTTPException as exc:
                        logger.error(
                            "Failed to notify channel %s about waitlist promotion for table %s: %s",
                            dest_channel.id,
                            self.table_id,
                            exc,
                        )
                try:
                    promoted_user = interaction.client.get_user(promoted["id"]) or await interaction.client.fetch_user(promoted["id"])
                    if promoted_user:
                        await promoted_user.send(
                            f"Good news! A seat opened up and you have been moved from the waitlist into the table '{table_data['infos'][:50]}...'."
                        )
                except discord.Forbidden:
                    logger.warning("Missing permission to DM promoted user %s.", promoted["id"])
                except discord.HTTPException as exc:
                    logger.error("Failed to DM promoted user %s: %s", promoted["id"], exc)
            await safe_followup_send(interaction, "You have left the table.", ephemeral=True)
            try:
                await user.send(
                    f"You left the table '{table_data['infos'][:50]}...'."
                )
            except discord.Forbidden:
                logger.warning("Missing permission to DM user %s about leaving table.", user.id)
            except discord.HTTPException as exc:
                logger.error("Failed to DM user %s about leaving table: %s", user.id, exc)
            return

        if any(entry["id"] == user.id for entry in waitlist):
            table_data["waitlist"] = [entry for entry in waitlist if entry["id"] != user.id]
            await self._populate_display_names(interaction, table_data)
            save_tables(active_tables, archived_tables)
            logger.info("User %s (%s) left waitlist for table %s.", user, user.id, self.table_id)
            await safe_response_send(interaction, "You have been removed from the waitlist.", ephemeral=True)
            await self.update_message(interaction, table_data)
            try:
                await user.send(
                    f"You have been removed from the waitlist for '{table_data['infos'][:50]}...'."
                )
            except discord.Forbidden:
                logger.warning("Missing permission to DM user %s about waitlist removal.", user.id)
            except discord.HTTPException as exc:
                logger.error("Failed to DM user %s about waitlist removal: %s", user.id, exc)
            return

        logger.warning("User %s (%s) not signed up or waiting for table %s.", user, user.id, self.table_id)
        await safe_response_send(interaction, "You weren't signed up in the first place.", ephemeral=True)


class ArchiveView(discord.ui.View):
    def __init__(self, bot: discord.Client, tables: Dict[str, TableData], user_id: int) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id

        options = [
            discord.SelectOption(
                label=_truncate_label(f"{info['infos']} ({table_id[-4:]})"),
                description=f"System: {info['system']}",
                value=table_id,
            )
            for table_id, info in tables.items()
        ]

        if not options:
            options.append(discord.SelectOption(label="You have no active tables to archive.", value="no_tables"))

        select_menu = discord.ui.Select(placeholder="Select a table to archive...", options=options)
        select_menu.callback = self.select_callback
        self.add_item(select_menu)
        self.select_menu = select_menu

    async def select_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await safe_response_send(interaction, "This is not for you!", ephemeral=True)
            return

        payload = interaction.data
        values: Optional[List[Any]] = None
        if isinstance(payload, dict):
            raw_values = payload.get('values')
            if isinstance(raw_values, list):
                values = raw_values

        if not values:
            await safe_response_send(interaction, "No selection detected.", ephemeral=True)
            return

        table_id = str(values[0])
        if table_id == "no_tables":
            await interaction.response.edit_message(content="No action taken.", view=None)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        active_tables, archived_tables = load_tables()
        table_data = active_tables.get(table_id)

        if not table_data:
            logger.error(
                "Archive attempt for table %s failed: table missing.",
                table_id,
            )
            await safe_followup_send(interaction, "This table cannot be archived.", ephemeral=True)
            return

        reason = ArchiveReason.OWNER
        if interaction.user.id != table_data["creator_id"]:
            channel = self.bot.get_channel(table_data["channel_id"])
            has_permission = False
            if isinstance(channel, discord.TextChannel):
                member = channel.guild.get_member(interaction.user.id)
                if member is not None:
                    permissions = channel.permissions_for(member)
                    has_permission = permissions.manage_messages
            if not has_permission:
                logger.warning(
                    "User %s (%s) lacks permission to archive table %s.",
                    interaction.user,
                    interaction.user.id,
                    table_id,
                )
                await safe_followup_send(interaction, "You are not allowed to archive this table.", ephemeral=True)
                return
            reason = ArchiveReason.MOD

        table_data["archive_reason"] = reason
        active_tables.pop(table_id, None)
        archived_tables[table_id] = table_data
        save_tables(active_tables, archived_tables)
        logger.info("Table %s archived by user %s.", table_id, self.user_id)

        try:
            channel = self.bot.get_channel(table_data["channel_id"])
            if isinstance(channel, discord.TextChannel):
                message = await channel.fetch_message(table_data["message_id"])
                if message and message.embeds:
                    embed = message.embeds[0]
                    embed.title = f"[ARCHIVED] {embed.title}"
                    embed.color = discord.Color.greyple()
                    await message.edit(embed=embed, view=None)
        except discord.NotFound:
            logger.warning(
                "Archived table %s message %s no longer exists.",
                table_id,
                table_data.get("message_id"),
            )
        except Exception as exc:
            logger.error("Error editing message for archived table %s: %s", table_id, exc, exc_info=True)

        await safe_followup_send(
            interaction,
            f"Table '{table_data['infos'][:50]}...' has been archived.",
            ephemeral=True,
        )
        await interaction.edit_original_response(content="The selected table has been archived.", view=None)


class EditTableView(discord.ui.View):
    def __init__(self, bot: discord.Client, tables: Dict[str, TableData], user_id: int) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.tables = tables

        options = [
            discord.SelectOption(
                label=_truncate_label(f"{info['infos']} ({table_id[-4:]})"),
                description=f"System: {info['system']}",
                value=table_id,
            )
            for table_id, info in tables.items()
        ]

        if not options:
            options.append(discord.SelectOption(label="You have no tables to edit.", value="no_tables"))

        select_menu = discord.ui.Select(placeholder="Select a table to edit...", options=options)
        select_menu.callback = self.select_callback
        self.add_item(select_menu)
        self.select_menu = select_menu

    async def select_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await safe_response_send(interaction, "This is not for you!", ephemeral=True)
            return

        payload = interaction.data
        values: Optional[List[Any]] = None
        if isinstance(payload, dict):
            raw_values = payload.get('values')
            if isinstance(raw_values, list):
                values = raw_values

        if not values:
            await safe_response_send(interaction, "No selection detected.", ephemeral=True)
            return

        table_id = str(values[0])
        if table_id == "no_tables":
            await interaction.response.edit_message(content="No action taken.", view=None)
            return

        active_tables = load_tables()[0]
        table_data = active_tables.get(table_id)

        if not table_data:
            await safe_response_send(interaction, "This table can no longer be edited.", ephemeral=True)
            return

        from .modals import EditTableModal  # Local import to avoid circular dependency

        modal = EditTableModal(self.bot, table_id, table_data)
        await interaction.response.send_modal(modal)
