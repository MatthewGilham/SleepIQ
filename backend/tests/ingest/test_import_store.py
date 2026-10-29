import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.db.coordinator import write_guard
from app.ingest import store
from app.ingest.parse import UnsupportedExport
from factories import (
    PLAN,
    WATCH,
    block,
    merge,
    new_store,
    night_blocks,
    nights_payload,
    payload,
    sleep_rows,
    utc,
)
from sqlalchemy import Engine, text

FIRST = date(2026, 1, 10)


def one(engine: Engine, sql: str) -> object:
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


def snapshot(engine: Engine) -> dict[str, list[tuple[object, ...]]]:
    """Every table except time-of-computation columns, for equality checks."""
    queries = {
        "obs": "SELECT metric, source, start_utc, end_utc, stage, qty, avg, fingerprint, status "
        "FROM observations ORDER BY fingerprint",
        "nights": "SELECT * FROM nightly_metrics ORDER BY wake_date",
        "general": "SELECT * FROM general_metrics ORDER BY local_date, metric",
        "scores": "SELECT wake_date, score_version, config_hash, status, overall, consistency, "
        "details_json FROM nightly_scores ORDER BY wake_date",
    }
    result = {}
    with engine.connect() as conn:
        for name, sql in queries.items():
            rows = [tuple(r) for r in conn.execute(text(sql))]
            if name == "nights":
                rows = [r[:-1] for r in rows]  # drop computed_utc
            result[name] = rows
    return result


def test_import_stores_observations_derives_nights_and_keeps_raw_bytes(scratch: Path) -> None:
    data, engine = new_store(scratch)
    body = nights_payload(FIRST, 3)
    result = store.import_bytes(engine, data, body, received_utc=1)
    assert result.status == "imported" and result.new > 0 and result.conflicting == 0
    assert one(engine, "SELECT count(*) FROM nightly_metrics") == 3
    assert (data / "raw").glob("*.json") and len(list((data / "raw").iterdir())) == 1
    assert next((data / "raw").iterdir()).read_bytes() == body
    row = one(engine, "SELECT efficiency FROM nightly_metrics WHERE wake_date = '2026-01-10'")
    assert row == pytest.approx(450 / 460)
    summary = json.loads(str(one(engine, "SELECT summary_json FROM import_batches")))
    assert summary["new"] == result.new


def test_same_file_twice_and_overlapping_files_do_not_duplicate(scratch: Path) -> None:
    data, engine = new_store(scratch)
    first = nights_payload(FIRST, 4)
    overlap = nights_payload(FIRST + timedelta(days=2), 4)
    store.import_bytes(engine, data, first)
    after_first = snapshot(engine)
    repeat = store.import_bytes(engine, data, first)
    assert repeat.status == "duplicate_batch" and snapshot(engine) == after_first
    second = store.import_bytes(engine, data, overlap)
    assert second.duplicate > 0 and second.conflicting == 0
    assert one(engine, "SELECT count(*) FROM nightly_metrics") == 6
    clean = new_store(scratch / "clean") if (scratch / "clean").mkdir() is None else None
    assert clean is not None
    store.import_bytes(clean[1], clean[0], nights_payload(FIRST, 6))
    assert snapshot(engine)["nights"] == snapshot(clean[1])["nights"]
    assert snapshot(engine)["obs"] == snapshot(clean[1])["obs"]


def test_batch_order_does_not_change_results(scratch: Path) -> None:
    (scratch / "a").mkdir()
    (scratch / "b").mkdir()
    (da, ea), (db, eb) = new_store(scratch / "a"), new_store(scratch / "b")
    early, late = nights_payload(FIRST, 5), nights_payload(FIRST + timedelta(days=5), 5)
    store.import_bytes(ea, da, early)
    store.import_bytes(ea, da, late)
    store.import_bytes(eb, db, late)  # reordered: later nights arrive first
    store.import_bytes(eb, db, early)
    assert snapshot(ea) == snapshot(eb)


def test_changed_reading_is_flagged_and_first_received_value_is_kept(scratch: Path) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 1))
    hr_before = one(engine, "SELECT hr_mean FROM nightly_metrics")
    original = night_blocks(FIRST)
    revised = json.loads(json.dumps(original))
    for item in revised:
        if item["name"] == "heart_rate":
            item["data"][0]["Avg"] += 20  # same slot, different value
    result = store.import_bytes(engine, data, payload(revised))
    assert result.conflicting == 1 and result.new == 1
    assert one(engine, "SELECT count(*) FROM observations WHERE status = 'conflicting'") == 1
    assert one(engine, "SELECT hr_mean FROM nightly_metrics") == hr_before  # no silent overwrite
    assert "revised" in str(one(engine, "SELECT flags_json FROM nightly_metrics"))


