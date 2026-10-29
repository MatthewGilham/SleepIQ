"""Synthetic performance calibration (R01). Builds a throwaway store; never touches real data.

Seeds ~5 years of nights and ~1 million physiology observations by direct bulk insert, then
times a clean rebuild, an incremental import and the browser-facing API calls. Prints a table
of measured seconds; compare against the proposed budgets in docs/TESTING.md.
"""

import argparse
import gc
import platform
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from app.domain.rebuild import rebuild
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.tests.factories import new_store, night_blocks, payload

HEADERS = {"origin": "http://localhost", "x-sleepiq-request": "charts"}
# Seconds. Calibrated 2026-10-29 on the owner's PC (see docs/TESTING.md); about 10x measured headroom.
BUDGETS = {
    "dashboard": 2.0,
    "chart series": 1.0,
    "incremental import": 5.0,
    "clean rebuild": 60.0,
}
STAGES = [("Core", 100), ("Deep", 50), ("Core", 90), ("REM", 60), ("Core", 80), ("Awake", 10), ("REM", 40)]


def seed(engine, nights: int, hr_per_night: int, last: date) -> int:
    rows = []
    n = 0
    first = last - timedelta(days=nights - 1)
    for i in range(nights):
        wake = first + timedelta(days=i)
        start = int(datetime(wake.year, wake.month, wake.day, tzinfo=UTC).timestamp()) - 3600
        t = start
        for stage, minutes in STAGES:
            end = t + minutes * 60
            rows.append(("sleep_analysis", t, end, stage, minutes / 60, None, None, None))
            t = end
        total = (t - start) // 60
        for k in range(hr_per_night):
            when = start + (k * total * 60) // hr_per_night
            rows.append(("heart_rate", when, when, None, None, 50 + k % 9, 47, 58))
        for k in range(20):
            when = start + k * 1200
            rows.append(("heart_rate_variability", when, when + 1800, None, 30 + (i + k) % 25, None, None, None))
        for k in range(10):
            when = start + k * 2400
            rows.append(("respiratory_rate", when, when, None, 13 + k % 3, None, None, None))
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO import_batches (sha256, received_utc, byte_count, parser_version, summary_json) "
                "VALUES (:d, 0, 0, 'perf', '{}')"
            ),
            {"d": "0" * 64},
        )
        raw = conn.connection.driver_connection
        raw.executemany(
            "INSERT INTO observations (batch_id, metric, source, start_utc, end_utc, start_offset_min, "
            "end_offset_min, stage, qty, avg, min, max, has_heartbeat_series, fingerprint, status) "
            "VALUES (1, ?, 'Watch', ?, ?, 0, 0, ?, ?, ?, ?, ?, 0, ?, 'active')",
            [(m, s, e, st, q, a, lo, hi, f"perf-{j}") for j, (m, s, e, st, q, a, lo, hi) in enumerate(rows)],
        )
        n = len(rows)
    return n


def timed(label: str, results: list, fn):
    started = time.perf_counter()
    value = fn()
    results.append((label, time.perf_counter() - started))
    print(f"{results[-1][1]:9.3f} s  {label}", flush=True)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nights", type=int, default=1826)
    parser.add_argument("--hr-per-night", type=int, default=480)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--enforce", action="store_true", help="exit 1 if a budget is exceeded")
    args = parser.parse_args()
    results: list[tuple[str, float]] = []
    with tempfile.TemporaryDirectory(prefix="sleepiq-perf-", ignore_cleanup_errors=True) as scratch:
        data, engine = new_store(Path(scratch))
        last = date(2026, 10, 28)
        count = timed("seed observations (bulk insert)", results, lambda: seed(engine, args.nights, args.hr_per_night, last))
        def clean_rebuild():
            with engine.begin() as conn:
                rebuild(conn)
        timed("clean rebuild, all nights", results, clean_rebuild)
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT count(*) FROM nightly_metrics")).scalar_one()
        new_night = payload(night_blocks(last + timedelta(days=1)))
        timed("incremental import of one night", results, lambda: import_bytes(engine, data, new_night))
        app = create_app(chart_data=data)
        body = {"metrics": ["asleep_s", "hr_mean", "hrv_mean", "efficiency"], "range": "all"}
        with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50123)) as client:
            calls = {
                "dashboard (first request)": lambda: client.get("/api/v1/dashboard", headers=HEADERS),
                "chart series, all 5 years": lambda: client.post("/api/v1/analytics/timeseries", json=body, headers=HEADERS),
                "chart series, 30 days": lambda: client.post("/api/v1/analytics/timeseries", json={**body, "range": "30"}, headers=HEADERS),
            }
            for label, call in calls.items():
                for attempt in range(args.repeat):
                    started = time.perf_counter()
                    response = call()
                    elapsed = time.perf_counter() - started
                    if response.status_code != 200:
                        print(f"FAIL {label}: HTTP {response.status_code} {response.text[:200]}")
                        return 1
                    results.append((f"{label} [{attempt + 1}]", elapsed))
        engine.dispose()
        del app
        gc.collect()
    print(f"python {platform.python_version()} on {platform.platform()}, {platform.processor()[:60]}")
    print(f"workload: {count:,} observations, {stored:,} stored nights")
    for label, seconds in results:
        print(f"{seconds:9.3f} s  {label}")
    failed = [
        f"{label}: {seconds:.3f} s > {limit} s"
        for label, seconds in results
        for prefix, limit in BUDGETS.items()
        if label.startswith(prefix) and seconds > limit
    ]
    for line in failed:
        print("OVER BUDGET", line)
    return 1 if failed and args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
