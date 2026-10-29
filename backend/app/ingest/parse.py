"""Health Auto Export JSON v2 adapter: validate per metric, never emit or log readings."""

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

PARSER_VERSION = "parse-1"
UNITS = {
    "sleep_analysis": "hr",
    "heart_rate": "count/min",
    "heart_rate_variability": "ms",
    "respiratory_rate": "count/min",
    "resting_heart_rate": "count/min",
    "apple_sleeping_wrist_temperature": "degC",
}
STAGES = frozenset({"Core", "Deep", "REM", "Awake"})
# Physical plausibility only; rows outside are rejected visibly (raw JSON keeps them).
PLAUSIBLE = {
    "heart_rate": (20.0, 250.0),
    "heart_rate_variability": (0.0, 500.0),
    "respiratory_rate": (3.0, 60.0),
    "resting_heart_rate": (20.0, 200.0),
    "apple_sleeping_wrist_temperature": (20.0, 45.0),
}
MAX_SOURCE = 200
REASONS = frozenset(
    {"timestamp", "number", "interval", "source", "stage", "value", "implausible", "shape"}
)


class UnsupportedExport(ValueError):
    """Envelope is not a recognised export; nothing may be stored."""


@dataclass(frozen=True)
class Observation:
    metric: str
    source: str
    start_utc: int
    end_utc: int
    start_offset_min: int
    end_offset_min: int
    stage: str | None
    qty: float | None
    avg: float | None
    minimum: float | None
    maximum: float | None
    has_heartbeat_series: bool
    fingerprint: str


@dataclass
class ParsedBatch:
    observations: list[Observation] = field(default_factory=list)
    rejected: Counter[str] = field(default_factory=Counter)
    unmapped_metrics: Counter[str] = field(default_factory=Counter)


def _instant(value: object) -> tuple[int, int]:
    """Return (UTC epoch seconds, offset minutes); zoned, whole-second stamps only."""
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("timestamp")
    try:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("timestamp") from None  # never echo the offending input
    offset = parsed.utcoffset()
    if offset is None or parsed.microsecond or offset.total_seconds() % 60:
        raise ValueError("timestamp")
    return int(parsed.timestamp()), int(offset.total_seconds()) // 60


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError("number")
    return float(value)


def _optional(row: dict[str, object], key: str) -> float | None:
    return _number(row[key]) if key in row else None


def _row(metric: str, row: dict[str, object]) -> Observation:
    start, start_offset = _instant(row.get("start", row.get("startDate")))
    end, end_offset = _instant(row.get("end", row.get("endDate")))
    if end < start or (metric == "sleep_analysis" and end == start):
        raise ValueError("interval")
    source = row.get("source", "")
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        raise ValueError("source")
    stage = qty = avg = low = high = None
    if metric == "sleep_analysis":
        value = row.get("value")
        if not isinstance(value, str) or value not in STAGES:
            raise ValueError("stage")
        stage = value
        qty = _optional(row, "qty")
    elif metric == "heart_rate":
        avg, low, high = (_optional(row, key) for key in ("Avg", "Min", "Max"))
        if avg is None:
            raise ValueError("value")
    else:
        qty = _optional(row, "qty")
        if qty is None:
            raise ValueError("value")
    if metric in PLAUSIBLE:
        main = avg if metric == "heart_rate" else qty
        lower, upper = PLAUSIBLE[metric]
        if main is None or not lower <= main <= upper:
            raise ValueError("implausible")
    fingerprint = hashlib.sha256(
        json.dumps(
            [metric, source, start, end, start_offset, end_offset, stage, qty, avg, low, high],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return Observation(
        metric,
        source,
        start,
        end,
        start_offset,
        end_offset,
        stage,
        qty,
        avg,
        low,
        high,
        "heartbeatSeries" in row,
        fingerprint,
    )


def parse_payload(payload: object) -> ParsedBatch:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise UnsupportedExport("Unsupported export envelope")
    metrics = payload["data"].get("metrics")
    if not isinstance(metrics, list):
        raise UnsupportedExport("Unsupported export envelope")
    result = ParsedBatch()
    for block in metrics:
        if not isinstance(block, dict) or not isinstance(block.get("data"), list):
            raise UnsupportedExport("Unsupported metric block")
        name = block.get("name")
        rows = block["data"]
        if not isinstance(name, str) or name not in UNITS:
            result.unmapped_metrics[str(name)[:64]] += len(rows)
            continue
        if block.get("units") != UNITS[name]:
            result.rejected["unexpected_units"] += len(rows)
            continue
        for row in rows:
            try:
                if not isinstance(row, dict):
                    raise ValueError("shape")  # noqa: TRY004 - collected as a row rejection
                result.observations.append(_row(name, row))
            except ValueError as error:
                reason = str(error)
                result.rejected[f"{name}:{reason if reason in REASONS else 'invalid'}"] += 1
    return result
