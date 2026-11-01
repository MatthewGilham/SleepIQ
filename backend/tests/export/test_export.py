"""CSV export: selected metrics/ranges, units, missing values, versions, formula safety, exclusions."""

import csv
import io
import json
from datetime import date
from pathlib import Path

import pytest
from app.analytics.catalog import BY_ID
from app.analytics.export import ExportRequest, cell, clock, nightly_csv, safe_text
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.tests.factories import merge, new_store, night_blocks, payload

HEADERS = {"origin": "http://localhost", "x-sleepiq-request": "charts"}


@pytest.fixture
def store(scratch: Path):
    data, engine = new_store(scratch)
    import_bytes(
        engine,
        data,
        payload(
            merge(
                night_blocks(date(2026, 10, 24), hr=50, hrv=40),
                night_blocks(date(2026, 10, 26), hr=60, hrv=None),
                night_blocks(date(2026, 10, 28), hr=70, hrv=60),
            )
        ),
    )
    yield data, engine
    engine.dispose()


def parse(body: str) -> list[list[str]]:
    assert body.startswith("\ufeff")
    return list(csv.reader(io.StringIO(body[1:])))


def test_selected_metrics_units_missing_values_and_versions(store):
    _, engine = store
    name, body, count = nightly_csv(
        engine,
        ExportRequest(metrics=["asleep_s", "hrv_mean", "onset_minute", "efficiency"], range="all"),
    )
    rows = parse(body)
    assert rows[0] == [
        "wake_date",
        "Total asleep (h)",
        "Overnight HRV (ms)",
        "Sleep onset (HH:MM source-local)",
        "Sleep efficiency (%)",
        "flags",
        "score_status",
        "derivation_version",
        "score_version",
    ]
    assert count == 3 and [r[0] for r in rows[1:]] == ["2026-10-24", "2026-10-26", "2026-10-28"]
    assert name == "sleepiq-nightly-2026-10-24_2026-10-28.csv"
    last = rows[3]
    assert last[1] == "7.5" and last[2] == "60.0" and last[3] == "23:00"
    assert float(last[4]) == pytest.approx(450 / 460 * 100)
    assert rows[2][2] == ""  # missing HRV is an empty cell, never 0
    assert rows[2][1] == "7.5"
    assert last[-3:] == ["insufficient_data", "derive-1", "score-2"]


def test_custom_range_is_inclusive_and_only_recorded_nights_are_listed(store):
    _, engine = store
    _, body, count = nightly_csv(
        engine,
        ExportRequest(metrics=["hr_mean"], range="custom", start="2026-10-25", end="2026-10-28"),
    )
    assert count == 2 and [r[0] for r in parse(body)[1:]] == ["2026-10-26", "2026-10-28"]
    _, body, count = nightly_csv(engine, ExportRequest(metrics=["hr_mean"], range="7"))
    assert count == 3  # relative range ends at the latest stored night (22-28 Oct)


def test_empty_store_exports_header_only(scratch: Path):
    _, engine = new_store(scratch)
    name, body, count = nightly_csv(engine, ExportRequest(metrics=["asleep_s"], range="all"))
    assert count == 0 and len(parse(body)) == 1 and name == "sleepiq-nightly-empty.csv"


def test_formula_characters_are_neutralised_in_text_but_numbers_stay_numeric(store):
    for start in "=+-@\t\r":
        assert safe_text(f"{start}cmd").startswith("'")
    assert safe_text("revised; possibly_incomplete") == "revised; possibly_incomplete"
    assert cell(-1.5, BY_ID["temp_mean"]) == "-1.5"
    assert cell(0.0, BY_ID["hr_mean"]) == "0.0"  # a real zero is kept
    assert clock(1439.6) == "00:00" and clock(23 * 60) == "23:00"
    _, engine = store
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE nightly_metrics SET flags_json=:f WHERE wake_date='2026-10-28'"),
            {"f": json.dumps(['=HYPERLINK("http://x")', "@SUM(1)"])},
        )
    rows = parse(nightly_csv(engine, ExportRequest(metrics=["asleep_s"], range="all"))[1])
    assert rows[3][2].startswith("'=HYPERLINK")


def test_export_has_no_resting_heart_rate_column(store):
    _, engine = store
    header = parse(nightly_csv(engine, ExportRequest(metrics=list(BY_ID), range="all"))[1])[0]
    assert header == [
        "wake_date",
        "Total asleep (h)",
        "Recorded awake (min)",
        "Core (min)",
        "Deep (min)",
        "REM (min)",
        "Sleep efficiency (%)",
        "Sleeping heart rate (bpm)",
        "Overnight HRV (ms)",
        "Respiratory rate (breaths/min)",
        "Sleeping wrist temperature (°C)",
        "SleepIQ score (/100)",
        "Consistency (/100)",
        "Sleep onset (HH:MM source-local)",
        "Wake time (HH:MM source-local)",
        "hr_method", "hr_n", "hr_eligible_n", "hr_contributing_n", "hr_covered_s",
        "hr_window_s", "hr_coverage", "hr_fallback_reason", "derivation_config_hash",
        "flags",
        "score_status",
        "derivation_version",
        "score_version",
    ]


def test_no_source_label_path_or_secret_field_is_exported(store):
    data, engine = store
    with engine.connect() as conn:
        source = conn.execute(text("SELECT source FROM nightly_metrics LIMIT 1")).scalar_one()
    body = nightly_csv(engine, ExportRequest(metrics=list(BY_ID), range="all"))[1]
    assert source not in body and str(data) not in body
    assert not any(word in body.lower() for word in ("token", "secret", "password", "sha256"))


def test_endpoint_boundary_headers_and_validation(store):
    data, _ = store
    api = TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("127.0.0.1", 50123)
    )
    good = {"metrics": ["asleep_s", "hrv_mean"], "range": "30"}
    ok = api.post("/api/v1/analytics/export", json=good, headers=HEADERS)
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "text/csv; charset=utf-8"
    assert ok.headers["content-disposition"] == (
        'attachment; filename="sleepiq-nightly-2026-09-29_2026-10-28.csv"'
    )
    assert ok.headers["cache-control"] == "no-store" and ok.headers["x-sleepiq-rows"] == "3"
    assert api.post("/api/v1/analytics/export", json=good).status_code == 403
    bad_origin = {**HEADERS, "origin": "http://evil.example"}
    assert api.post("/api/v1/analytics/export", json=good, headers=bad_origin).status_code == 403
    for bad in (
        {"metrics": ["nope"], "range": "30"},
        {"metrics": [], "range": "30"},
        {"metrics": ["asleep_s", "asleep_s"], "range": "30"},
        {"metrics": ["asleep_s"], "range": "custom"},
        {"metrics": ["asleep_s"], "range": "30", "path": "C:/x"},
    ):
        assert api.post("/api/v1/analytics/export", json=bad, headers=HEADERS).status_code == 422
    assert api.get("/api/v1/analytics/export").status_code == 405
