"""Physiology attribution by interval midpoint, including intervals far longer than the night."""

from datetime import date

from app.domain.rebuild import rebuild
from app.ingest.store import import_bytes
from sqlalchemy import text

from backend.tests.factories import block, merge, new_store, night_blocks, payload, span, utc


def test_long_interval_counts_when_midpoint_is_inside_the_night(tmp_path):
    data, engine = new_store(tmp_path)
    night = night_blocks(date(2026, 1, 10), hrv=None)  # session 23:00 on the 9th, ~8 h
    # 18:00 on the 9th for 12 h: starts 5 h before the session, midpoint 00:00 is inside it.
    long_hrv = [block("heart_rate_variability", "ms", [span(utc(date(2026, 1, 9), 18), 12, qty=40)])]
    # Midpoint 12:00 on the 10th is after the night, so it must not be counted.
    outside = [block("heart_rate_variability", "ms", [span(utc(date(2026, 1, 10), 6), 12, qty=90)])]
    import_bytes(engine, data, payload(merge(night, long_hrv, outside)))
    with engine.begin() as conn:
        rebuild(conn)
        row = conn.execute(text("SELECT hrv_mean, hrv_n FROM nightly_metrics")).one()
    engine.dispose()
    assert row == (40.0, 1)
