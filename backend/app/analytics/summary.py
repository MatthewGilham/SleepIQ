"""Period summary for the Analytics page (U05). Python computes every figure; the page only formats.

Missing nights are excluded from every mean and count, never treated as zero. The previous period is
the same number of calendar days ending the day before the selected range starts.
"""

import math
from datetime import date, timedelta
from statistics import fmean, quantiles
from typing import Any

from sqlalchemy import Engine

from app.analytics.api import Window, _bounds, _rows, _value
from app.analytics.catalog import CATALOG
from app.analytics.dashboard import ceiling
from app.domain.config import DERIVE, SCORE

STAGES = (("deep", "deep_s"), ("rem", "rem_s"), ("core", "core_s"), ("awake", "awake_s"))
METHOD = {
    "means": "Mean over recorded nights in the range; nights without a reading are excluded",
    "previous": "Same number of calendar days immediately before the range",
    "stages": "Mean minutes per recorded night; % of the four stage means combined",
    "clock": (
        "Source-local clock minutes unwrapped around their circular mean, then inclusive "
        "quartiles; a midnight crossing stays continuous"
    ),
}


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


def _clock(minutes: list[float]) -> dict[str, Any]:
    """Quartiles of clock times that may straddle midnight, as minutes of the day (0-1439)."""
    if not minutes:
        return {"n": 0, "q1": None, "median": None, "q3": None}
    angle = [m / 1440 * 2 * math.pi for m in minutes]
    centre = math.atan2(sum(map(math.sin, angle)), sum(map(math.cos, angle))) / (2 * math.pi) * 1440
    # Shift each time to within 12 hours of the centre so 23:30 and 00:30 are an hour apart, not 23.
    unwrapped = sorted(centre + ((m - centre + 720) % 1440) - 720 for m in minutes)
    q1, q2, q3 = (
        quantiles(unwrapped, n=4, method="inclusive") if len(unwrapped) > 1 else unwrapped * 3
    )

    def wrap(v: float) -> float:
        # Round first so a value a hair below midnight reads 00:00, never 24:00.
        return round(v, 6) % 1440

    return {"n": len(minutes), "q1": wrap(q1), "median": wrap(q2), "q3": wrap(q3)}


def _period(indexed: dict[str, Any], start: date, end: date) -> dict[str, Any]:
    rows = [
        indexed[d]
        for d in ((start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1))
        if d in indexed
    ]
    metrics: dict[str, Any] = {}
    for metric in CATALOG:
        if metric.clock:
            continue
        values = [v for v in (_value(r, metric) for r in rows) if v is not None]
        metrics[metric.id] = {
            "mean": _mean(values),
            "n": len(values),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": (end - start).days + 1,
        "nights": len(rows),
        "rows": rows,
        "metrics": metrics,
    }


def summary(engine: Engine, window: Window) -> dict[str, Any]:
    indexed = _rows(engine)
    base: dict[str, Any] = {
        "versions": [DERIVE.version, SCORE.version],
        "ceiling": ceiling(),
        "method": METHOD,
    }
    if not indexed:
        return {
            **base,
            "start": None,
            "end": None,
            "days": 0,
            "nights": 0,
            "previous": None,
            "metrics": {},
            "stages": None,
            "clock": None,
        }
    start, end = _bounds(indexed, window)
    current = _period(indexed, start, end)
    length = timedelta(days=current["days"])
    previous = _period(indexed, start - length, start - timedelta(days=1))
    metrics: dict[str, Any] = {}
    for key, item in current["metrics"].items():
        before = previous["metrics"][key]
        delta = (
            item["mean"] - before["mean"]
            if item["mean"] is not None and before["mean"] is not None
            else None
        )
        metrics[key] = {
            **item,
            "previous_mean": before["mean"],
            "previous_n": before["n"],
            "delta": delta,
        }
    rows = current["rows"]
    stage_means = {
        name: _mean([r[column] / 60 for r in rows if r[column] is not None])
        for name, column in STAGES
    }
    total = sum(v for v in stage_means.values() if v is not None)
    stages = (
        {
            name: {"minutes": m, "percent": (m / total * 100) if m is not None and total else None}
            for name, m in stage_means.items()
        }
        if rows
        else None
    )
    return {
        **base,
        "start": current["start"],
        "end": current["end"],
        "days": current["days"],
        "nights": current["nights"],
        "previous": {k: previous[k] for k in ("start", "end", "days", "nights")},
        "metrics": metrics,
        "stages": stages,
        "clock": {
            "onset": _clock(
                [float(r["onset_minute"]) for r in rows if r["onset_minute"] is not None]
            ),
            "wake": _clock([float(r["wake_minute"]) for r in rows if r["wake_minute"] is not None]),
        },
    }
