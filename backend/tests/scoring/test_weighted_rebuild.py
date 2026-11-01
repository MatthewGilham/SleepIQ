"""Candidate weighted-HR persistence/history on isolated synthetic stores only."""

import json
from dataclasses import asdict, replace
from datetime import date, timedelta

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from app.db.backup import create_daily, restore_isolated
from app.db.engine import open_engine
from app.db.migrate import upgrade
from app.domain.config import DERIVE, PILOT_SCORE, SCORE, WEIGHTED_DERIVE, WEIGHTED_SCORE
from app.domain.rebuild import rebuild, rescore
from app.ingest.service import make_handler
from app.ingest.store import import_bytes
from app.main import create_app
from factories import block, merge, new_store, night_blocks, payload, point, utc
from fastapi.testclient import TestClient
from sqlalchemy import text

FIRST = date(2026, 1, 10)


def dense_night(day):
    blocks = night_blocks(day, hr=None)
    start = utc(day - timedelta(days=1), 23)
    minutes = [0, 20, *range(30, 451, 30), 460]
    readings = [
        point(start + timedelta(minutes=m), Avg=40 if m == 0 else 52 if m == 20 else 56)
        for m in minutes
    ]
    return [*blocks, block("heart_rate", "count/min", readings)]


def rows(engine, table):
    with engine.connect() as conn:
        return [
            dict(r) for r in conn.execute(text(f"SELECT * FROM {table} ORDER BY 1, 2")).mappings()
        ]


def candidate(engine, since=None, score=WEIGHTED_SCORE, derive=WEIGHTED_DERIVE):
    with engine.begin() as conn:
        rebuild(conn, since, derive=derive, score=score, now=42)


def legacy_store(scratch):
    data = scratch / "legacy"
    data.mkdir()
    (data / "raw").mkdir()
    engine = open_engine(data / "sleepiq.sqlite3")
    config = Config()
    config.set_main_option("script_location", "backend/app/db/migrations")
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "0002_health")
    return data, engine


def test_candidate_preserves_legacy_inputs_metrics_scores_and_formula(scratch):
    data, engine = new_store(scratch)
    body = payload(merge(*(dense_night(FIRST + timedelta(days=i)) for i in range(9))))
    import_bytes(engine, data, body)
    with engine.begin() as conn:
        rescore(conn, score=PILOT_SCORE, now=1)
    original = {
        t: rows(engine, t)
        for t in ("observations", "import_batches", "nightly_metrics", "nightly_scores")
    }
    raw = {p.name: p.read_bytes() for p in (data / "raw").iterdir()}
    candidate(engine)
    metrics = rows(engine, "nightly_metrics")
    assert [r for r in metrics if r["derivation_version"] == "derive-1"] == original[
        "nightly_metrics"
    ]
    weighted = [r for r in metrics if r["derivation_version"] == "derive-2"]
    assert len(weighted) == 9
    for old, new in zip(original["nightly_metrics"], weighted, strict=True):
        assert new["hr_mean"] == pytest.approx(25540 / 460)
        assert new["hr_method"] == "time_weighted_linear"
        assert (new["hr_n"], new["hr_eligible_n"], new["hr_contributing_n"]) == (18, 18, 18)
        assert (new["hr_covered_s"], new["hr_window_s"], new["hr_coverage"]) == (27600, 27600, 1)
        assert new["hr_fallback_reason"] is None
        assert new["derivation_config_hash"] == WEIGHTED_DERIVE.config_hash()
        for key in old:
            if not key.startswith("hr_") and key not in {
                "derivation_version",
                "derivation_config_hash",
                "computed_utc",
            }:
                assert new[key] == old[key], (
                    key
                )  # Includes HRV, other physiology and sleep windows.
    scores = rows(engine, "nightly_scores")
    assert [r for r in scores if r["score_version"] != "score-3"] == original["nightly_scores"]
    for old, new in zip(
        [r for r in scores if r["score_version"] == "score-2"],
        [r for r in scores if r["score_version"] == "score-3"],
        strict=True,
    ):
        before, after = [json.loads(r["details_json"]) for r in (old, new)]
        assert before["consistency"] == after["consistency"]
        for name in ("duration", "consistency", "deep", "rem"):
            assert before["components"][name] == after["components"][name]
        if old["overall"] is not None:
            delta = (
                after["components"]["sleeping_hr"]["score"]
                - before["components"]["sleeping_hr"]["score"]
            )
            assert new["overall"] - old["overall"] == pytest.approx(delta * 0.1)
    assert {k: v for k, v in asdict(WEIGHTED_SCORE).items() if k != "version"} == {
        k: v for k, v in asdict(SCORE).items() if k != "version"
    }
    assert (DERIVE.version, SCORE.version) == ("derive-1", "score-2")
    for table in ("observations", "import_batches"):
        assert rows(engine, table) == original[table]
    assert {p.name: p.read_bytes() for p in (data / "raw").iterdir()} == raw
    assert rows(engine, "app_settings") == []
    engine.dispose()


