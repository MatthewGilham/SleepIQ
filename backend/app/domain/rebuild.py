"""Rebuild derived nights, general metrics and scores from stored observations.

`rebuild(conn, from_date=None)` recomputes everything from that wake date forward. A clean rebuild
is `from_date=None`; an incremental one must produce identical rows (tested). Source observations
are never modified.
"""

import json
import math
import time
from bisect import bisect_right
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Connection, text

from app.domain.config import DERIVE, SCORE, DeriveConfig, ScoreConfig
from app.domain.scoring import consistency, score_night
from app.domain.sessions import (
    Night,
    StageRow,
    build_candidates,
    local_date,
    local_minute,
    select_nights,
)

PHYSIOLOGY = {
    "hr": ("heart_rate", "avg"),
    "hrv": ("heart_rate_variability", "qty"),
    "resp": ("respiratory_rate", "qty"),
    "rhr": ("resting_heart_rate", "qty"),
    "temp": ("apple_sleeping_wrist_temperature", "qty"),
}


def _midnight(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def latest_night(conn: Connection, cfg: DeriveConfig = DERIVE) -> date | None:
    value = conn.execute(
        text("SELECT max(wake_date) FROM nightly_metrics WHERE derivation_version = :v"),
        {"v": cfg.version},
    ).scalar()
    return date.fromisoformat(value) if value else None


def _longest_interval(conn: Connection, metric: str) -> int:
    value = conn.execute(
        text("SELECT max(end_utc - start_utc) FROM observations WHERE metric = :m"), {"m": metric}
    ).scalar()
    return int(value or 0)


def _window_mean(
    conn: Connection, metric: str, column: str, start: int, end: int, longest: int
) -> tuple[float | None, int]:
    # Representative instant is the interval midpoint (start + end) / 2, kept in integers.
    # The start_utc bounds are implied by the midpoint test and the longest stored interval;
    # they let SQLite use the (metric, status, start_utc) index instead of scanning the metric.
    rows = conn.execute(
        text(
            f"SELECT {column} FROM observations WHERE metric = :m AND status = 'active' "
            "AND start_utc BETWEEN :first AND :end "
            "AND start_utc + end_utc BETWEEN :lo AND :hi ORDER BY start_utc, id"
        ),
        {"m": metric, "first": start - longest // 2 - 1, "end": end, "lo": 2 * start, "hi": 2 * end},
    ).scalars()
    values = [float(v) for v in rows]
    return (math.fsum(values) / len(values), len(values)) if values else (None, 0)


def _stage_rows(conn: Connection, since: int) -> list[StageRow]:
    rows = conn.execute(
        text(
            "SELECT id, source, start_utc, end_utc, start_offset_min, end_offset_min, stage, qty "
            "FROM observations WHERE metric = 'sleep_analysis' AND status = 'active' "
            "AND end_utc >= :since ORDER BY start_utc, id"
        ),
        {"since": since},
    )
    return [StageRow(*row) for row in rows]


def _flags(conn: Connection, night: Night, cfg: DeriveConfig) -> list[str]:
    window = night.selected
    flags = list(night.flags)
    revised = conn.execute(
        text(
            "SELECT 1 FROM observations WHERE status = 'conflicting' "
            "AND start_utc <= :hi AND end_utc >= :lo LIMIT 1"
        ),
        {"lo": window.start, "hi": window.end},
    ).first()
    if revised:
        flags.append("revised")
    later = conn.execute(
        text("SELECT 1 FROM observations WHERE status = 'active' AND start_utc > :t LIMIT 1"),
        {"t": window.end + cfg.completion_lookahead_seconds},
    ).first()
    if not later:
        flags.append("possibly_incomplete")
    return flags


def _store_night(
    conn: Connection,
    day: date,
    night: Night,
    cfg: DeriveConfig,
    now: int,
    longest: dict[str, int],
) -> dict[str, object]:
    window = night.selected
    asleep, awake = window.asleep, window.awake
    values: dict[str, object] = {
        "wake_date": day.isoformat(),
        "derivation_version": cfg.version,
        "source": window.source,
        "session_start_utc": window.start,
        "session_end_utc": window.end,
        "start_offset_min": window.start_offset,
        "end_offset_min": window.end_offset,
        "onset_minute": local_minute(window.start, window.start_offset),
        "wake_minute": local_minute(window.end, window.end_offset),
        "asleep_s": asleep,
        "core_s": window.core,
        "deep_s": window.deep,
        "rem_s": window.rem,
        "awake_s": awake,
        "efficiency": asleep / (asleep + awake),
        "candidate_count": night.candidate_count,
        "flags_json": json.dumps(_flags(conn, night, cfg)),
        "computed_utc": now,
    }
    for key, (metric, column) in PHYSIOLOGY.items():
        mean, count = _window_mean(conn, metric, column, window.start, window.end, longest[metric])
        values[f"{key}_mean"], values[f"{key}_n"] = mean, count
    values["hr_method"] = "simple_mean_fallback" if values["hr_n"] else None
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    conn.execute(text(f"INSERT INTO nightly_metrics ({columns}) VALUES ({placeholders})"), values)
    return values


def _general_metrics(
    conn: Connection, windows: list[tuple[int, int]], from_day: date, cfg: DeriveConfig
) -> None:
    """Physiology readings outside every selected sleep window are general daily metrics."""
    conn.execute(
        text("DELETE FROM general_metrics WHERE derivation_version = :v AND local_date >= :d"),
        {"v": cfg.version, "d": from_day.isoformat()},
    )
    starts = [w[0] for w in windows]
    for metric, column in PHYSIOLOGY.values():
        sums: dict[str, list[float]] = {}
        rows = conn.execute(
            text(
                f"SELECT start_utc, end_utc, start_offset_min, {column} FROM observations "
                "WHERE metric = :m AND status = 'active' AND end_utc >= :since "
                "ORDER BY start_utc, id"
            ),
            {"m": metric, "since": _midnight(from_day) - 86400},
        )
        for start, end, offset, value in rows:
            day = local_date(start, offset)
            if day < from_day:
                continue
            twice = start + end
            i = bisect_right(starts, twice // 2) - 1
            if i >= 0 and 2 * windows[i][0] <= twice <= 2 * windows[i][1]:
                continue
            sums.setdefault(day.isoformat(), []).append(float(value))
        for day_text, values in sums.items():
            conn.execute(
                text("INSERT INTO general_metrics VALUES (:d, :m, :v, :mean, :n)"),
                {
                    "d": day_text,
                    "m": metric,
                    "v": cfg.version,
                    "mean": math.fsum(values) / len(values),
                    "n": len(values),
                },
            )


def _score_nights(
    conn: Connection, days: list[date], derive: DeriveConfig, score: ScoreConfig, now: int
) -> None:
    for day in days:
        row = conn.execute(
            text(
                "SELECT asleep_s, efficiency, onset_minute, wake_minute, hr_mean, hrv_mean "
                "FROM nightly_metrics WHERE wake_date = :d AND derivation_version = :v"
            ),
            {"d": day.isoformat(), "v": derive.version},
        ).one()
        # Eligible baseline: valid, unrevised sessions in the preceding calendar window.
        prior = conn.execute(
            text(
                "SELECT onset_minute, wake_minute FROM nightly_metrics "
                "WHERE derivation_version = :v AND wake_date >= :lo AND wake_date < :d "
                "AND flags_json NOT LIKE '%\"revised\"%' ORDER BY wake_date"
            ),
            {
                "v": derive.version,
                "lo": (day - timedelta(days=score.baseline_days)).isoformat(),
                "d": day.isoformat(),
            },
        ).all()
        cons = consistency(row.onset_minute, row.wake_minute, [tuple(p) for p in prior], score)
        result = score_night(row.asleep_s, row.efficiency, cons, row.hr_mean, row.hrv_mean, score)
        details = {
            "components": result.components,
            "missing": list(result.missing),
            "consistency": {
                "available": cons.available,
                "reason": cons.reason,
                "baseline_nights": cons.nights,
                "provisional": cons.provisional,
                "onset_deviation_min": cons.onset_deviation,
                "wake_deviation_min": cons.wake_deviation,
            },
        }
        conn.execute(
            text(
                "INSERT INTO nightly_scores (wake_date, score_version, derivation_version, "
                "config_hash, status, overall, consistency, details_json, computed_utc) "
                "VALUES (:d, :sv, :dv, :h, :s, :o, :c, :j, :t)"
            ),
            {
                "d": day.isoformat(),
                "sv": score.version,
                "dv": derive.version,
                "h": score.config_hash(),
                "s": result.status,
                "o": result.overall,
                "c": cons.score,
                "j": json.dumps(details, sort_keys=True),
                "t": now,
            },
        )


def rebuild(
    conn: Connection,
    from_date: date | None = None,
    derive: DeriveConfig = DERIVE,
    score: ScoreConfig = SCORE,
    now: int | None = None,
) -> date:
    """Recompute nights/general metrics/scores with wake date >= from_date. Returns the start."""
    stamp = int(time.time()) if now is None else now
    first = conn.execute(
        text("SELECT min(start_utc) FROM observations WHERE status = 'active'")
    ).scalar()
    start_day = from_date or (local_date(first, 0) if first is not None else date(1970, 1, 1))
    since = _midnight(start_day) - 3 * 86400
    candidates = build_candidates(_stage_rows(conn, since), derive)
    nights = select_nights(candidates, derive)
    conn.execute(
        text("DELETE FROM nightly_metrics WHERE derivation_version = :v AND wake_date >= :d"),
        {"v": derive.version, "d": start_day.isoformat()},
    )
    conn.execute(
        text("DELETE FROM nightly_scores WHERE score_version = :v AND wake_date >= :d"),
        {"v": score.version, "d": start_day.isoformat()},
    )
    rebuilt = sorted(day for day in nights if day >= start_day)
    longest = {metric: _longest_interval(conn, metric) for metric, _ in PHYSIOLOGY.values()}
    for day in rebuilt:
        _store_night(conn, day, nights[day], derive, stamp, longest)
    windows = sorted(
        (night.selected.start, night.selected.end)
        for day, night in nights.items()
        if day >= start_day - timedelta(days=1)
    )
    _general_metrics(conn, windows, start_day, derive)
    _score_nights(conn, rebuilt, derive, score, stamp)
    return start_day
