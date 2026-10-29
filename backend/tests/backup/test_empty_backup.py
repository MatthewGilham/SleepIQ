from datetime import date
from pathlib import Path

from app.db.backup import create_daily, restore_isolated
from app.db.initialize import initialize


def test_empty_database_restores_with_raw_directory(scratch: Path) -> None:
    data = scratch / "data"
    data.mkdir()
    initialize(data)
    backups = scratch / "backups"
    backups.mkdir()
    snapshot = create_daily(data / "sleepiq.sqlite3", data / "raw", backups, date(2026, 10, 29))
    restored = restore_isolated(snapshot, scratch / "restored")
    assert (restored / "raw").is_dir()
    assert list((restored / "raw").iterdir()) == []
