"""Synthetic chart/preset integration and independent normalization references."""

import json
from datetime import date
from pathlib import Path

import pytest
from app.analytics.api import Selection, normalize, series
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


def client(data):
    return TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("127.0.0.1", 50123)
    )


def test_normalization_reference():
    values, stats = normalize([1, None, 2, 3])
    assert values == pytest.approx([-1.224744871391589, None, 0, 1.224744871391589])
    assert stats["n"] == 3
    assert stats["sd"] == pytest.approx((2 / 3) ** 0.5)
    assert normalize([2, None, 2])[0] == [None, None, None]
    assert normalize([])[1]["reason"]


def test_calendar_gaps_units_offsets_and_missing(store):
    _, engine = store
    result = series(
        engine, Selection(metrics=["asleep_s", "efficiency", "hrv_mean", "onset_minute"], range="7")
    )
    assert len(result["dates"]) == 7
    assert result["dates"][-1] == "2026-10-28"
    assert result["series"][0]["values"][-1] == 7.5
    assert result["series"][0]["values"][-2] is None
    assert result["series"][1]["values"][-1] == pytest.approx(450 / 460 * 100)
    assert result["series"][2]["values"][-3] is None
    assert result["series"][3]["details"][2]["offset_minutes"] == 60
    assert result["series"][3]["details"][-1]["offset_minutes"] == 0


@pytest.mark.parametrize("window,length", [("7", 7), ("30", 30), ("90", 90), ("all", 5)])
def test_ranges(store, window, length):
    assert len(series(store[1], Selection(metrics=["hr_mean"], range=window))["dates"]) == length


def test_custom_normalized_and_validation(store):
    r = series(
        store[1],
        Selection(
            metrics=["hrv_mean"],
            range="custom",
            start=date(2026, 10, 24),
            end=date(2026, 10, 28),
            mode="normalized",
        ),
    )
    assert r["series"][0]["values"] == [-1, None, None, None, 1]
    for args in [
        {"metrics": ["onset_minute"], "mode": "normalized"},
        {"metrics": ["unknown"]},
        {"metrics": ["hr_mean"], "range": "custom", "start": "2026-10-28", "end": "2026-10-01"},
    ]:
        with pytest.raises(ValueError):
            Selection(**args)


def test_preset_roundtrip_restart_conflicts_and_delete(store):
    data, engine = store
    body = {"metrics": ["hr_mean"], "name": "My chart", "default": True}
    with client(data) as c:
        saved = c.put("/api/v1/presets/new", json=body, headers=HEADERS).json()
        assert saved["revision"] == 1
        assert c.put("/api/v1/presets/new", json=body, headers=HEADERS).status_code == 409
    with client(data) as c:
        assert c.get("/api/v1/presets").json() == [saved]
        update = {k: v for k, v in saved.items() if k != "id"}
        update["name"] = "Renamed"
        updated = c.put(f"/api/v1/presets/{saved['id']}", json=update, headers=HEADERS).json()
        assert updated["revision"] == 2
        assert (
            c.put(f"/api/v1/presets/{saved['id']}", json=update, headers=HEADERS).status_code == 409
        )
        other = c.put(
            "/api/v1/presets/new", json={**body, "name": "Second"}, headers=HEADERS
        ).json()
        items = c.get("/api/v1/presets").json()
        assert sum(p["default"] for p in items) == 1
        assert next(p for p in items if p["id"] == other["id"])["default"]
        assert (
            c.delete(f"/api/v1/presets/{saved['id']}?revision=2", headers=HEADERS).status_code
            == 409
        )
        assert (
            c.delete(f"/api/v1/presets/{saved['id']}?revision=3", headers=HEADERS).status_code
            == 200
        )
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM nightly_metrics")).scalar() == 3


