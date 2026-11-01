"""Owner rollout and coordinated consumers, using isolated synthetic data only."""

import csv
import io
import json
from datetime import date, timedelta

import pytest
from app.analytics.api import Pairing, Selection, Window, correlation, series
from app.analytics.dashboard import dashboard
from app.analytics.export import ExportRequest, nightly_csv
from app.analytics.summary import summary
from app.domain.rollout import activate, prepare, rollback
from app.domain.versions import active_pair
from app.ingest.service import make_handler
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.tests.factories import merge, new_store, payload
from backend.tests.scoring.test_weighted_rebuild import FIRST, dense_night, rows


def setup(scratch):
    data, engine = new_store(scratch)
    import_bytes(
        engine, data, payload(merge(*(dense_night(FIRST + timedelta(days=i)) for i in range(9))))
    )
    backups = scratch / "backups"
    backups.mkdir()
    return data, engine, backups


def test_prepare_is_inactive_then_all_consumers_use_reviewed_pair(scratch):
    data, engine, backups = setup(scratch)
    old_hrv = [r["hrv_mean"] for r in rows(engine, "nightly_metrics")]
    result = prepare(data, backups, confirm_individual_hr=True)
    assert result["nights"] == 9 and result["weighted"] == 9
    assert result["fallback"] == result["missing"] == 0
    assert dashboard(engine, True)["versions"] == ["derive-1", "score-2"]
    with engine.connect() as conn:
        assert active_pair(conn).generation == 0
    pair = activate(data, backups, result["review_token"])
    assert pair.versions == ["derive-2", "score-3"] and pair.generation == 1
    view = dashboard(engine, True)
    assert view["versions"] == pair.versions
    hr = view["latest"]["physiology"][0]
    assert hr["value"] == pytest.approx(25540 / 460)
    assert hr["quality"]["method"] == "time_weighted_linear"
    assert hr["quality"]["coverage"] == 1 and hr["quality"]["covered_s"] == 27600
    graph = series(engine, Selection(metrics=["hr_mean", "hrv_mean"], range="all"))
    assert graph["versions"] == pair.versions
    assert graph["series"][0]["details"][0]["hr_quality"] == hr["quality"]
    assert graph["series"][1]["raw"] == old_hrv
    assert summary(engine, Window(range="all"))["metrics"]["hr_mean"]["mean"] == pytest.approx(
        25540 / 460
    )
    assert (
        correlation(engine, Pairing(x="hr_mean", y="hrv_mean", range="all"))["versions"]
        == pair.versions
    )
    _, csv_text, _ = nightly_csv(
        engine, ExportRequest(metrics=["hr_mean", "hrv_mean"], range="all")
    )
    exported = list(csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"))))
    assert exported[0]["hr_method"] == "time_weighted_linear"
    assert exported[0]["hr_coverage"] == "1.0"
    assert exported[0]["derivation_version"] == "derive-2"
    assert exported[0]["score_version"] == "score-3"
    _, no_hr, _ = nightly_csv(engine, ExportRequest(metrics=["hrv_mean"], range="all"))
    assert "hr_method" not in no_hr
    engine.dispose()


def test_old_same_day_backup_does_not_replace_fresh_rollout_snapshot(scratch):
    data, engine, backups = setup(scratch)
    from app.db.backup import create_daily, verify

    original = create_daily(data / "sleepiq.sqlite3", data / "raw", backups, date.today())
    import_bytes(engine, data, payload(dense_night(FIRST + timedelta(days=10))))
    result = prepare(data, backups, confirm_individual_hr=True)
    checkpoint = backups / "hr" / result["checkpoint"]
    assert checkpoint.is_dir() and original.is_dir()
    assert len(list(checkpoint.glob("????-??-??/manifest.json"))) == 1
    assert (checkpoint / "restore-check" / "database.sqlite3").is_file()
    verify(next(checkpoint.glob("????-??-??/manifest.json")).parent)
    engine.dispose()


def test_unconfirmed_input_or_unreviewed_token_cannot_activate(scratch):
    data, engine, backups = setup(scratch)
    with pytest.raises(ValueError, match="individual"):
        prepare(data, backups, confirm_individual_hr=False)
    result = prepare(data, backups, confirm_individual_hr=True)
    with pytest.raises(ValueError, match="review"):
        activate(data, backups, "wrong-token")
    assert dashboard(engine, True)["versions"] == ["derive-1", "score-2"]
    assert activate(data, backups, result["review_token"]).generation == 1
    engine.dispose()


@pytest.mark.parametrize("change", ["new_input", "candidate", "backup"])
def test_changes_after_review_prevent_activation(scratch, change):
    data, engine, backups = setup(scratch)
    result = prepare(data, backups, confirm_individual_hr=True)
    if change == "new_input":
        import_bytes(engine, data, payload(dense_night(FIRST + timedelta(days=10))))
    elif change == "candidate":
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE nightly_metrics SET hr_mean=100 WHERE derivation_version='derive-2'")
            )
    else:
        checkpoint = backups / "hr" / result["checkpoint"]
        next(checkpoint.glob("????-??-??/database.sqlite3")).write_bytes(b"synthetic corruption")
    with pytest.raises(ValueError):
        activate(data, backups, result["review_token"])
    assert dashboard(engine, True)["versions"] == ["derive-1", "score-2"]
    engine.dispose()


