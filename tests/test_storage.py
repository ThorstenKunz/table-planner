from concurrent.futures import ThreadPoolExecutor
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
        "gm_id": 123,
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
    assert loaded_active["table-1"].get("gm_id") == 123
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


def test_load_tables_falls_back_to_creator_when_gm_missing(tmp_path: Path, monkeypatch) -> None:
    active_path = tmp_path / "active.json"
    archived_path = tmp_path / "archived.json"

    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(active_path))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(archived_path))

    active_path.write_text(
        """
{
    "table-1": {
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
        "archive_reason": null,
        "archived_at": null,
        "archived_by": null
    }
}
""".strip(),
        encoding="utf-8",
    )
    archived_path.write_text("{}", encoding="utf-8")

    loaded_active, _ = storage.load_tables()

    assert loaded_active["table-1"].get("gm_id") == 123


def test_load_tables_falls_back_to_creator_when_gm_unset(tmp_path: Path, monkeypatch) -> None:
    active_path = tmp_path / "active.json"
    archived_path = tmp_path / "archived.json"

    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(active_path))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(archived_path))

    active_path.write_text(
        """
{
    "table-1": {
        "system": "Test System",
        "infos": "Test",
        "schedule": "Soon",
        "created_at": "2025-01-01T00:00:00Z",
        "max_players": 4,
        "players": [],
        "waitlist": [],
        "creator_id": 123,
        "gm_id": 0,
        "message_id": 456,
        "channel_id": 789,
        "guild_id": 101112,
        "archive_reason": null,
        "archived_at": null,
        "archived_by": null
    }
}
""".strip(),
        encoding="utf-8",
    )
    archived_path.write_text("{}", encoding="utf-8")

    loaded_active, _ = storage.load_tables()

    assert loaded_active["table-1"].get("gm_id") == 123


def test_mutate_tables_preserves_concurrent_updates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(tmp_path / "active.json"))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(tmp_path / "archived.json"))
    storage.save_tables({"table-1": _sample_table()}, {})

    def append_player(user_id: int) -> None:
        def mutation(active, _archived) -> None:
            active["table-1"]["players"].append(
                {"id": user_id, "joined_at": f"2026-01-01T00:00:{user_id:02d}+00:00"}
            )

        storage.mutate_tables(mutation)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_player, range(20)))

    active, _ = storage.load_tables()
    assert {entry["id"] for entry in active["table-1"]["players"]} == set(range(20))


def test_mutate_tables_does_not_write_when_mutation_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "ACTIVE_DATA_FILE", str(tmp_path / "active.json"))
    monkeypatch.setattr(storage, "ARCHIVED_DATA_FILE", str(tmp_path / "archived.json"))
    storage.save_tables({"table-1": _sample_table()}, {})

    def failing_mutation(active, _archived) -> None:
        active["table-1"]["system"] = "Should not persist"
        raise RuntimeError("injected failure")

    try:
        storage.mutate_tables(failing_mutation)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected injected mutation failure")

    active, _ = storage.load_tables()
    assert active["table-1"]["system"] == "Test System"
