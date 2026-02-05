"""Shared utilities for command handlers."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict

import discord

from ..config import get_guild_command_rate_limit, get_user_command_rate_limit
from ..types import TableData

_user_rate_limits: dict[int, Deque[datetime]] = {}
_guild_rate_limits: dict[int, Deque[datetime]] = {}


def check_user_rate_limit(user_id: int, now: datetime) -> tuple[bool, int]:
    max_commands, window_seconds = get_user_command_rate_limit()
    window = timedelta(seconds=window_seconds)
    timestamps = _user_rate_limits.setdefault(user_id, deque())
    cutoff = now - window
    while timestamps and timestamps[0] < cutoff:
        timestamps.popleft()
    if len(timestamps) >= max_commands:
        oldest = timestamps[0]
        wait_seconds = max(0, int((oldest + window - now).total_seconds()))
        return False, wait_seconds
    timestamps.append(now)
    return True, 0


def check_guild_rate_limit(guild_id: int, now: datetime) -> tuple[bool, int]:
    max_commands, window_seconds = get_guild_command_rate_limit()
    window = timedelta(seconds=window_seconds)
    timestamps = _guild_rate_limits.setdefault(guild_id, deque())
    cutoff = now - window
    while timestamps and timestamps[0] < cutoff:
        timestamps.popleft()
    if len(timestamps) >= max_commands:
        oldest = timestamps[0]
        wait_seconds = max(0, int((oldest + window - now).total_seconds()))
        return False, wait_seconds
    timestamps.append(now)
    return True, 0


async def resolve_resolvable_ids(guild: discord.Guild | None, table_data: TableData) -> set[int]:
    if guild is None:
        return set()
    user_ids = {
        entry["id"]
        for bucket in (table_data.get("players", []), table_data.get("waitlist", []))
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


async def filter_tables_for_dm(
    interaction: discord.Interaction,
    active_tables: Dict[str, TableData],
) -> Dict[str, TableData]:
    filtered: dict[str, TableData] = {}
    client = interaction.client
    user = interaction.user
    for table_id, info in active_tables.items():
        guild = client.get_guild(info["guild_id"])
        if guild is None:
            continue
        member = guild.get_member(user.id)
        if member is None:
            try:
                member = await guild.fetch_member(user.id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                continue
        channel_obj = guild.get_channel(info["channel_id"])
        if not isinstance(channel_obj, discord.TextChannel):
            continue
        permissions = channel_obj.permissions_for(member)
        if not permissions.view_channel:
            continue
        filtered[table_id] = info
    return filtered


async def resolve_gm_name(
    bot: discord.Client,
    user_id: int,
    guild_id: int,
    gm_name_cache: dict[int, str],
) -> str:
    if user_id in gm_name_cache:
        return gm_name_cache[user_id]

    display = str(user_id)

    member = None
    if guild_id:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
    if member:
        display = member.display_name
    else:
        user_obj = bot.get_user(user_id)
        if not user_obj:
            try:
                user_obj = await bot.fetch_user(user_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                user_obj = None
        if user_obj:
            display = user_obj.display_name or user_obj.name

    gm_name_cache[user_id] = display
    return display


def format_cell(value: str, width: int) -> str:
    if len(value) <= width:
        return value.ljust(width)
    if width <= 3:
        return value[:width]
    return (value[: width - 3] + "...").ljust(width)
