import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.db import backup
from app.db.engine import open_engine
from app.db.migrate import upgrade


@pytest.fixture
def sources(scratch: Path) -> tuple[Path, Path, Path]:
    database = scratch / "live.sqlite3"
    engine = open_engine(database)
    try:
        upgrade(engine)
    finally:
        engine.dispose()
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("INSERT INTO app_settings VALUES ('theme', '\"dark\"')")
        connection.commit()
    raw = scratch / "raw"
    raw.mkdir()
    (raw / "synthetic.json").write_text('{"synthetic":true}', encoding="utf-8")
    folder = scratch / "backups"
    folder.mkdir()
    return database, raw, folder


def test_snapshot_and_isolated_restore(sources: tuple[Path, Path, Path], scratch: Path) -> None:
    database, raw, folder = sources
    snapshot = backup.create_daily(database, raw, folder, date(2026, 10, 29))
    assert set(backup.verify(snapshot)) == {"database.sqlite3", "raw/synthetic.json"}
    restored = backup.restore_isolated(snapshot, scratch / "restore-test")
    assert (restored / "raw/synthetic.json").read_bytes() == (raw / "synthetic.json").read_bytes()
    with closing(sqlite3.connect(restored / "database.sqlite3")) as connection:
        assert connection.execute("SELECT * FROM app_settings").fetchall() == [("theme", '"dark"')]
    assert database.is_file()


def test_repeat_same_day_does_not_replace_snapshot(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    first = backup.create_daily(database, raw, folder, date(2026, 10, 29))
    manifest = (first / "manifest.json").read_bytes()
    (raw / "later.json").write_text("{}", encoding="utf-8")
    assert backup.create_daily(database, raw, folder, date(2026, 10, 29)) == first
    assert (first / "manifest.json").read_bytes() == manifest
    assert not (first / "raw/later.json").exists()


def test_rotation_retains_fourteen_successful_dates(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    (folder / "unrelated").mkdir()
    start = date(2026, 10, 1)
    for index in range(16):
        backup.create_daily(database, raw, folder, start + timedelta(days=index))
    dates = sorted(path.name for path in folder.iterdir() if path.name != "unrelated")
    assert dates == [(start + timedelta(days=i)).isoformat() for i in range(2, 16)]
    assert (folder / "unrelated").is_dir()
    assert (raw / "synthetic.json").is_file()


def test_downtime_creates_only_one_current_snapshot(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    backup.create_daily(database, raw, folder, date(2026, 10, 1))
    backup.create_daily(database, raw, folder, date(2026, 10, 29))
    assert sorted(p.name for p in folder.iterdir()) == ["2026-10-01", "2026-10-29"]


def test_failed_copy_keeps_prior_snapshot(
    sources: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, raw, folder = sources
    prior = backup.create_daily(database, raw, folder, date(2026, 10, 28))

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("Synthetic disk-full failure")

    monkeypatch.setattr(backup.shutil, "copyfile", fail)
    with pytest.raises(OSError):
        backup.create_daily(database, raw, folder, date(2026, 10, 29))
    backup.verify(prior)
    assert not (folder / "2026-10-29").exists()


def test_corrupt_raw_blocks_restore(sources: tuple[Path, Path, Path], scratch: Path) -> None:
    snapshot = backup.create_daily(*sources, date(2026, 10, 29))
    (snapshot / "raw/synthetic.json").write_text("damaged", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        backup.restore_isolated(snapshot, scratch / "restore-test")
    assert not (scratch / "restore-test").exists()


def test_existing_restore_target_is_never_overwritten(
    sources: tuple[Path, Path, Path],
    scratch: Path,
) -> None:
    snapshot = backup.create_daily(*sources, date(2026, 10, 29))
    destination = scratch / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError):
        backup.restore_isolated(snapshot, destination)
    assert marker.read_text() == "preserve"


def test_manifest_traversal_is_rejected(sources: tuple[Path, Path, Path]) -> None:
    snapshot = backup.create_daily(*sources, date(2026, 10, 29))
    path = snapshot / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"]["../outside.json"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe"):
        backup.verify(snapshot)


def test_unknown_files_block_retention_delete(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    snapshot = backup.create_daily(database, raw, folder, date(2026, 10, 29))
    (snapshot / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        backup._delete_verified(snapshot, folder)
    assert (snapshot / "unrelated.txt").read_text() == "keep"
    assert database.is_file()


def test_non_json_raw_is_not_copied(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    (raw / "secret.key").write_text("synthetic", encoding="utf-8")
    with pytest.raises(ValueError):
        backup.create_daily(database, raw, folder, date(2026, 10, 29))
    assert not (folder / "2026-10-29").exists()


def test_committed_wal_data_is_in_snapshot(sources: tuple[Path, Path, Path]) -> None:
    database, raw, folder = sources
    with closing(sqlite3.connect(database)) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("INSERT INTO app_settings VALUES ('wal-test', '123')")
        writer.commit()
        snapshot = backup.create_daily(database, raw, folder, date(2026, 10, 29))
        with closing(sqlite3.connect(snapshot / "database.sqlite3")) as copied:
            assert copied.execute(
                "SELECT value_json FROM app_settings WHERE key='wal-test'"
            ).fetchone() == ("123",)


def test_corrupt_database_is_rejected_even_with_matching_hash(
    sources: tuple[Path, Path, Path],
) -> None:
    snapshot = backup.create_daily(*sources, date(2026, 10, 29))
    database = snapshot / "database.sqlite3"
    database.write_bytes(b"synthetic invalid SQLite file")
    path = snapshot / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"]["database.sqlite3"] = backup._digest(database)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(sqlite3.Error):
        backup.verify(snapshot)
