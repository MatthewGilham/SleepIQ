"""Synthetic Health Auto Export JSON v2 builders. No real data, sources or identifiers."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.db.engine import open_engine
from app.db.initialize import initialize
from sqlalchemy import Engine

WATCH = "Synthetic Apple Watch"
PHONE = "Synthetic Phone"
# One standard night: 450 min asleep (7.5 h) and 10 min interior Awake.
PLAN = [
    ("Core", 120),
    ("Deep", 60),
    ("REM", 60),
    ("Core", 90),
    ("Awake", 10),
    ("REM", 60),
    ("Core", 60),
]
BST_START = datetime(2026, 3, 29, 1, tzinfo=UTC)
BST_END = datetime(2026, 10, 25, 1, tzinfo=UTC)


def offset_for(utc: datetime) -> int:
    """UK offset in minutes for 2026 (BST between the two clock changes)."""
    return 60 if BST_START <= utc < BST_END else 0


def stamp(utc: datetime) -> str:
    minutes = offset_for(utc)
    local = utc + timedelta(minutes=minutes)
    sign = "+" if minutes >= 0 else "-"
    return f"{local:%Y-%m-%d %H:%M:%S} {sign}{minutes // 60:02d}{minutes % 60:02d}"


def utc(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def sleep_rows(
    start: datetime, plan: list[tuple[str, int]] = PLAN, source: str = WATCH
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stage, minutes in plan:
        end = start + timedelta(minutes=minutes)
        rows.append(
            {
                "start": stamp(start),
                "end": stamp(end),
                "value": stage,
                "qty": minutes / 60,
                "source": source,
            }
        )
        start = end
    return rows


def point(when: datetime, **values: object) -> dict[str, object]:
    return {"start": stamp(when), "end": stamp(when), "source": WATCH, **values}


def span(start: datetime, hours: float, **values: object) -> dict[str, object]:
    return {
        "start": stamp(start),
        "end": stamp(start + timedelta(hours=hours)),
        "source": WATCH,
        **values,
    }


def block(name: str, units: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {"name": name, "units": units, "data": rows}


def night_blocks(
    wake_day: date,
    *,
    onset: tuple[int, int] = (23, 0),
    plan: list[tuple[str, int]] = PLAN,
    hr: float | None = 52.0,
    hrv: float | None = 48.0,
    resp: float | None = 14.5,
) -> list[dict[str, object]]:
    """Blocks for the night ending on `wake_day` (session starts the previous evening)."""
    start = utc(wake_day - timedelta(days=1), *onset)
    if offset_for(start):
        start -= timedelta(minutes=60)  # keep the same local clock time during BST
    total = sum(minutes for _, minutes in plan)
    blocks = [block("sleep_analysis", "hr", sleep_rows(start, plan))]
    if hr is not None:
        samples = [
            point(start + timedelta(minutes=m), Avg=hr + m % 3, Min=hr - 3, Max=hr + 6)
            for m in range(30, total, 60)
        ]
        blocks.append(block("heart_rate", "count/min", samples))
    if hrv is not None:
        blocks.append(
            block(
                "heart_rate_variability",
                "ms",
                [span(start + timedelta(minutes=90), 0.5, qty=hrv)],
            )
        )
    if resp is not None:
        blocks.append(
            block(
                "respiratory_rate",
                "count/min",
                [point(start + timedelta(minutes=45), qty=resp)],
            )
        )
    return blocks


def merge(*groups: list[dict[str, object]]) -> list[dict[str, object]]:
    """Combine blocks of the same metric into one block each, preserving row order."""
    merged: dict[str, dict[str, object]] = {}
    for group in groups:
        for item in group:
            name = str(item["name"])
            if name in merged:
                rows = merged[name]["data"]
                assert isinstance(rows, list) and isinstance(item["data"], list)
                rows.extend(item["data"])
            else:
                merged[name] = {**item, "data": list(item["data"])}  # type: ignore[call-overload]
    return list(merged.values())


def payload(blocks: list[dict[str, object]]) -> bytes:
    return json.dumps({"data": {"metrics": blocks}}).encode()


def nights_payload(first: date, count: int, **night: object) -> bytes:
    groups = [night_blocks(first + timedelta(days=i), **night) for i in range(count)]  # type: ignore[arg-type]
    return payload(merge(*groups))


def new_store(scratch: Path) -> tuple[Path, Engine]:
    initialize(scratch)
    return scratch, open_engine(scratch / "sleepiq.sqlite3")
