from pathlib import Path

from table_planner import storage
from table_planner.types import ArchiveReason, TableData


def _sample_table() -> TableData:
    return {
        "system": "Test System",
        "infos": "Test",
        "schedule": "Soon",
        "created_at": "2025-01-01T00:00:00Z",
        "max_players": 4,
        "players": [],
        "waitlist": [],
        "creator_id": 123,
        "message_id": 456,
        "channel_id": 789,
        "guild_id": 101112,
        "archive_reason": None,
        "archived_at": None,
        "archived_by": None,
    }


def test_save_and_load_tables(tmp_path: Path, monkeypatch) -> None:
    active_path = tmp_path / "active.json"
    archived_path = tmp_path / "archived.json"

    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(active_path))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(archived_path))

    active: dict[str, TableData] = {"table-1": _sample_table()}
    archived_entry = _sample_table()
    archived_entry["archive_reason"] = ArchiveReason.OWNER
    archived: dict[str, TableData] = {"table-2": archived_entry}

    storage.save_tables(active, archived)

    loaded_active, loaded_archived = storage.load_tables()
    assert loaded_active["table-1"]["system"] == "Test System"
    assert loaded_archived["table-2"]["archive_reason"] == ArchiveReason.OWNER


def test_archive_tables_moves_records(tmp_path: Path, monkeypatch) -> None:
    active_path = tmp_path / "active.json"
    archived_path = tmp_path / "archived.json"

    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(active_path))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(archived_path))

    active = {"table-1": _sample_table()}
    storage.save_tables(active, {})

    archived_count = storage.archive_tables(["table-1"], ArchiveReason.KICK)
    assert archived_count == 1

    loaded_active, loaded_archived = storage.load_tables()
    assert "table-1" not in loaded_active
    assert loaded_archived["table-1"]["archive_reason"] == ArchiveReason.KICK
