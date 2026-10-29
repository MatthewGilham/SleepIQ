"""Evidence bundle: statistics computed in Python and the only health data the AI ever sees."""

import math
from itertools import combinations
from statistics import fmean, pstdev
from typing import Any

from sqlalchemy import Engine

from app.ai.config import LIMITS
from app.analytics.api import Pairing, Selection, Window, correlation, series
from app.analytics.catalog import BY_ID
from app.domain.config import DERIVE, SCORE


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def slope_per_week(points: list[tuple[int, float]]) -> float | None:
    """Least-squares change per 7 days over observed nights; None below 3 nights."""
    if len(points) < 3:
        return None
    mean_x, mean_y = fmean(p[0] for p in points), fmean(p[1] for p in points)
    denominator = math.fsum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        return None
    return 7 * math.fsum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def _clock(minutes: float) -> str:
    whole = round(minutes) % 1440
    return f"{whole // 60:02d}:{whole % 60:02d}"


def build(engine: Engine, metrics: list[str], window: Window) -> dict[str, Any] | None:
    """Return None when the range holds no recorded night for any selected metric."""
    chart = series(
        engine,
        Selection(metrics=metrics, range=window.range, start=window.start, end=window.end),
    )
    dates: list[str] = chart["dates"]
    per_metric: list[dict[str, Any]] = []
    observed_any = False
    for item in chart["series"]:
        metric = BY_ID[item["id"]]
        points = [(i, v) for i, v in enumerate(item["values"]) if v is not None]
        observed_any = observed_any or bool(points)
        entry: dict[str, Any] = {
            "metric": metric.label,
            "unit": "HH:MM source-local" if metric.clock else metric.unit,
            "method": metric.method,
            "nights_recorded": len(points),
            "nights_missing": len(dates) - len(points),
        }
        if points and not metric.clock:
            values = [v for _, v in points]
            entry.update(
                mean=_round(fmean(values)),
                sd=_round(pstdev(values)),
                min=_round(min(values)),
                max=_round(max(values)),
                change_per_week=_round(slope_per_week(points)),
            )
        shown = points[-LIMITS.max_nights :]
        entry["nightly_values"] = [
            [dates[i], _clock(v) if metric.clock else _round(v)] for i, v in shown
        ]
        entry["nightly_values_truncated"] = len(shown) < len(points)
        per_metric.append(entry)
    if not observed_any:
        return None
    pairs = []
    for x, y in combinations([m for m in metrics if not BY_ID[m].clock], 2):
        result = correlation(
            engine, Pairing(x=x, y=y, range=window.range, start=window.start, end=window.end)
        )
        pairs.append(
            {
                "x": BY_ID[x].label,
                "y": BY_ID[y].label,
                "paired_nights": result["n"],
                "pearson_r": _round(result["r"]),
                "unavailable_reason": result["reason"],
            }
        )
    return {
        "date_range": [chart["start"], chart["end"]],
        "calendar_days": len(dates),
        "metrics": per_metric,
        "correlations": pairs,
        "correlation_method": "Pearson r over nights where both were recorded; not evidence of cause",
        "versions": [DERIVE.version, SCORE.version],
    }
