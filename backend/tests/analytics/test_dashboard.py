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


def test_physiology_cards_exclude_resting_heart_rate(scratch: Path):
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 10, 27), 2))
    ids = [p["id"] for p in dashboard(engine, False)["latest"]["physiology"]]
    assert ids == ["hr", "hrv", "resp", "temp"]


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


def gap_store(scratch: Path):
    """Stored nights on 1, 2 and 5 October (wake dates), so 3 and 4 October are unrecorded."""
    data, engine = new_store(scratch)
    groups = [night_blocks(date(2026, 10, d), hr=50 + d) for d in (1, 2, 5)]
    import_bytes(engine, data, payload(merge(*groups)))
    return data, engine


def test_default_is_latest_night_with_no_next(scratch: Path):
    data, _ = gap_store(scratch)
    body = client(data).get("/api/v1/dashboard").json()
    assert body["latest"]["wake_date"] == "2026-10-05"
    assert body["next_night"] is None and body["previous_night"] == "2026-10-02"


def test_neighbours_skip_unrecorded_days(scratch: Path):
    data, _ = gap_store(scratch)
    api = client(data)
    middle = api.get("/api/v1/dashboard?night=2026-10-02").json()
    assert middle["latest"]["wake_date"] == "2026-10-02"
    assert middle["previous_night"] == "2026-10-01" and middle["next_night"] == "2026-10-05"
    first = api.get("/api/v1/dashboard?night=2026-10-01").json()
    assert first["previous_night"] is None and first["next_night"] == "2026-10-02"
    # The night shown is the requested one, not the latest: its own heart rate (50 + day).
    hr = next(p for p in middle["latest"]["physiology"] if p["id"] == "hr")
    assert hr["value"] == pytest.approx(52)


def test_unknown_or_malformed_night_is_rejected_plainly(scratch: Path):
    data, _ = gap_store(scratch)
    api = client(data)
    missing = api.get("/api/v1/dashboard?night=2026-10-03")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "No sleep was recorded for that night"}
    for bad in ("2026-13-40", "abc"):
        response = api.get(f"/api/v1/dashboard?night={bad}")
        assert response.status_code == 422
        # Errors name the field and the problem only; no stored value or path is echoed.
        assert "52" not in response.text and str(data) not in response.text
        assert "heart" not in response.text.lower()
    (scratch / "empty").mkdir()
    empty_data, _ = new_store(scratch / "empty")
    assert client(empty_data).get("/api/v1/dashboard?night=2026-10-01").status_code == 404


def test_trend_ends_on_requested_night(scratch: Path):
    data, engine = new_store(scratch)
    import_bytes(engine, data, nights_payload(date(2026, 9, 1), 40))
    body = client(data).get("/api/v1/dashboard?night=2026-09-20").json()
    trend = body["trend"]
    assert trend["dates"][-1] == "2026-09-20" and len(trend["dates"]) == 30
    assert max(trend["dates"]) == "2026-09-20"  # no later nights
    assert trend["asleep_h"][-1] == pytest.approx(body["latest"]["asleep_s"] / 3600)


def test_night_variant_keeps_local_origin_and_no_store_rules(scratch: Path):
    data, _ = gap_store(scratch)
    url = "/api/v1/dashboard?night=2026-10-02"
    ok = client(data).get(url)
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert client(data).get(url, headers={"origin": "http://evil.example"}).status_code == 403
    remote = TestClient(
        create_app(chart_data=data), base_url="http://localhost", client=("10.0.0.5", 1)
    )
    assert remote.get(url).status_code == 403
    missing = client(data).get("/api/v1/dashboard?night=2026-10-03")
    assert missing.headers["cache-control"] == "no-store"
