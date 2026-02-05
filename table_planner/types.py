"""Type definitions for table planner."""

from enum import Enum
from typing import Dict, List, NotRequired, TypedDict


class ArchiveReason(str, Enum):
    MOD = "MOD"
    OWNER = "OWNER"
    NO_ACCESS = "NO_ACCESS"
    KICK = "KICK"


class PlayerEntry(TypedDict):
    id: int
    joined_at: str
    display_name: NotRequired[str]


class TableData(TypedDict):
    system: str
    infos: str
    schedule: str
    created_at: str | None
    max_players: int
    players: List[PlayerEntry]
    waitlist: List[PlayerEntry]
    creator_id: int
    message_id: int
    channel_id: int
    guild_id: int
    archive_reason: ArchiveReason | None
    archived_at: str | None
    archived_by: int | None


TablesDB = Dict[str, TableData]
