"""A01 rolling means and paired correlation against hand-calculated and stdlib references."""

import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.analytics.api import Pairing, Selection, correlation, series
from app.analytics.stats import pearson, rolling_mean
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient

from backend.tests.factories import merge, new_store, night_blocks, payload

HEADERS = {"origin": "http://localhost", "x-sleepiq-request": "charts"}
# October 2026 wake dates 1..10; nights 3 and 7 absent; HRV absent on night 5.
# Night d has sleeping HR 50 + d and HRV 30 + 2d (+5 on even nights). Respiratory is constant.
DAYS = [1, 2, 4, 5, 6, 8, 9, 10]
HR = {d: 50.0 + d for d in DAYS}
HRV = {d: 30.0 + 2 * d + (5 if d % 2 == 0 else 0) for d in DAYS if d != 5}


@pytest.fixture
def store(scratch: Path):
    data, engine = new_store(scratch)
    groups = [night_blocks(date(2026, 10, d), hr=HR[d], hrv=HRV.get(d), resp=14.5) for d in DAYS]
    import_bytes(engine, data, payload(merge(*groups)))
    yield data, engine
    engine.dispose()


def custom(first: int, last: int) -> dict[str, object]:
    return {"range": "custom", "start": date(2026, 10, first), "end": date(2026, 10, last)}


def test_rolling_reference_skips_missing_days_and_enforces_minimum():
    values = [1.0, None, 3.0, None, 5.0, 7.0, None, 9.0, None, None]
    means, counts = rolling_mean(values, 7)
    assert counts == [1, 1, 2, 2, 3, 4, 4, 4, 4, 3]
    assert means == [None, None, None, None, None, 4.0, 4.0, 6.0, 6.0, None]
    # Zero is a measurement, not missing data.
    assert rolling_mean([0.0, 0.0, 0.0, 0.0], 7)[0][-1] == 0.0
    assert rolling_mean([], 7) == ([], [])


def test_rolling_thirty_needs_fifteen_observed_nights():
    fourteen = [2.0] * 14 + [None] * 16
    assert rolling_mean(fourteen, 30)[0][-1] is None
    assert rolling_mean(fourteen, 30)[1][-1] == 14
    means, counts = rolling_mean([None] * 15 + [float(i) for i in range(15)], 30)
    assert counts[-1] == 15 and means[-1] == 7.0
    assert means[-2] is None


def test_pearson_hand_reference_and_stdlib_agreement():
    # Deviations (-1,0,1) and (-1,1,0): sxy=1, sxx=syy=2, so r = 1/2 exactly.
    assert pearson([1, 2, 3], [1, 3, 2]) == (pytest.approx(0.5), None)
    assert pearson([1, 2, 3], [10, 20, 30])[0] == pytest.approx(1)
    assert pearson([1, 2, 3], [3, 2, 1])[0] == pytest.approx(-1)
    xs = [54.5, 61.25, 49.0, 58.0, 66.75, 52.5, 60.0]
    ys = [41.0, 33.5, 47.25, 39.0, 30.5, 44.0, 36.75]
    assert pearson(xs, ys)[0] == pytest.approx(statistics.correlation(xs, ys), abs=1e-12)


def test_pearson_unavailable_cases():
    assert pearson([1, 2], [2, 1]) == (None, "Unavailable: fewer than 3 paired nights")
    assert pearson([], []) == (None, "Unavailable: fewer than 3 paired nights")
    constant = (None, "Unavailable: a metric has no variation across the paired nights")
    assert pearson([4, 4, 4], [1, 2, 3]) == constant
    assert pearson([1, 2, 3], [0.1, 0.1, 0.1]) == constant
    with pytest.raises(ValueError):
        pearson([1, 2, 3], [1, 2])


def test_series_rolling_uses_calendar_window_before_range_start(store):
    result = series(store[1], Selection(metrics=["hr_mean"], rolling="7", **custom(8, 10)))
    rolling = result["series"][0]["rolling"]
    # 10-08 covers 10-02..10-08: HR 52, 54, 55, 56, 58 (nights 3 and 7 missing).
    assert rolling["counts"] == [5, 5, 6]
    assert rolling["values"] == pytest.approx([55.0, 56.4, 57.0])
    assert rolling["window"] == 7 and rolling["minimum"] == 4
    assert result["series"][0]["values"] == [58.0, 59.0, 60.0]