@pytest.mark.parametrize("hr,reason,n", [(52, "long_gaps", 8), (None, None, 0)])
def test_sparse_and_missing_candidates_preserve_old_mean_and_hrv(scratch, hr, reason, n):
    data, engine = new_store(scratch)
    import_bytes(engine, data, payload(night_blocks(FIRST, hr=hr)))
    candidate(engine)
    new = next(r for r in rows(engine, "nightly_metrics") if r["derivation_version"] == "derive-2")
    assert (new["hr_mean"], new["hr_n"], new["hr_fallback_reason"]) == (hr, n, reason)
    assert new["hr_coverage"] == 0 and new["hr_covered_s"] == 0
    assert (new["hrv_mean"], new["hrv_n"]) == (48, 1)
    engine.dispose()


def test_late_import_incremental_equals_clean_and_duplicate_is_idempotent(scratch):
    data, engine = new_store(scratch)
    import_bytes(
        engine, data, payload(merge(dense_night(FIRST), dense_night(FIRST + timedelta(days=2))))
    )
    candidate(engine)
    late = payload(dense_night(FIRST + timedelta(days=1)))
    import_bytes(engine, data, late)
    candidate(engine, FIRST + timedelta(days=1))
    incremental = [
        rows(engine, t) for t in ("nightly_metrics", "nightly_scores", "general_metrics")
    ]
    assert import_bytes(engine, data, late).status == "duplicate_batch"
    candidate(engine)
    assert [
        rows(engine, t) for t in ("nightly_metrics", "nightly_scores", "general_metrics")
    ] == incremental
    candidate(engine)
    assert [
        rows(engine, t) for t in ("nightly_metrics", "nightly_scores", "general_metrics")
    ] == incremental
    engine.dispose()


def test_failed_candidate_transaction_rolls_back_and_startup_does_not_activate(scratch):
    data, engine = new_store(scratch)
    import_bytes(engine, data, payload(dense_night(FIRST)))
    before = [rows(engine, t) for t in ("nightly_metrics", "nightly_scores")]
    with pytest.raises(RuntimeError, match="synthetic failure"), engine.begin() as conn:
        rebuild(conn, derive=WEIGHTED_DERIVE, score=WEIGHTED_SCORE)
        raise RuntimeError("synthetic failure")
    assert [rows(engine, t) for t in ("nightly_metrics", "nightly_scores")] == before
    candidate(engine)
    snapshot = rows(engine, "nightly_scores")
    with TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("127.0.0.1", 1234)
    ) as client:
        dashboard = client.get("/api/v1/dashboard").json()
        assert dashboard["versions"] == ["derive-1", "score-2"]
        assert dashboard["latest"]["physiology"][0]["value"] != pytest.approx(25540 / 460)
    assert rows(engine, "nightly_scores") == snapshot
    assert rows(engine, "app_settings") == []
    engine.dispose()


