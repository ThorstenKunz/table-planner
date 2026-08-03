"""Persistence helpers for table planner."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, Tuple, TypeVar, cast

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

from .types import ArchiveReason, TableData, TablesDB
from .table_access import normalize_table_record

logger = logging.getLogger(__name__)

DATA_DIR = "data"
ACTIVE_DATA_FILE = os.path.join(DATA_DIR, "tables_active.json")
ARCHIVED_DATA_FILE = os.path.join(DATA_DIR, "tables_archived.json")

MutationResult = TypeVar("MutationResult")
_PROCESS_DATABASE_LOCK = threading.RLock()


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
        entry = normalize_table_record(entry)
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


@contextmanager
def _database_lock(exclusive: bool) -> Iterator[None]:
    """Serialize complete database operations within and across processes."""
    lock_target = f"{ACTIVE_DATA_FILE}.database"
    with _PROCESS_DATABASE_LOCK:
        with _locked_file(lock_target, exclusive=exclusive):
            yield


def _load_tables_unlocked() -> Tuple[TablesDB, TablesDB]:
    return _read_json(ACTIVE_DATA_FILE), _read_json(ARCHIVED_DATA_FILE)


def _save_tables_unlocked(active: TablesDB, archived: TablesDB) -> None:
    normalized_active: TablesDB = {}
    for key, value in active.items():
        entry = dict(value)
        entry = normalize_table_record(entry)
        entry["archive_reason"] = None
        normalized_active[key] = cast(TableData, entry)

    _write_json(ACTIVE_DATA_FILE, normalized_active)
    _write_json(ARCHIVED_DATA_FILE, archived)


def load_tables() -> Tuple[TablesDB, TablesDB]:
    """Loads active and archived tables from disk."""
    with _database_lock(exclusive=False):
        return _load_tables_unlocked()


def load_active_tables() -> TablesDB:
    return load_tables()[0]


def load_archived_tables() -> TablesDB:
    return load_tables()[1]


def save_tables(active: TablesDB, archived: TablesDB) -> None:
    """Persists active and archived tables to disk."""
    with _database_lock(exclusive=True):
        _save_tables_unlocked(active, archived)


def mutate_tables(
    mutation: Callable[[TablesDB, TablesDB], MutationResult],
) -> MutationResult:
    """Apply and persist one synchronous read-modify-write transaction.

    Mutations must not perform asynchronous or network work while the database
    lock is held. If the callback raises, no files are written.
    """
    with _database_lock(exclusive=True):
        active_tables, archived_tables = _load_tables_unlocked()
        result = mutation(active_tables, archived_tables)
        _save_tables_unlocked(active_tables, archived_tables)
        return result


def remove_tables_for_channel(channel_id: int) -> int:
    """Archive all tables associated with a specific channel as the bot was removed."""
    archived = _archive_matching(
        lambda info: info["channel_id"] == channel_id,
        ArchiveReason.KICK,
    )
    if archived:
        logger.info("Archived %s table(s) for channel %s.", archived, channel_id)
    else:
        logger.info("No tables to archive for channel %s.", channel_id)
    return archived


def remove_tables_for_guild(guild_id: int) -> int:
    """Archive all tables associated with a specific guild as the bot was removed."""
    archived = _archive_matching(
        lambda info: info["guild_id"] == guild_id,
        ArchiveReason.KICK,
    )
    if archived:
        logger.info("Archived %s table(s) for guild %s.", archived, guild_id)
    else:
        logger.info("No tables to archive for guild %s.", guild_id)
    return archived


def archive_tables(table_ids: Iterable[str], reason: ArchiveReason) -> int:
    """Move selected tables from active storage into the archive with a reason."""
    table_ids_to_archive = tuple(table_ids)

    def archive(active_tables: TablesDB, archived_tables: TablesDB) -> int:
        archived_count = 0
        for table_id in table_ids_to_archive:
            record = active_tables.pop(table_id, None)
            if record is None:
                continue
            record["archive_reason"] = reason
            archived_tables[table_id] = record
            archived_count += 1
        return archived_count

    archived_count = mutate_tables(archive)
    if archived_count:
        logger.info("Archived %s table(s) with reason %s.", archived_count, reason.value)

    return archived_count


def _archive_matching(
    predicate: Callable[[TableData], bool],
    reason: ArchiveReason,
) -> int:
    def archive(active_tables: TablesDB, archived_tables: TablesDB) -> int:
        matching_ids = [table_id for table_id, info in active_tables.items() if predicate(info)]
        for table_id in matching_ids:
            record = active_tables.pop(table_id)
            record["archive_reason"] = reason
            archived_tables[table_id] = record
        return len(matching_ids)

    return mutate_tables(archive)
