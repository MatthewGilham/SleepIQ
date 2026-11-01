import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.ingest import store
from factories import (
    block,
    merge,
    new_store,
    night_blocks,
    nights_payload,
    payload,
    point,
    span,
    utc,
)
from sqlalchemy import Engine, text

FIRST = date(2026, 1, 1)


def day(n: int) -> date:
    return FIRST + timedelta(days=n)


def scores(engine: Engine) -> dict[str, tuple[str, float | None, dict[str, object]]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT wake_date, status, overall, details_json FROM nightly_scores")
        )
        return {r[0]: (r[1], r[2], json.loads(r[3])) for r in rows}


def fresh(scratch: Path, name: str) -> tuple[Path, Engine]:
    (scratch / name).mkdir()
    return new_store(scratch / name)


def snapshot(engine: Engine) -> list[list[tuple[object, ...]]]:
    sql = (
        "SELECT * FROM nightly_metrics ORDER BY wake_date",
        "SELECT * FROM general_metrics ORDER BY local_date, metric",
        (
            "SELECT wake_date, status, overall, consistency, details_json FROM nightly_scores "
            "ORDER BY wake_date"
        ),
    )
    with engine.connect() as conn:
        # Column names remain stable when additive migrations append quality metadata.
        out = [
            [
                tuple(v for k, v in r._mapping.items() if k != "computed_utc")
                for r in conn.execute(text(q))
            ]
            for q in sql
        ]
    return out


def test_consistency_unlocks_after_seven_prior_nights_with_hand_calculated_score(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 10))
    result = scores(engine)
    for n in range(7):  # fewer than seven prior eligible nights
        status, overall, details = result[day(n).isoformat()]
        assert (status, overall) == ("insufficient_data", None)
        assert details["missing"] == ["consistency:insufficient_history"]
    status, overall, details = result[day(7).isoformat()]
    # Duration 87.5, consistency 100, Deep 60 min = 70, REM 120 min = 100, HR 52 = 60.
    assert status == "scored" and overall == pytest.approx(86.875, abs=1e-9)
    assert details["consistency"]["baseline_nights"] == 7  # type: ignore[index]
    assert details["consistency"]["provisional"] is True  # type: ignore[index]
    assert result[day(9).isoformat()][2]["consistency"]["baseline_nights"] == 9  # type: ignore[index]


def test_late_onset_lowers_consistency_by_the_approved_penalty(scratch: Path) -> None:
    data, engine = new_store(scratch)
    groups = [night_blocks(day(n)) for n in range(8)]
    groups.append(night_blocks(day(8), onset=(23, 20)))  # 20 minutes later; wake also 20 later
    store.import_bytes(engine, data, payload(merge(*groups)))
    status, overall, details = scores(engine)[day(8).isoformat()]
    assert status == "scored"
    assert details["consistency"]["onset_deviation_min"] == pytest.approx(20)  # type: ignore[index]
    assert details["consistency"]["wake_deviation_min"] == pytest.approx(20)  # type: ignore[index]
    assert overall == pytest.approx(21.875 + 25 * 0.9 + 14 + 20 + 6)  # consistency 90


def test_missing_hr_withholds_score_but_hrv_is_optional_and_metrics_remain(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    groups = [night_blocks(day(n)) for n in range(10)]
    groups[8] = night_blocks(day(8), hrv=None)
    groups[9] = night_blocks(day(9), hr=None)
    store.import_bytes(engine, data, payload(merge(*groups)))
    result = scores(engine)
    assert result[day(8).isoformat()][0] == "scored"
    assert result[day(8).isoformat()][2]["missing"] == []
    assert result[day(9).isoformat()][2]["missing"] == ["sleeping_hr"]
    assert result[day(7).isoformat()][0] == "scored"
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT hrv_mean, hrv_n, hr_mean, resp_mean FROM nightly_metrics "
                "WHERE wake_date = :d"
            ),
            {"d": day(8).isoformat()},
        ).one()
    assert row[:2] == (None, 0) and row[2] is not None and row[3] == pytest.approx(14.5)


def test_hr_is_labelled_simple_mean_with_sample_count(scratch: Path) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 1))
    with engine.connect() as conn:
        row = conn.execute(text("SELECT hr_mean, hr_n, hr_method FROM nightly_metrics")).one()
    # Samples every 60 min from minute 30 over 460 minutes: minutes 30, 90, ..., 450 (8 samples);
    # Avg = 52 + minute % 3 with minute % 3 == 0 for each, so the mean is exactly 52.
    assert row[0] == pytest.approx(52.0) and row[1] == 8 and row[2] == "simple_mean_fallback"


def test_incremental_rebuild_equals_clean_rebuild_for_backfill_and_gaps(scratch: Path) -> None:
    pieces = [
        nights_payload(day(0), 12),
        nights_payload(day(20), 15),  # gap, then later nights first
        nights_payload(day(12), 8),  # backfill fills the gap
        nights_payload(day(5), 20),  # overlapping resend
    ]
    data, engine = fresh(scratch, "inc")
    for piece in pieces:
        store.import_bytes(engine, data, piece)
    with engine.begin() as conn:
        conn.execute(text("UPDATE nightly_metrics SET computed_utc=0"))
    ref_data, ref = fresh(scratch, "clean")
    store.import_bytes(ref, ref_data, nights_payload(day(0), 35))
    assert snapshot(engine) == snapshot(ref)
    # The explicit clean rebuild of the incremental store changes nothing.
    from app.domain.rebuild import rebuild

    with engine.begin() as conn:
        rebuild(conn, None)
    assert snapshot(engine) == snapshot(ref)