@pytest.mark.parametrize(
    "derive,score",
    [
        (WEIGHTED_DERIVE, SCORE),
        (DERIVE, WEIGHTED_SCORE),
        (replace(WEIGHTED_DERIVE, hr_max_gap_seconds=3600), WEIGHTED_SCORE),
        (WEIGHTED_DERIVE, replace(WEIGHTED_SCORE, hr_points=((45, 0), (58, 100)))),
    ],
)
def test_invalid_version_or_policy_pair_rejected_before_mutation(scratch, derive, score):
    data, engine = new_store(scratch)
    import_bytes(engine, data, payload(dense_night(FIRST)))
    before = [rows(engine, t) for t in ("nightly_metrics", "nightly_scores")]
    with pytest.raises(ValueError, match="version|policy"):
        candidate(engine, derive=derive, score=score)
    with pytest.raises(ValueError, match="version|policy"), engine.begin() as conn:
        rescore(conn, derive=derive, score=score)
    assert [rows(engine, t) for t in ("nightly_metrics", "nightly_scores")] == before
    engine.dispose()


def test_additive_migration_preserves_old_store_and_legacy_runtime(scratch):
    data, engine = legacy_store(scratch)
    body = payload(dense_night(FIRST))
    import_bytes(engine, data, body)
    assert make_handler(data)(body)["status"] == "duplicate_batch"
    old = rows(engine, "nightly_metrics")
    with pytest.raises(ValueError, match="schema"):
        candidate(engine)
    assert rows(engine, "nightly_metrics") == old
    upgrade(engine)
    new = rows(engine, "nightly_metrics")
    assert len(new) == 1 and {k: new[0][k] for k in old[0]} == old[0]
    for key in set(new[0]) - set(old[0]):
        assert new[0][key] is None
    assert make_handler(data)(body)["status"] == "duplicate_batch"
    candidate(engine)
    engine.dispose()


def test_failed_migration_leaves_previous_schema_and_app_usable(scratch, monkeypatch):
    data, engine = legacy_store(scratch)
    body = payload(dense_night(FIRST))
    import_bytes(engine, data, body)
    before = rows(engine, "nightly_metrics")
    original = Operations.add_column
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic migration failure")
        return original(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "add_column", fail_second)
        with pytest.raises(RuntimeError, match="synthetic migration failure"):
            upgrade(engine)
    assert rows(engine, "nightly_metrics") == before
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0002_health"
    assert make_handler(data)(body)["status"] == "duplicate_batch"
    upgrade(engine)
    candidate(engine)
    engine.dispose()


def test_weighted_metadata_and_both_histories_survive_isolated_restore(scratch):
    data, engine = new_store(scratch)
    import_bytes(engine, data, payload(dense_night(FIRST)))
    candidate(engine)
    backups = scratch / "backups"
    backups.mkdir()
    snapshot = create_daily(data / "sleepiq.sqlite3", data / "raw", backups, FIRST)
    restored = restore_isolated(snapshot, scratch / "isolated")
    assert (restored / "database.sqlite3").is_file()
    recovery = open_engine(restored / "database.sqlite3")
    for table in ("observations", "nightly_metrics", "nightly_scores", "general_metrics"):
        assert rows(recovery, table) == rows(engine, table)
    recovery.dispose()
    engine.dispose()


def test_stored_policy_mismatch_rejected_without_deleting_history(scratch):
    data, engine = new_store(scratch)
    import_bytes(engine, data, payload(dense_night(FIRST)))
    candidate(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE nightly_metrics SET derivation_config_hash=:h "
                "WHERE derivation_version='derive-2'"
            ),
            {"h": "0" * 64},
        )
    before = [rows(engine, table) for table in ("nightly_metrics", "nightly_scores")]
    with pytest.raises(ValueError, match="policy"):
        candidate(engine)
    with pytest.raises(ValueError, match="policy"), engine.begin() as conn:
        rescore(conn, derive=WEIGHTED_DERIVE, score=WEIGHTED_SCORE)
    assert [rows(engine, table) for table in ("nightly_metrics", "nightly_scores")] == before
    engine.dispose()


def test_ingest_rejects_unknown_future_schema(scratch):
    data, engine = new_store(scratch)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num='unknown_schema'"))
    with pytest.raises(ValueError, match="schema"):
        make_handler(data)
    engine.dispose()
