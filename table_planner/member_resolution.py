"""Fast cached and best-effort Discord member resolution."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import discord

from .storage import mutate_tables
from .table_access import get_gm_id
from .types import TableData, TablesDB

DISPLAY_NAME_TTL = timedelta(hours=24)
MAX_CONCURRENT_MEMBER_FETCHES = 4


def _display_name_is_stale(entry: object, now: datetime) -> bool:
    if not isinstance(entry, dict) or not entry.get("display_name"):
        return True
    raw_updated_at = entry.get("display_name_updated_at")
    if not isinstance(raw_updated_at, str):
        return True
    try:
        updated_at = datetime.fromisoformat(raw_updated_at)
    except ValueError:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return now - updated_at.astimezone(timezone.utc) >= DISPLAY_NAME_TTL


async def refresh_table_members(
    guild: discord.Guild,
    table_data: TableData,
) -> tuple[set[int], dict[int, tuple[str, str]]]:
    """Resolve stale member names with bounded concurrency.

    Failures are deliberately ignored: the caller keeps the last known display
    name and can retry after the next cache interval or restart.
    """
    now = datetime.now(timezone.utc)
    refreshed_at = now.isoformat()
    entries = [
        entry
        for bucket in (table_data.get("players", []), table_data.get("waitlist", []))
        for entry in bucket
    ]
    gm_entry = {
        "id": get_gm_id(table_data),
        "display_name": table_data.get("gm_display_name"),
        "display_name_updated_at": table_data.get("gm_display_name_updated_at"),
    }
    entries.append(gm_entry)
    resolvable: set[int] = set()
    stale_ids = {entry["id"] for entry in entries if _display_name_is_stale(entry, now)}
    updates: dict[int, tuple[str, str]] = {}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_MEMBER_FETCHES)

    async def resolve(user_id: int) -> None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                async with semaphore:
                    member = await guild.fetch_member(user_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return
        resolvable.add(user_id)
        if user_id in stale_ids:
            updates[user_id] = (member.display_name, refreshed_at)

    await asyncio.gather(*(resolve(user_id) for user_id in stale_ids))
    return resolvable, updates


def apply_display_name_updates(
    table_id: str,
    updates: dict[int, tuple[str, str]],
) -> TableData | None:
    """Merge refreshed names into the latest table revision transactionally."""
    if not updates:
        return None

    def apply(active_tables: TablesDB, _archived_tables: TablesDB) -> TableData | None:
        table_data = active_tables.get(table_id)
        if table_data is None:
            return None
        gm_update = updates.get(get_gm_id(table_data))
        if gm_update is not None:
            table_data["gm_display_name"], table_data["gm_display_name_updated_at"] = gm_update
        for bucket in (table_data.get("players", []), table_data.get("waitlist", [])):
            for entry in bucket:
                update = updates.get(entry["id"])
                if update is None:
                    continue
                entry["display_name"], entry["display_name_updated_at"] = update
        return table_data

    return mutate_tables(apply)