def test_series_rolling_normalized_clock_and_low_coverage(store):
    normal = series(
        store[1],
        Selection(metrics=["hr_mean"], mode="normalized", rolling="7", **custom(8, 10)),
    )["series"][0]
    sd = (2 / 3) ** 0.5  # population SD of 58, 59, 60
    assert normal["rolling"]["values"] == pytest.approx([(m - 59) / sd for m in (55, 56.4, 57)])
    early = series(store[1], Selection(metrics=["hr_mean"], rolling="7", **custom(1, 4)))
    assert early["series"][0]["rolling"]["counts"] == [1, 2, 2, 3]
    assert early["series"][0]["rolling"]["values"] == [None] * 4
    month = series(store[1], Selection(metrics=["hr_mean"], rolling="30", range="all"))
    assert month["series"][0]["rolling"]["values"] == [None] * 10
    assert month["series"][0]["rolling"]["counts"][-1] == 8
    clock = series(store[1], Selection(metrics=["onset_minute"], rolling="7", range="all"))
    assert clock["series"][0]["rolling"]["values"] is None
    assert clock["series"][0]["rolling"]["reason"] == "Not available for clock times"
    flat = series(store[1], Selection(metrics=["resp_mean"], mode="normalized", rolling="7"))
    assert set(flat["series"][0]["rolling"]["values"]) == {None}
    assert series(store[1], Selection(metrics=["hr_mean"]))["series"][0]["rolling"] is None


def test_correlation_pairs_exclusions_and_reference(store):
    result = correlation(store[1], Pairing(x="hr_mean", y="hrv_mean", range="all"))
    paired = [d for d in DAYS if d in HRV]
    assert [p["date"] for p in result["pairs"]] == [f"2026-10-{d:02d}" for d in paired]
    assert result["n"] == 7 and result["days"] == 10
    assert result["excluded"] == {"missing_x": 0, "missing_y": 1, "neither": 2}
    reference = statistics.correlation([HR[d] for d in paired], [HRV[d] for d in paired])
    assert result["r"] == pytest.approx(reference, abs=1e-12)
    assert result["reason"] is None
    assert result["x"]["unit"] == "bpm" and result["y"]["unit"] == "ms"
    assert "not evidence of cause" in result["method"]


def test_correlation_unavailable_constant_sparse_and_empty(store, scratch):
    sparse = correlation(store[1], Pairing(x="hr_mean", y="hrv_mean", **custom(8, 9)))
    assert sparse["n"] == 2 and sparse["r"] is None
    assert sparse["reason"] == "Unavailable: fewer than 3 paired nights"
    flat = correlation(store[1], Pairing(x="hr_mean", y="resp_mean", range="all"))
    assert flat["n"] == 8 and flat["r"] is None and "no variation" in flat["reason"]
    (scratch / "empty").mkdir()
    _, empty_engine = new_store(scratch / "empty")
    empty = correlation(empty_engine, Pairing(x="hr_mean", y="hrv_mean"))
    assert empty["n"] == 0 and empty["r"] is None and empty["pairs"] == []
    empty_engine.dispose()
    for bad in [
        {"x": "hr_mean", "y": "hr_mean"},
        {"x": "onset_minute", "y": "hr_mean"},
        {"x": "hr_mean", "y": "unknown"},
        {"x": "hr_mean", "y": "hrv_mean", "range": "custom", "start": "2026-10-09"},
    ]:
        with pytest.raises(ValueError):
            Pairing(**bad)


def test_correlation_endpoint_and_rolling_preset(store):
    data, _ = store
    app = create_app(chart_data=data)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1)) as c:
        body = {"x": "hr_mean", "y": "hrv_mean", "range": "all"}
        assert c.post("/api/v1/analytics/correlation", json=body).status_code == 403
        ok = c.post("/api/v1/analytics/correlation", json=body, headers=HEADERS)
        assert ok.status_code == 200 and ok.json()["n"] == 7
        assert ok.json()["synthetic"] is False
        assert ok.headers["cache-control"] == "no-store"
        clock = {**body, "x": "wake_minute"}
        assert (
            c.post("/api/v1/analytics/correlation", json=clock, headers=HEADERS).status_code == 422
        )
        preset = {"metrics": ["hr_mean"], "rolling": "30", "name": "Trend"}
        saved = c.put("/api/v1/presets/new", json=preset, headers=HEADERS).json()
        assert saved["rolling"] == "30"
        assert c.get("/api/v1/presets").json()[0]["rolling"] == "30"
        bad = {**preset, "name": "Other", "rolling": "14"}
        assert c.put("/api/v1/presets/new", json=bad, headers=HEADERS).status_code == 422


def test_wake_dates_are_consecutive_calendar_days(store):
    dates = series(store[1], Selection(metrics=["hr_mean"], range="all"))["dates"]
    first = date.fromisoformat(dates[0])
    assert dates == [(first + timedelta(days=i)).isoformat() for i in range(10)]