def test_backfilling_old_history_updates_later_baselines_not_earlier_scores(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(day(10), 10))  # days 10-19, no history
    before = scores(engine)
    assert all(v[0] == "insufficient_data" for k, v in before.items() if k < day(17).isoformat())
    store.import_bytes(engine, data, nights_payload(day(0), 10))  # corrected/backfilled history
    after = scores(engine)
    assert after[day(10).isoformat()][0] == "scored"  # 10 prior nights now exist
    assert len(after) == 20


def test_no_future_leakage_adding_later_nights_never_changes_earlier_scores(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    groups = [night_blocks(day(n), onset=(23, 0) if n % 3 else (23, 40)) for n in range(40)]
    store.import_bytes(engine, data, payload(merge(*groups[:20])))
    early = scores(engine)
    store.import_bytes(engine, data, payload(merge(*groups[20:])))
    later = scores(engine)
    for key, value in early.items():
        assert later[key] == value, key


def test_possibly_incomplete_flag_clears_when_later_data_arrives_after_a_long_gap(
    scratch: Path,
) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 3))

    def flags() -> list[str]:
        with engine.connect() as conn:
            value = conn.execute(
                text("SELECT flags_json FROM nightly_metrics WHERE wake_date = :d"),
                {"d": day(2).isoformat()},
            ).scalar()
        return list(json.loads(str(value)))

    assert flags() == ["possibly_incomplete"]  # nothing after the wake time proves completeness
    store.import_bytes(engine, data, nights_payload(day(60), 2))
    assert flags() == []
    clean_data, clean = fresh(scratch, "clean")
    store.import_bytes(
        clean, clean_data, payload(merge(*[night_blocks(day(n)) for n in (0, 1, 2, 60, 61)]))
    )
    assert snapshot(engine) == snapshot(clean)


def test_revised_nights_are_excluded_from_the_consistency_baseline(scratch: Path) -> None:
    data, engine = new_store(scratch)
    store.import_bytes(engine, data, nights_payload(FIRST, 8))
    clean = scores(engine)[day(7).isoformat()][2]["consistency"]["baseline_nights"]  # type: ignore[index]
    assert clean == 7
    revised = night_blocks(day(3))
    for item in revised:
        if item["name"] == "heart_rate":
            item["data"][0]["Avg"] += 10  # type: ignore[index]
    store.import_bytes(engine, data, payload(revised))
    again = scores(engine)[day(7).isoformat()]
    assert again[2]["consistency"]["baseline_nights"] == 6  # type: ignore[index]
    assert again[0] == "insufficient_data"  # fewer than seven eligible nights


def test_physiology_counts_for_a_night_only_inside_its_sleep_window(scratch: Path) -> None:
    data, engine = new_store(scratch)
    night_start = utc(FIRST - timedelta(days=1), 23)
    extra = [
        block("heart_rate", "count/min", [point(utc(FIRST, 14), Avg=80, Min=70, Max=95)]),
        block("resting_heart_rate", "count/min", [span(utc(FIRST, 0), 24, qty=58)]),
        block("heart_rate_variability", "ms", [span(utc(FIRST, 12), 0.5, qty=30)]),
        block("apple_sleeping_wrist_temperature", "degC", [span(night_start, 7, qty=35.2)]),
    ]
    store.import_bytes(engine, data, payload(merge(night_blocks(FIRST), extra)))
    with engine.connect() as conn:
        night = conn.execute(
            text("SELECT hr_n, hrv_n, rhr_n, temp_n, temp_mean FROM nightly_metrics")
        ).one()
        general = {
            (r[0], r[1]): (r[2], r[3])
            for r in conn.execute(text("SELECT local_date, metric, mean, n FROM general_metrics"))
        }
    assert night[:3] == (8, 1, 0)  # daytime HR/HRV and the day-long RHR are not sleeping values
    assert night[3] == 1 and night[4] == pytest.approx(35.2)  # interval midpoint inside window
    assert general[("2026-01-01", "heart_rate")] == (80.0, 1)
    assert general[("2026-01-01", "heart_rate_variability")] == (30.0, 1)
    assert general[("2026-01-01", "resting_heart_rate")] == (58.0, 1)
    assert ("2026-01-01", "apple_sleeping_wrist_temperature") not in general


def test_naps_never_create_or_change_a_night(scratch: Path) -> None:
    data, engine = new_store(scratch)
    nap = block(
        "sleep_analysis",
        "hr",
        [
            {
                "start": "2026-01-01 13:00:00 +0000",
                "end": "2026-01-01 13:40:00 +0000",
                "value": "Core",
                "source": "Synthetic Apple Watch",
            }
        ],
    )
    store.import_bytes(engine, data, nights_payload(FIRST, 2))
    base = snapshot(engine)
    store.import_bytes(engine, data, payload([nap]))
    after = snapshot(engine)
    assert after[0] == base[0] and after[2] == base[2]


def test_dst_nights_keep_wall_clock_consistency_and_elapsed_hours(scratch: Path) -> None:
    data, engine = new_store(scratch)
    start = date(2026, 10, 18)  # nights straddle the 25 October fall-back
    groups = [night_blocks(start + timedelta(days=n), plan=[("Core", 480)]) for n in range(14)]
    store.import_bytes(engine, data, payload(merge(*groups)))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wake_date, asleep_s, onset_minute, wake_minute, start_offset_min, "
                "end_offset_min FROM nightly_metrics ORDER BY wake_date"
            )
        ).all()
    by_date = {r[0]: r for r in rows}
    changeover = by_date["2026-10-25"]
    assert changeover[1] == 8 * 3600  # elapsed time, though the clock repeats an hour
    assert (changeover[4], changeover[5]) == (60, 0)
    assert {r[2] for r in rows} == {23 * 60.0}  # same wall-clock bedtime throughout
    status = scores(engine)
    assert status["2026-10-25"][2]["consistency"]["available"] is True  # type: ignore[index]