def test_stale_app_and_receiver_reject_until_restarted(scratch):
    data, engine, backups = setup(scratch)
    app = create_app(chart_data=data)
    receiver = make_handler(data)
    result = prepare(data, backups, confirm_individual_hr=True)
    activate(data, backups, result["review_token"])
    new_body = payload(dense_night(FIRST + timedelta(days=10)))
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/v1/dashboard").status_code == 503
    with pytest.raises(ValueError, match="restart"):
        receiver(new_body)
    make_handler(data)(new_body)
    weighted = [r for r in rows(engine, "nightly_metrics") if r["derivation_version"] == "derive-2"]
    assert len(weighted) == 10 and weighted[-1]["hr_method"] == "time_weighted_linear"
    engine.dispose()


def test_rollback_rebuilds_new_imports_and_preserves_weighted_history(scratch):
    data, engine, backups = setup(scratch)
    result = prepare(data, backups, confirm_individual_hr=True)
    activate(data, backups, result["review_token"])
    import_bytes(engine, data, payload(dense_night(FIRST + timedelta(days=10))))
    weighted = [r for r in rows(engine, "nightly_metrics") if r["derivation_version"] == "derive-2"]
    observations = rows(engine, "observations")
    pair = rollback(data, backups)
    assert pair.versions == ["derive-1", "score-2"] and pair.generation == 2
    assert (
        len([r for r in rows(engine, "nightly_metrics") if r["derivation_version"] == "derive-1"])
        == 10
    )
    assert [
        r for r in rows(engine, "nightly_metrics") if r["derivation_version"] == "derive-2"
    ] == weighted
    assert rows(engine, "observations") == observations
    engine.dispose()


def test_invalid_active_record_fails_closed(scratch):
    data, engine, _ = setup(scratch)
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app_settings VALUES ('derivation.active.v1', :v)"),
            {"v": json.dumps({"derive": "derive-2", "score": "score-2"})},
        )
    with pytest.raises(ValueError):
        create_app(chart_data=data)
    with pytest.raises(ValueError):
        make_handler(data)
    engine.dispose()


def test_incomplete_active_history_is_not_backfilled_at_startup(scratch):
    data, engine, backups = setup(scratch)
    result = prepare(data, backups, confirm_individual_hr=True)
    activate(data, backups, result["review_token"])
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM nightly_scores WHERE score_version='score-3'"))
    with pytest.raises(ValueError, match="incomplete"):
        create_app(chart_data=data)
    assert not [r for r in rows(engine, "nightly_scores") if r["score_version"] == "score-3"]
    engine.dispose()


def test_failed_activation_transaction_keeps_legacy_active(scratch, monkeypatch):
    from app.domain import rollout

    data, engine, backups = setup(scratch)
    result = prepare(data, backups, confirm_individual_hr=True)
    original = rollout.set_active

    def failing(conn, weighted):
        original(conn, weighted)
        raise RuntimeError("synthetic activation failure")

    monkeypatch.setattr(rollout, "set_active", failing)
    with pytest.raises(RuntimeError, match="synthetic activation failure"):
        activate(data, backups, result["review_token"])
    assert dashboard(engine, True)["versions"] == ["derive-1", "score-2"]
    engine.dispose()