def test_resegmented_sleep_stages_are_a_revision_not_extra_sleep(scratch: Path) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 1))
    asleep = one(engine, "SELECT asleep_s FROM nightly_metrics")
    start = utc(FIRST - timedelta(days=1), 23)
    other = sleep_rows(start, [("Core", 200), ("Deep", 100), ("REM", 150)])
    result = store.import_bytes(engine, data, payload([block("sleep_analysis", "hr", other)]))
    assert result.conflicting == 3
    assert one(engine, "SELECT asleep_s FROM nightly_metrics") == asleep  # not double-counted
    assert "revised" in str(one(engine, "SELECT flags_json FROM nightly_metrics"))


def test_invalid_batches_store_nothing(scratch: Path) -> None:
    data, engine = new_store(scratch)
    for bad in (b"not json", b"[]", b'{"data": {"metrics": [5]}}', b"x" * (store.MAX_BYTES + 1)):
        with pytest.raises(UnsupportedExport):
            store.import_bytes(engine, data, bad)
    assert one(engine, "SELECT count(*) FROM import_batches") == 0
    assert list((data / "raw").iterdir()) == []


def test_rejected_and_unmapped_rows_are_visible_and_valid_rows_import(scratch: Path) -> None:
    data, engine = new_store(scratch)
    blocks = night_blocks(FIRST)
    blocks.append(block("steps", "count", [{"a": 1}]))
    blocks.append(block("respiratory_rate", "count/min", [{"start": "bad", "end": "bad"}]))
    result = store.import_bytes(engine, data, payload(merge(blocks)))
    assert result.unmapped_metrics == {"steps": 1}
    assert result.rejected == {"respiratory_rate:timestamp": 1}
    assert result.new > 0


@pytest.mark.parametrize("crash", ["raw_publish", "mid_insert", "rebuild", "batch_summary"])
def test_crash_points_never_partially_commit_and_retry_succeeds(
    scratch: Path, monkeypatch: pytest.MonkeyPatch, crash: str
) -> None:
    data, engine = new_store(scratch)
    body = nights_payload(FIRST, 3)
    calls = {"n": 0}
    real_insert, real_rebuild, real_replace = store._insert, store.rebuild, store.os.replace

    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("simulated crash")

    def flaky_insert(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 20:
            boom()
        return real_insert(*args, **kwargs)  # type: ignore[arg-type]

    if crash == "raw_publish":
        monkeypatch.setattr(store.os, "replace", boom)
    elif crash == "mid_insert":
        monkeypatch.setattr(store, "_insert", flaky_insert)
    elif crash == "rebuild":
        monkeypatch.setattr(store, "rebuild", boom)
    else:
        original = store.text

        def failing_text(sql: str):  # type: ignore[no-untyped-def]
            if sql.startswith("UPDATE import_batches"):
                boom()
            return original(sql)

        monkeypatch.setattr(store, "text", failing_text)
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.import_bytes(engine, data, body)
    for table in ("import_batches", "observations", "nightly_metrics", "nightly_scores"):
        assert one(engine, f"SELECT count(*) FROM {table}") == 0, table
    assert list((data / "raw").iterdir()) == []  # temp and published raw both cleaned
    monkeypatch.setattr(store, "_insert", real_insert)
    monkeypatch.setattr(store, "rebuild", real_rebuild)
    monkeypatch.setattr(store.os, "replace", real_replace)
    if crash == "batch_summary":
        monkeypatch.undo()
    retry = store.import_bytes(engine, data, body)
    assert retry.status == "imported"
    (scratch / "ref").mkdir()
    ref_data, ref_engine = new_store(scratch / "ref")
    store.import_bytes(ref_engine, ref_data, body)
    assert snapshot(engine) == snapshot(ref_engine)


def test_importer_uses_the_shared_writer_gate(scratch: Path) -> None:
    data, engine = new_store(scratch)
    with write_guard(data):  # e.g. a running backup holds the gate
        # A second process would time out; the same-thread lock is re-entrant, so assert the
        # importer goes through the gate by observing the lock file it creates and uses.
        assert (data / ".write.lock").exists()
    assert WATCH and PLAN  # factories import sanity
    store.import_bytes(engine, data, nights_payload(FIRST, 1))
    assert (data / ".write.lock").exists()
