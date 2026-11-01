"""Analytics period summary (U05) against hand-calculated references on a synthetic store."""

from datetime import date
from pathlib import Path

import pytest
from app.analytics.api import Window
from app.analytics.summary import _clock, summary
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient

from backend.tests.factories import merge, new_store, night_blocks, payload

HEADERS = {"origin": "http://localhost", "x-sleepiq-request": "charts"}
SHORT = [("Core", 100), ("Awake", 20), ("Deep", 40), ("REM", 60), ("Core", 100)]


@pytest.fixture
def store(scratch: Path):
    # Wake dates: 8 Oct (previous period), 10, 12 and 13 Oct. 9, 11 and 14 Oct are unrecorded.
    # night_blocks starts the session on the day before its argument, so an after-midnight onset
    # for the 12 Oct night passes 13 Oct.
    data, engine = new_store(scratch)
    groups = [
        night_blocks(date(2026, 10, 8), hr=40, hrv=30),
        night_blocks(date(2026, 10, 10), onset=(23, 30), hr=50, hrv=40),
        night_blocks(date(2026, 10, 13), onset=(0, 30), plan=SHORT, hr=60, hrv=None),
        night_blocks(date(2026, 10, 13), onset=(23, 0), hr=70, hrv=60),
    ]
    import_bytes(engine, data, payload(merge(*groups)))
    yield data, engine
    engine.dispose()


def window(start: str, end: str) -> Window:
    return Window(range="custom", start=date.fromisoformat(start), end=date.fromisoformat(end))


def test_period_means_stages_and_clock_match_hand_calculation(store):
    _, engine = store
    result = summary(engine, window("2026-10-10", "2026-10-14"))
    assert (result["start"], result["end"], result["days"], result["nights"]) == (
        "2026-10-10",
        "2026-10-14",
        5,
        3,
    )
    m = result["metrics"]
    # Default plan: 450 min asleep (Core 270, Deep 60, REM 120) and 10 min interior Awake.
    # Short plan: 300 min asleep (Core 200, Deep 40, REM 60) and 20 min Awake.
    assert m["asleep_s"]["mean"] == pytest.approx((7.5 + 5 + 7.5) / 3)
    assert m["asleep_s"]["n"] == 3 and m["asleep_s"]["min"] == pytest.approx(5)
    assert m["hr_mean"]["mean"] == pytest.approx(60) and m["hr_mean"]["n"] == 3
    # HRV is missing on 12 Oct: excluded, not counted as zero.
    assert m["hrv_mean"]["mean"] == pytest.approx(50) and m["hrv_mean"]["n"] == 2
    assert m["efficiency"]["mean"] == pytest.approx((450 / 460 + 300 / 320 + 450 / 460) / 3 * 100)
    # Previous period: 5 to 9 Oct holds only 8 Oct (HR 40, HRV 30).
    assert result["previous"] == {
        "start": "2026-10-05",
        "end": "2026-10-09",
        "days": 5,
        "nights": 1,
    }
    assert m["hr_mean"]["previous_mean"] == pytest.approx(40) and m["hr_mean"][
        "delta"
    ] == pytest.approx(20)
    assert m["hrv_mean"]["delta"] == pytest.approx(20)
    stages = result["stages"]
    minutes = {"deep": 160 / 3, "rem": 300 / 3, "core": 740 / 3, "awake": 40 / 3}
    total = sum(minutes.values())
    for name, value in minutes.items():
        assert stages[name]["minutes"] == pytest.approx(value)
        assert stages[name]["percent"] == pytest.approx(value / total * 100)
    # Onsets 23:30, 00:30, 23:00 -> unwrapped 1380, 1410, 1470 -> quartiles 1395, 1410, 1440 (00:00).
    assert result["clock"]["onset"] == {
        "n": 3,
        "q1": pytest.approx(1395),
        "median": pytest.approx(1410),
        "q3": pytest.approx(0),
    }
    # Wakes 07:10, 05:50, 06:40 -> 350, 400, 430.
    assert result["clock"]["wake"] == {
        "n": 3,
        "q1": pytest.approx(375),
        "median": pytest.approx(400),
        "q3": pytest.approx(415),
    }
    # Scores need consistency history, so no night here has an overall score: n=0, never 0 points.
    assert m["overall"]["n"] == 0 and m["overall"]["mean"] is None
    assert result["ceiling"] == pytest.approx(100)


def test_previous_period_without_recorded_nights_gives_null_delta(store):
    _, engine = store
    result = summary(engine, window("2026-10-12", "2026-10-13"))
    assert result["previous"] == {
        "start": "2026-10-10",
        "end": "2026-10-11",
        "days": 2,
        "nights": 1,
    }
    empty_before = summary(engine, window("2026-10-08", "2026-10-10"))
    assert empty_before["previous"]["nights"] == 0
    for item in empty_before["metrics"].values():
        assert item["delta"] is None and item["previous_mean"] is None
    assert empty_before["metrics"]["hr_mean"]["mean"] == pytest.approx(45)
    all_history = summary(engine, Window(range="all"))
    assert (
        all_history["start"] == "2026-10-08" and all_history["metrics"]["hr_mean"]["delta"] is None
    )


def test_bedtimes_across_midnight_have_a_typical_time_of_midnight():
    assert _clock([1410, 30])["median"] == pytest.approx(0)  # 23:30 and 00:30 -> 00:00, not 12:00
    assert _clock([1410, 30])["q1"] == pytest.approx(1425) and _clock([1410, 30])[
        "q3"
    ] == pytest.approx(15)
    assert _clock([400]) == {"n": 1, "q1": 400, "median": 400, "q3": 400}
    assert _clock([]) == {"n": 0, "q1": None, "median": None, "q3": None}


def test_endpoint_boundary_and_range_limit(store, scratch: Path):
    data, _ = store
    good = {"range": "custom", "start": "2026-10-10", "end": "2026-10-14"}
    local = TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("127.0.0.1", 1)
    )
    ok = local.post("/api/v1/analytics/summary", json=good, headers=HEADERS)
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert ok.json()["nights"] == 3 and ok.json()["synthetic"] is False
    assert (
        local.post(
            "/api/v1/analytics/summary",
            json=good,
            headers={"origin": "http://evil.example", "x-sleepiq-request": "charts"},
        ).status_code
        == 403
    )
    assert (
        local.post(
            "/api/v1/analytics/summary", json=good, headers={"origin": "http://localhost"}
        ).status_code
        == 403
    )
    remote = TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("10.0.0.5", 1)
    )
    assert remote.post("/api/v1/analytics/summary", json=good, headers=HEADERS).status_code == 403
    too_long = {"range": "custom", "start": "1990-01-01", "end": "2026-10-14"}
    assert (
        local.post("/api/v1/analytics/summary", json=too_long, headers=HEADERS).status_code == 422
    )
    assert (
        local.post(
            "/api/v1/analytics/summary", json={**good, "metrics": ["x"]}, headers=HEADERS
        ).status_code
        == 422
    )
    (scratch / "empty").mkdir()
    empty, _ = new_store(scratch / "empty")
    blank = TestClient(
        create_app(chart_data=empty), base_url="http://localhost", client=("127.0.0.1", 1)
    )
    body = blank.post("/api/v1/analytics/summary", json={"range": "30"}, headers=HEADERS).json()
    assert body["nights"] == 0 and body["metrics"] == {} and body["stages"] is None
