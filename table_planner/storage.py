"""Persistence helpers for table planner."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Tuple, cast

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

from .types import ArchiveReason, TableData, TablesDB

logger = logging.getLogger(__name__)

DATA_DIR = "data"
ACTIVE_DATA_FILE = os.path.join(DATA_DIR, "tables_active.json")
ARCHIVED_DATA_FILE = os.path.join(DATA_DIR, "tables_archived.json")


@contextmanager
def _locked_file(path: str, exclusive: bool) -> Iterator[None]:
    lock_path = f"{path}.lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    with open(lock_path, "a", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_handle.fileno(), lock_type)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _read_json(path: str) -> TablesDB:
    if not os.path.exists(path):
        return {}

    with _locked_file(path, exclusive=False):
        try:
            with open(path, "r", encoding="utf-8") as source:
                raw = json.load(source)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not decode JSON from %s. Returning empty data.", path)
            return {}

    if not isinstance(raw, dict):
        logger.warning("Data in %s is not a dictionary. Returning empty data.", path)
        return {}

    normalized: TablesDB = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        entry: dict[str, Any] = dict(value)
        reason = entry["archive_reason"]
        entry["archive_reason"] = ArchiveReason(reason) if reason is not None else None
        normalized[key] = cast(TableData, entry)

    return normalized


def _write_json(path: str, data: TablesDB) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    serializable: dict[str, Any] = {}
    for key, value in data.items():
        entry = dict(value)
        reason = entry.get("archive_reason")
        if isinstance(reason, ArchiveReason):
            entry["archive_reason"] = reason.value
        serializable[key] = entry

    with _locked_file(path, exclusive=True):
        fd, temp_path = tempfile.mkstemp(prefix=".tables_", suffix=".json", dir=directory or ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                json.dump(serializable, target, indent=4)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.debug("Failed to remove temp file %s", temp_path)


def load_tables() -> Tuple[TablesDB, TablesDB]:
    """Loads active and archived tables from disk."""
    return _read_json(ACTIVE_DATA_FILE), _read_json(ARCHIVED_DATA_FILE)


def load_active_tables() -> TablesDB:
    return load_tables()[0]


def load_archived_tables() -> TablesDB:
    return load_tables()[1]


def save_tables(active: TablesDB, archived: TablesDB) -> None:
    """Persists active and archived tables to disk."""
    normalized_active: TablesDB = {}
    for key, value in active.items():
        entry = dict(value)
        entry["archive_reason"] = None
        normalized_active[key] = cast(TableData, entry)

    _write_json(ACTIVE_DATA_FILE, normalized_active)
    _write_json(ARCHIVED_DATA_FILE, archived)


def remove_tables_for_channel(channel_id: int) -> int:
    """Archive all tables associated with a specific channel as the bot was removed."""
    active_tables, _ = load_tables()
    table_ids = [table_id for table_id, info in active_tables.items() if info["channel_id"] == channel_id]
    archived = archive_tables(table_ids, ArchiveReason.KICK)
    if archived:
        logger.info("Archived %s table(s) for channel %s.", archived, channel_id)
    else:
        logger.info("No tables to archive for channel %s.", channel_id)
    return archived


def remove_tables_for_guild(guild_id: int) -> int:
    """Archive all tables associated with a specific guild as the bot was removed."""
    active_tables, _ = load_tables()
    table_ids = [table_id for table_id, info in active_tables.items() if info["guild_id"] == guild_id]
    archived = archive_tables(table_ids, ArchiveReason.KICK)
    if archived:
        logger.info("Archived %s table(s) for guild %s.", archived, guild_id)
    else:
        logger.info("No tables to archive for guild %s.", guild_id)
    return archived


def archive_tables(table_ids: Iterable[str], reason: ArchiveReason) -> int:
    """Move selected tables from active storage into the archive with a reason."""
    active_tables, archived_tables = load_tables()
    archived_count = 0

    for table_id in list(table_ids):
        record = active_tables.pop(table_id, None)
        if record is None:
            continue
        record["archive_reason"] = reason
        archived_tables[table_id] = record
        archived_count += 1

    if archived_count:
        save_tables(active_tables, archived_tables)
        logger.info("Archived %s table(s) with reason %s.", archived_count, reason.value)

    return archived_count
