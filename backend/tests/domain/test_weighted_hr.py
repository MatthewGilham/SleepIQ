"""Independent duration/quality references for P34; synthetic inputs only."""

from datetime import datetime
from math import nan

import pytest
from app.domain.heart_rate import HRReading, sleeping_hr

WATCH = "Synthetic Watch"


def point(t, value=50, source=WATCH):
    return HRReading(t, t, value, source)


def test_irregular_points_weight_elapsed_seconds_not_sample_count():
    result = sleeping_hr([point(0, 50), point(1200, 60), point(1800, 80)], 0, 1800, WATCH)
    # 20 min at mean 55, then 10 min at mean 70. Sample mean would be 190/3.
    assert result.mean == 60
    assert result.mean != pytest.approx(190 / 3)
    assert (result.n, result.eligible_n, result.contributing_n) == (3, 3, 3)
    assert result.method == "time_weighted_linear" and result.fallback_reason is None
    assert (result.covered_s, result.window_s, result.coverage) == (1800, 1800, 1)


def test_constant_and_linear_ramps_are_invariant_to_extra_points():
    for values, expected in [([50, 50, 50, 50], 50), ([40, 41, 50, 70], 55)]:
        readings = [point(t, v) for t, v in zip([0, 60, 600, 1800], values, strict=True)]
        result = sleeping_hr(readings, 0, 1800, WATCH)
        assert result.mean == expected
        assert sleeping_hr(list(reversed(readings)), 0, 1800, WATCH) == result


@pytest.mark.parametrize(
    "duration,method,reason",
    [
        (1800, "time_weighted_linear", None),
        (1801, "simple_mean_fallback", "long_gaps"),
    ],
)
def test_maximum_gap_boundary(duration, method, reason):
    result = sleeping_hr([point(0, 50), point(duration, 60)], 0, duration, WATCH)
    assert result.method == method and result.fallback_reason == reason
    assert result.covered_s == (1800 if duration == 1800 else 0)
    assert result.mean == 55


@pytest.mark.parametrize(
    "last,method,reason",
    [
        (7000, "time_weighted_linear", None),
        (6999, "simple_mean_fallback", "low_coverage"),
    ],
)
def test_coverage_exactly_seventy_percent_and_one_second_below(last, method, reason):
    points = [point(t) for t in [0, 1000, 2000, 3000, 4000, 5000, 6000, last]]
    result = sleeping_hr(points, 0, 10000, WATCH)
    assert (result.method, result.fallback_reason) == (method, reason)
    assert result.covered_s == last and result.coverage == last / 10000


def test_disjoint_segments_exclude_long_gap_but_include_it_in_coverage():
    result = sleeping_hr(
        [point(0, 40), point(1800, 40), point(3700, 80), point(5500, 80)], 0, 5500, WATCH
    )
    assert result.covered_s == 3600 and result.coverage == 3600 / 5500
    assert result.fallback_reason == "low_coverage" and result.mean == 60
    assert result.contributing_n == 4


def test_uncovered_edges_and_outside_points_are_not_extrapolated():
    result = sleeping_hr(
        [point(-1, 200), point(100, 50), point(900, 70), point(1001, 200)], 0, 1000, WATCH
    )
    assert result.mean == 60 and result.eligible_n == 2
    assert result.covered_s == 800 and result.coverage == 0.8


@pytest.mark.parametrize(
    "readings,mean,n,reason",
    [
        ([], None, 0, None),
        ([point(100, 57)], 57, 1, "insufficient_points"),
        ([point(0, 50), point(4000, 70)], 60, 2, "long_gaps"),
    ],
)
def test_empty_single_and_long_gap_readings(readings, mean, n, reason):
    result = sleeping_hr(readings, 0, 4000, WATCH)
    assert (result.mean, result.n, result.fallback_reason) == (mean, n, reason)
    assert result.coverage == 0 and result.contributing_n == 0
    assert result.method == ("simple_mean_fallback" if n else None)


def test_exact_sleep_source_preferred_and_other_stream_never_connected():
    result = sleeping_hr(
        [point(0, 40), point(1200, 60), point(600, 200, "Other Watch")], 0, 1200, WATCH
    )
    assert result.mean == 50 and result.n == 2 and result.eligible_n == 3


def test_unique_watch_stream_used_if_sleep_source_has_no_hr():
    result = sleeping_hr(
        [point(0, 40), point(1200, 60), point(600, 200, "Phone")], 0, 1200, "Different sleep source"
    )
    assert result.mean == 50 and result.n == 2


@pytest.mark.parametrize(
    "sources,sleep_source",
    [
        (["Watch A", "Watch B"], "Unmatched"),
        (["Phone", "Phone"], "Unmatched"),
        (["", ""], ""),
    ],
)
def test_ambiguous_stream_falls_back_without_claiming_coverage(sources, sleep_source):
    result = sleeping_hr(
        [point(0, 40, sources[0]), point(1200, 60, sources[1])], 0, 1200, sleep_source
    )
    assert result.mean == 50 and result.n == 2
    assert result.fallback_reason == "ambiguous_source"
    assert result.covered_s is result.coverage is result.contributing_n is None


def test_same_instant_same_value_collapses_only_for_integration():
    readings = [point(0, 40), point(0, 40), point(1200, 60)]
    result = sleeping_hr(readings, 0, 1200, WATCH)
    assert result.mean == 50 and (result.n, result.eligible_n) == (2, 3)
    # On fallback the original eligible rows still contribute to the old arithmetic mean.
    fallback = sleeping_hr(readings, 0, 4000, WATCH)
    assert fallback.mean == pytest.approx(140 / 3) and fallback.n == 3


def test_unequal_same_instant_values_force_fallback_before_point_count():
    result = sleeping_hr([point(0, 40), point(0, 60)], 0, 1200, WATCH)
    assert result.mean == 50 and result.fallback_reason == "ambiguous_timestamp"
    assert result.coverage is None


def test_nonpoint_interval_midpoint_and_reason_precedence():
    result = sleeping_hr(
        [HRReading(-100, 100, 40, "Phone"), point(1200, 60, "Other")], 0, 1200, WATCH
    )
    assert result.mean == 50 and result.fallback_reason == "unsupported_interval"
    assert result.coverage is None
    outside = sleeping_hr([HRReading(-4000, -1, 200, WATCH), point(0), point(1200)], 0, 1200, WATCH)
    assert outside.mean == 50 and outside.eligible_n == 2


def test_invalid_values_never_enter_the_integral_or_fallback():
    result = sleeping_hr(
        [point(0), point(1200), point(100, nan), point(200, 0), point(300, 251)], 0, 1200, WATCH
    )
    assert result.mean == 50 and result.eligible_n == 2


@pytest.mark.parametrize(
    "first,last",
    [
        ("2026-10-25T01:50:00+01:00", "2026-10-25T01:10:00+00:00"),
        ("2026-03-29T00:50:00+00:00", "2026-03-29T02:10:00+01:00"),
        ("2026-01-01T23:50:00+00:00", "2026-01-02T00:10:00+00:00"),
    ],
)
def test_dst_midnight_and_mixed_offsets_use_elapsed_seconds(first, last):
    start, end = [int(datetime.fromisoformat(v).timestamp()) for v in (first, last)]
    result = sleeping_hr([point(start, 50), point(end, 60)], start, end, WATCH)
    assert result.mean == 55 and result.covered_s == 1200


@pytest.mark.parametrize("start,end", [(0, 0), (1, 0)])
def test_invalid_window_rejected(start, end):
    with pytest.raises(ValueError, match="window"):
        sleeping_hr([], start, end, WATCH)
