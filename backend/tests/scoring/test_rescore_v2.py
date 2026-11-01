"""Version transition, atomic historical rescore and startup backfill on synthetic stores."""

from datetime import date

import pytest
from app.domain.config import PILOT_SCORE, SCORE
from app.domain.rebuild import rescore
from app.ingest.rebuild_cli import run
from app.ingest.store import import_bytes
from app.main import create_app
from factories import new_store, nights_payload
from sqlalchemy import text


def rows(engine, table):
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(f"SELECT * FROM {table} ORDER BY 1"))]


def test_historical_rescore_preserves_inputs_pilot_outputs_and_matches_fresh_v2(scratch):
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 1, 1), 12, hrv=None))
    with engine.begin() as conn:
        rescore(conn, score=PILOT_SCORE, now=1)
    observations = rows(engine, "observations")
    metrics = rows(engine, "nightly_metrics")
    old = [r for r in rows(engine, "nightly_scores") if r[1] == PILOT_SCORE.version]
    expected = [r[:-1] for r in rows(engine, "nightly_scores") if r[1] == SCORE.version]
    # Exercise the backed-up owner command, twice, including a history without HRV.
    backups = scratch / "backups"
    backups.mkdir()
    assert run(data, backups, date(2026, 1, 20), scores_only=True) == 12
    assert run(data, backups, date(2026, 1, 20), scores_only=True) == 12
    assert rows(engine, "observations") == observations
    assert rows(engine, "nightly_metrics") == metrics
    current = rows(engine, "nightly_scores")
    assert [r for r in current if r[1] == PILOT_SCORE.version] == old
    assert [r[:-1] for r in current if r[1] == SCORE.version] == expected
    assert len(current) == 24
    assert len(list(backups.iterdir())) == 1
    # A transaction failure must restore the previous score rows.
    with pytest.raises(RuntimeError), engine.begin() as conn:
        rescore(conn, now=3)
        raise RuntimeError("synthetic failure")
    assert rows(engine, "nightly_scores") == current


def test_dashboard_startup_backfills_all_old_nights_and_is_idempotent(scratch):
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 1, 1), 12))
    with engine.begin() as conn:
        rescore(conn, score=PILOT_SCORE, now=1)
        conn.execute(
            text("DELETE FROM nightly_scores WHERE score_version=:v"), {"v": SCORE.version}
        )
    before = rows(engine, "nightly_metrics")
    create_app(chart_data=data)
    first = rows(engine, "nightly_scores")
    assert len(first) == 24
    assert sum(r[4] == "scored" for r in first if r[1] == SCORE.version) == 5
    assert rows(engine, "nightly_metrics") == before
    create_app(chart_data=data)
    assert rows(engine, "nightly_scores") == first
