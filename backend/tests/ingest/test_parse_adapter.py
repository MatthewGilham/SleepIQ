import json
from datetime import date

import pytest
from app.ingest.parse import UnsupportedExport, parse_payload
from factories import WATCH, block, point, utc


def parse(*blocks: dict[str, object]):  # type: ignore[no-untyped-def]
    return parse_payload({"data": {"metrics": list(blocks)}})


def test_all_six_metric_shapes_are_accepted() -> None:
    t = utc(date(2026, 1, 10), 3)
    result = parse(
        block("sleep_analysis", "hr", [{**point(t), "end": point(t)["start"], "value": "Core"}]),
        block("heart_rate", "count/min", [point(t, Avg=50, Min=45, Max=60)]),
        block("heart_rate_variability", "ms", [point(t, qty=40, heartbeatSeries=[{"x": 1}])]),
        block("respiratory_rate", "count/min", [point(t, qty=14)]),
        block("resting_heart_rate", "count/min", [point(t, qty=55)]),
        block("apple_sleeping_wrist_temperature", "degC", [point(t, qty=35.5)]),
    )
    # Zero-length sleep stage rows are invalid; every other metric is accepted.
    assert result.rejected == {"sleep_analysis:interval": 1}
    assert len(result.observations) == 5
    assert [o.has_heartbeat_series for o in result.observations] == [
        False,
        True,
        False,
        False,
        False,
    ]


def test_heart_rate_uses_avg_and_never_qty() -> None:
    t = utc(date(2026, 1, 10), 3)
    assert not parse(block("heart_rate", "count/min", [point(t, qty=60)])).observations
    row = parse(block("heart_rate", "count/min", [point(t, Avg=61.5, Min=58, Max=70)]))
    assert (row.observations[0].avg, row.observations[0].qty) == (61.5, None)
    assert (row.observations[0].minimum, row.observations[0].maximum) == (58, 70)


def test_rows_are_rejected_visibly_without_blocking_valid_rows() -> None:
    t = utc(date(2026, 1, 10), 3)
    good = point(t, qty=14)
    result = parse(
        block(
            "respiratory_rate",
            "count/min",
            [
                good,
                point(t, qty=999),  # implausible
                point(t, qty=float("nan")),
                {"start": "2026-01-10 03:00:00", "end": "2026-01-10 03:00:00", "qty": 14},
                "not an object",
                {**good, "end": "2026-01-10 02:00:00 +0000"},  # negative interval
            ],
        ),
        block("heart_rate", "bpm", [point(t, Avg=60)]),  # unexpected units
        block("steps", "count", [{"x": 1}, {"x": 2}]),  # unmapped, inventoried
    )
    assert len(result.observations) == 1
    assert result.rejected == {
        "respiratory_rate:implausible": 1,
        "respiratory_rate:number": 1,
        "respiratory_rate:timestamp": 1,
        "respiratory_rate:shape": 1,
        "respiratory_rate:interval": 1,
        "unexpected_units": 1,
    }
    assert result.unmapped_metrics == {"steps": 2}


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"data": []},
        {"data": {"metrics": "x"}},
        {"data": {"metrics": [1]}},
        {"data": {"metrics": [{"name": "heart_rate", "data": "x"}]}},
    ],
)
def test_unsupported_envelopes_are_refused(payload: object) -> None:
    with pytest.raises(UnsupportedExport):
        parse_payload(payload)


def test_offsets_and_instants_are_preserved() -> None:
    result = parse(
        block(
            "sleep_analysis",
            "hr",
            [
                {
                    "start": "2026-10-25 01:48:29 +0100",
                    "end": "2026-10-25 01:12:31 +0000",
                    "value": "Core",
                    "source": WATCH,
                }
            ],
        )
    )
    obs = result.observations[0]
    assert obs.end_utc - obs.start_utc == 1442
    assert (obs.start_offset_min, obs.end_offset_min) == (60, 0)


def test_fingerprint_is_stable_and_value_sensitive_and_hides_nothing_in_logs() -> None:
    t = utc(date(2026, 1, 10), 3)
    a = parse(block("respiratory_rate", "count/min", [point(t, qty=14)])).observations[0]
    b = parse(block("respiratory_rate", "count/min", [point(t, qty=14)])).observations[0]
    c = parse(block("respiratory_rate", "count/min", [point(t, qty=15)])).observations[0]
    assert a.fingerprint == b.fingerprint != c.fingerprint
    assert json.dumps(parse(block("steps", "count", [{"a": 1}])).unmapped_metrics) == '{"steps": 1}'
