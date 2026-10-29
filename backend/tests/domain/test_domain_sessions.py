import json
from datetime import UTC, date, datetime, timedelta

from app.domain.config import DeriveConfig
from app.domain.sessions import StageRow, build_candidates, local_minute, select_nights
from app.ingest.parse import parse_payload
from factories import PHONE, PLAN, WATCH, block, nights_payload, sleep_rows, utc

CFG = DeriveConfig()


def rows(raw: list[dict[str, object]]) -> list[StageRow]:
    parsed = parse_payload({"data": {"metrics": [block("sleep_analysis", "hr", raw)]}})
    return [
        StageRow(
            i + 1,
            o.source,
            o.start_utc,
            o.end_utc,
            o.start_offset_min,
            o.end_offset_min,
            o.stage or "",
            o.qty,
        )
        for i, o in enumerate(parsed.observations)
    ]


def nights(raw: list[dict[str, object]]):  # type: ignore[no-untyped-def]
    return select_nights(build_candidates(rows(raw), CFG), CFG)


def test_standard_night_crosses_midnight_and_uses_wake_date() -> None:
    # Hand calculation: Core 120+90+60, Deep 60, REM 60+60 = 450 min; interior Awake 10 min.
    result = nights(sleep_rows(utc(date(2026, 1, 9), 23)))
    assert list(result) == [date(2026, 1, 10)]
    night = result[date(2026, 1, 10)]
    selected = night.selected
    assert (selected.core, selected.deep, selected.rem, selected.awake) == (
        270 * 60,
        60 * 60,
        120 * 60,
        10 * 60,
    )
    assert selected.asleep == 450 * 60
    assert night.flags == ()
    assert local_minute(selected.start, selected.start_offset) == 23 * 60
    assert local_minute(selected.end, selected.end_offset) == (23 * 60 + 460) % 1440


def test_leading_and_trailing_awake_are_trimmed() -> None:
    plan = [("Awake", 20), *PLAN, ("Awake", 15)]
    selected = nights(sleep_rows(utc(date(2026, 1, 9), 22, 40), plan))[date(2026, 1, 10)].selected
    assert selected.awake == 10 * 60
    assert local_minute(selected.start, selected.start_offset) == 23 * 60


def test_gap_threshold_boundary_and_gaps_count_as_neither() -> None:
    start = utc(date(2026, 1, 9), 22)
    first = sleep_rows(start, [("Core", 200)])
    for gap, joined in ((30, True), (31, False)):
        second = sleep_rows(start + timedelta(minutes=200 + gap), [("Core", 200)])
        candidates = build_candidates(rows(first + second), CFG)
        assert (len(candidates) == 1) is joined
        if joined:
            assert candidates[0].asleep == 400 * 60 and candidates[0].awake == 0


def test_naps_are_ignored_and_greatest_sleep_wins() -> None:
    night = sleep_rows(utc(date(2026, 1, 9), 23))
    evening = sleep_rows(utc(date(2026, 1, 10), 17), [("Core", 190)])
    nap = sleep_rows(utc(date(2026, 1, 10), 13), [("Core", 40)])
    result = nights(night + evening + nap)
    assert result[date(2026, 1, 10)].selected.asleep == 450 * 60
    assert result[date(2026, 1, 10)].flags == ("multiple_candidates",)  # evening block, same date
    assert nights(nap) == {}  # nap-only day: no night


def test_two_qualifying_blocks_on_one_wake_date_flag_ambiguity_and_ties() -> None:
    early = sleep_rows(utc(date(2026, 1, 10), 0, 30), [("Core", 240)])
    late = sleep_rows(utc(date(2026, 1, 10), 6), [("Core", 240)])
    night = nights(early + late)[date(2026, 1, 10)]
    assert {"multiple_candidates", "tie"} <= set(night.flags)
    assert night.selected.start == int(utc(date(2026, 1, 10), 0, 30).timestamp())
    longer = sleep_rows(utc(date(2026, 1, 10), 6), [("Core", 300)])
    assert nights(early + longer)[date(2026, 1, 10)].selected.asleep == 300 * 60


def test_apple_watch_is_preferred_over_larger_other_source() -> None:
    watch = sleep_rows(utc(date(2026, 1, 9), 23), [("Core", 240)])
    phone = sleep_rows(utc(date(2026, 1, 9), 23), [("Core", 480)], PHONE)
    night = nights(watch + phone)[date(2026, 1, 10)]
    assert night.selected.source == WATCH and "other_source_ignored" in night.flags
    assert "non_preferred_source" in nights(phone)[date(2026, 1, 10)].flags


def test_overlapping_stage_rows_are_not_double_counted_and_flagged() -> None:
    base = sleep_rows(utc(date(2026, 1, 9), 23), [("Core", 240)])
    overlap = sleep_rows(utc(date(2026, 1, 10), 1), [("Deep", 120)])
    night = nights(base + overlap)[date(2026, 1, 10)]
    assert night.selected.asleep == 240 * 60  # union of 23:00-03:00, not 6 hours
    assert night.selected.deep == 120 * 60 and night.selected.core == 120 * 60
    assert "overlapping_stages" in night.flags


def test_fall_back_interval_and_night_have_positive_elapsed_time() -> None:
    sample = {
        "start": "2026-10-25 01:48:29 +0100",
        "end": "2026-10-25 01:12:31 +0000",
        "value": "Core",
        "source": WATCH,
    }
    row = rows([sample])[0]
    assert row.end - row.start == 1442  # not negative 36 minutes
    start = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)  # 23:00 BST
    selected = nights(sleep_rows(start, [("Core", 480)]))[date(2026, 10, 25)].selected
    assert selected.asleep == 8 * 3600
    assert (selected.start_offset, selected.end_offset) == (60, 0)
    assert local_minute(selected.end, selected.end_offset) == 6 * 60


def test_spring_forward_night() -> None:
    start = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)  # clocks go forward at 01:00 GMT
    selected = nights(sleep_rows(start, [("Core", 420)]))[date(2026, 3, 29)].selected
    assert selected.asleep == 7 * 3600
    assert (selected.start_offset, selected.end_offset) == (0, 60)
    assert local_minute(selected.end, selected.end_offset) == 7 * 60


def test_qty_cross_check_flags_mismatch() -> None:
    good = sleep_rows(utc(date(2026, 1, 9), 23), [("Core", 240)])
    bad = [{**good[0], "qty": 3.0}]
    assert nights(good)[date(2026, 1, 10)].flags == ()
    assert "qty_mismatch" in nights(bad)[date(2026, 1, 10)].flags


def test_factory_payload_is_valid() -> None:
    parsed = parse_payload(json.loads(nights_payload(date(2026, 1, 10), 2)))
    assert not parsed.rejected and not parsed.unmapped_metrics
