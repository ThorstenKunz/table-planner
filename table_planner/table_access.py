from __future__ import annotations

import re

import discord

from .types import TableData

_USER_REFERENCE_RE = re.compile(r"^<@!?(\d+)>$|^(\d+)$")


def get_gm_id(table_data: TableData) -> int:
    gm_id = table_data.get("gm_id")
    if isinstance(gm_id, int) and gm_id > 0:
        return gm_id
    return table_data["creator_id"]


def normalize_table_record(table_data: dict[str, object]) -> dict[str, object]:
    creator_id = table_data.get("creator_id")
    gm_id = table_data.get("gm_id")
    if not isinstance(creator_id, int) or creator_id <= 0:
        return table_data
    if not isinstance(gm_id, int) or gm_id <= 0:
        table_data["gm_id"] = creator_id
    return table_data


def is_table_owner(user_id: int, table_data: TableData) -> bool:
    return user_id == table_data["creator_id"] or user_id == get_gm_id(table_data)


def parse_user_reference(raw_value: str) -> int | None:
    match = _USER_REFERENCE_RE.fullmatch(raw_value.strip())
    if match is None:
        return None
    user_id = next(group for group in match.groups() if group is not None)
    return int(user_id)


async def get_table_channel(bot: discord.Client, channel_id: int) -> discord.TextChannel | None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return None
    if isinstance(channel, discord.TextChannel):
        return channel
    return None


async def resolve_guild_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return None


async def can_manage_table(bot: discord.Client, table_data: TableData, user_id: int) -> bool:
    if is_table_owner(user_id, table_data):
        return True

    channel = await get_table_channel(bot, table_data["channel_id"])
    if channel is None:
        return False

    member = await resolve_guild_member(channel.guild, user_id)
    if member is None:
        return False

    return channel.permissions_for(member).manage_messages


async def resolve_table_member(bot: discord.Client, table_data: TableData, raw_value: str) -> discord.Member | None:
    user_id = parse_user_reference(raw_value)
    if user_id is None:
        return None

    guild = bot.get_guild(table_data["guild_id"])
    if guild is None:
        return None

    return await resolve_guild_member(guild, user_id)