def test_browser_boundary_and_invalid_inputs(store):
    with client(store[0]) as c:
        body = {"metrics": ["hr_mean"]}
        assert c.post("/api/v1/analytics/timeseries", json=body).status_code == 403
        assert (
            c.post(
                "/api/v1/analytics/timeseries",
                json=body,
                headers={**HEADERS, "origin": "https://evil.invalid"},
            ).status_code
            == 403
        )
        assert c.get("/api/v1/presets", headers={"sec-fetch-site": "cross-site"}).status_code == 403
        assert (
            c.post("/api/v1/analytics/timeseries", content="x" * 16385, headers=HEADERS).status_code
            == 413
        )
        assert (
            c.post(
                "/api/v1/analytics/timeseries", json={"metrics": ["bad"]}, headers=HEADERS
            ).status_code
            == 422
        )
        good = c.post("/api/v1/analytics/timeseries", json=body, headers=HEADERS)
        assert good.status_code == 200
        assert good.headers["cache-control"] == "no-store"
        assert c.get("/api/v1/presets", headers={"host": "evil.invalid"}).status_code == 400
    with TestClient(
        create_app(chart_data=store[0]), base_url="http://localhost", client=("192.168.1.10", 1)
    ) as c:
        assert c.get("/api/v1/presets").status_code == 403


def test_empty_store_and_unconfigured(scratch):
    _, engine = new_store(scratch)
    assert series(engine, Selection(metrics=["hr_mean"]))["dates"] == []
    engine.dispose()
    with TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 1)) as c:
        assert c.get("/api/v1/presets").status_code == 503


def test_resting_heart_rate_is_not_offered_or_accepted(store):
    data, _ = store
    with client(data) as c:
        ids = [m["id"] for m in c.get("/api/v1/metrics/catalog").json()]
        assert "rhr_mean" not in ids and "hr_mean" in ids
        rejected = c.post(
            "/api/v1/analytics/timeseries", json={"metrics": ["rhr_mean"]}, headers=HEADERS
        )
        assert rejected.status_code == 422


def test_preset_saved_with_resting_heart_rate_loads_without_it(store):
    data, engine = store
    old = [
        {
            "id": "abc",
            "name": "Old",
            "metrics": ["asleep_s", "rhr_mean"],
            "range": "30",
            "start": None,
            "end": None,
            "mode": "actual",
            "rolling": "off",
            "default": False,
            "revision": 1,
        },
        {"id": "only", "name": "Only", "metrics": ["rhr_mean"], "revision": 1},
    ]
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app_settings(key,value_json) VALUES(:k,:v)"),
            {"k": "charts.presets.v1", "v": json.dumps(old)},
        )
    with client(data) as c:
        loaded = {p["id"]: p for p in c.get("/api/v1/presets").json()}
    assert loaded["abc"]["metrics"] == ["asleep_s"]
    assert loaded["only"]["metrics"] == ["asleep_s"]  # never an empty chart


def test_average_is_mean_of_observed_nights_whatever_the_rolling_setting(store):
    # U08-8: the chart's average line uses normalization.mean. Hand reference over 24-28 Oct:
    # HR nights 50, 60, 70 -> 60; HRV 40, (missing on 26 Oct), 60 -> 50; 25 and 27 Oct unrecorded.
    data, _ = store
    body = {"metrics": ["hr_mean", "hrv_mean"], "range": "custom", "start": "2026-10-24"}
    body["end"] = "2026-10-28"
    with client(data) as c:
        for rolling in ("off", "7", "30"):
            got = c.post(
                "/api/v1/analytics/timeseries", json={**body, "rolling": rolling}, headers=HEADERS
            ).json()
            by_id = {s["id"]: s for s in got["series"]}
            assert len(got["dates"]) == 5
            assert by_id["hr_mean"]["normalization"]["mean"] == pytest.approx(60)
            assert by_id["hr_mean"]["normalization"]["n"] == 3
            assert by_id["hrv_mean"]["normalization"]["mean"] == pytest.approx(50)
            assert by_id["hrv_mean"]["normalization"]["n"] == 2
