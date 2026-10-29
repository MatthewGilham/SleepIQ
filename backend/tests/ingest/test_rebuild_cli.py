import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from app.db.engine import open_engine
from app.domain.config import DERIVE
from app.ingest import store
from app.ingest.rebuild_cli import run
from factories import merge, new_store, night_blocks, payload
from sqlalchemy import text


def flags(data: Path) -> list[str]:
    engine = open_engine(data / "sleepiq.sqlite3")
    try:
        with engine.connect() as conn:
            return list(
                json.loads(
                    str(conn.execute(text("SELECT flags_json FROM nightly_metrics")).scalar())
                )
            )
    finally:
        engine.dispose()


def test_clean_rebuild_applies_a_changed_source_preference_without_touching_observations(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    body = payload(merge(night_blocks(date(2026, 1, 3))))
    # A label matching no preference is flagged until the owner-chosen preference changes.
    body = body.replace(b"Synthetic Apple Watch", b"Synthetic Band")
    store.import_bytes(engine, data, body)
    before = (
        engine.connect().execute(text("SELECT count(*), sum(start_utc) FROM observations")).one()
    )
    engine.dispose()
    assert "non_preferred_source" in flags(data)
    backups = scratch / "backups"
    backups.mkdir()
    run(data, backups, date(2026, 1, 4), replace(DERIVE, preferred_source="band"))
    assert "non_preferred_source" not in flags(data)
    engine = open_engine(data / "sleepiq.sqlite3")
    after = (
        engine.connect().execute(text("SELECT count(*), sum(start_utc) FROM observations")).one()
    )
    engine.dispose()
    assert tuple(before) == tuple(after)
    assert len(list(backups.iterdir())) == 1  # verified snapshot taken first
