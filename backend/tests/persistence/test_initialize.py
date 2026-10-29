from pathlib import Path

import pytest
from app.db.initialize import initialize


def test_only_new_empty_store_is_initialized(scratch: Path) -> None:
    initialize(scratch)
    database = scratch / "sleepiq.sqlite3"
    before = database.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        initialize(scratch)
    assert database.read_bytes() == before
    assert (scratch / "raw").is_dir()


def test_nonempty_raw_directory_is_refused(scratch: Path) -> None:
    raw = scratch / "raw"
    raw.mkdir()
    (raw / "synthetic.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="empty regular raw"):
        initialize(scratch)
    assert not (scratch / "sleepiq.sqlite3").exists()
