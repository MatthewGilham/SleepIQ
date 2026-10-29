"""Latest-night dashboard read model against hand-derived synthetic references."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from app.analytics.dashboard import ceiling, dashboard
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient

from backend.tests.factories import merge, new_store, night_blocks, nights_payload, payload


def client(data: Path) -> TestClient:
    return TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("127.0.0.1", 50123)
    )


def test_ceiling_matches_pilot_documentation():
    assert ceiling() == pytest.approx(92.5)


def test_empty_store_has_no_latest_night(scratch: Path):
    _, engine = new_store(scratch)
    result = dashboard(engine, True)
    assert result["latest"] is None
    assert result["import"] == {"batches": 0, "last_received_utc": None, "nights": 0}
    assert result["trend"] == {"dates": [], "asleep_h": []}
    assert result["synthetic"] is True


def test_unscored_latest_night_is_still_shown(scratch: Path):
    # Fewer than seven prior nights: consistency unavailable, so no overall score; the night remains.
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 10, 26), 3))
    result = dashboard(engine, False)
    latest = result["latest"]
    assert latest["wake_date"] == "2026-10-28"
    assert latest["score"]["status"] == "insufficient_data"
    assert latest["score"]["overall"] is None
    assert any(m.startswith("consistency:") for m in latest["score"]["missing"])
    assert latest["asleep_s"] > 0 and latest["stages"]
    assert result["import"]["nights"] == 3 and result["import"]["batches"] == 1


def test_scored_night_stages_trend_and_missing_hrv(scratch: Path):
    data, engine = new_store(scratch)
    first = date(2026, 10, 1)
    groups = [night_blocks(first + timedelta(days=i)) for i in range(26)]
    groups.append(night_blocks(date(2026, 10, 28), hrv=None))
    import_bytes(engine, data, payload(merge(*groups)))
    result = dashboard(engine, False)
    latest = result["latest"]
    assert latest["wake_date"] == "2026-10-28"
    hrv = next(p for p in latest["physiology"] if p["id"] == "hrv")
    assert hrv["value"] is None and hrv["n"] == 0
    assert latest["score"]["overall"] is None and "overnight_hrv" in latest["score"]["missing"]
    assert latest["score"]["ceiling"] == pytest.approx(92.5)
    # Stage rows sum back to the recorded window and begin at session start.
    assert latest["stages"][0]["start_s"] == 0
    assert sum(s["duration_s"] for s in latest["stages"]) == latest["session_s"]
    assert latest["onset_local"].endswith("T23:00") and latest["wake_local"].startswith(
        "2026-10-28"
    )
    trend = result["trend"]
    assert len(trend["dates"]) == 30 and trend["dates"][-1] == "2026-10-28"
    assert trend["asleep_h"][-1] == pytest.approx(latest["asleep_s"] / 3600)
    assert trend["asleep_h"][-2] is None  # 27 Oct was not recorded: a gap, not zero
    assert trend["asleep_h"][-3] is not None


def test_endpoint_is_local_only_and_not_cached(scratch: Path):
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 10, 27), 2))
    api = client(data)
    ok = api.get("/api/v1/dashboard")
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert ok.json()["latest"]["wake_date"] == "2026-10-28"
    assert (
        api.get("/api/v1/dashboard", headers={"origin": "http://evil.example"}).status_code == 403
    )
    remote = TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("10.0.0.5", 1)
    )
    assert remote.get("/api/v1/dashboard").status_code == 403
    unconfigured = TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 1))
    assert unconfigured.get("/api/v1/dashboard").status_code == 503
