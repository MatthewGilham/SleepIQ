"""Local chart queries and bounded, revision-checked SQLite preferences."""

import json
import math
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine, text

from app.analytics.catalog import BY_ID, CATALOG, Metric
from app.analytics.dashboard import NightNotFound, dashboard
from app.analytics.quality import hr_quality
from app.analytics.stats import ROLLING_MINIMUM, least_squares, pearson, rolling_mean
from app.db.coordinator import write_guard
from app.domain.versions import ActivePair, active_pair

KEY = "charts.presets.v1"
# Metrics removed from the catalog; old saved presets drop them silently on load (U03).
RETIRED = frozenset({"rhr_mean"})
CORRELATION_METHOD = (
    "Pearson r over nights where both metrics were recorded (same wake date); "
    "exploratory only: no significance test and not evidence of cause"
)


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    range: Literal["7", "30", "90", "365", "all", "custom"] = "30"
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def valid_window(self) -> "Window":
        if self.range == "custom":
            if not self.start or not self.end or self.start > self.end:
                raise ValueError("Choose an ordered custom range")
            if (self.end - self.start).days > 10000:
                raise ValueError("Range exceeds 10000 days")
        return self


class Selection(Window):
    metrics: list[str] = Field(min_length=1, max_length=15)
    mode: Literal["actual", "normalized"] = "actual"
    rolling: Literal["off", "7", "30"] = "off"

    @model_validator(mode="after")
    def valid(self) -> "Selection":
        if len(set(self.metrics)) != len(self.metrics) or any(m not in BY_ID for m in self.metrics):
            raise ValueError("Choose distinct supported metrics")
        if self.mode == "normalized" and any(BY_ID[m].clock for m in self.metrics):
            raise ValueError("Clock metrics cannot be normalized")
        return self


class Pairing(Window):
    x: str
    y: str

    @model_validator(mode="after")
    def valid_pair(self) -> "Pairing":
        # P21: source-local clock times are excluded from correlation.
        if self.x == self.y or any(m not in BY_ID or BY_ID[m].clock for m in (self.x, self.y)):
            raise ValueError("Choose two different non-clock metrics")
        return self


class Preset(Selection):
    name: str = Field(min_length=1, max_length=60, pattern=r".*\S.*")
    default: bool = False
    revision: int = Field(default=0, ge=0)


def normalize(values: list[float | None]) -> tuple[list[float | None], dict[str, Any]]:
    observed = [v for v in values if v is not None]
    mean = fmean(observed) if observed else None
    sd = pstdev(observed) if observed else None
    usable = sd is not None and sd > 0
    return (
        [((v - mean) / sd if v is not None else None) for v in values]
        if usable and mean is not None and sd is not None
        else [None] * len(values)
    ), {
        "n": len(observed),
        "mean": mean,
        "sd": sd,
        "reason": None if usable else "Normalization unavailable: no variation or no observations",
        "method": "(value - selected-range mean) / population standard deviation",
    }


class NightRows(dict[str, Any]):
    def __init__(self, pair: ActivePair, rows: Any) -> None:
        super().__init__((r["wake_date"], r) for r in rows)
        self.pair = pair


def _rows(engine: Engine) -> NightRows:
    # Fixed columns, bound values. No user SQL fragments or raw payloads.
    with engine.connect() as conn:
        pair = active_pair(conn)
        rows = (
            conn.execute(
                text("""SELECT n.*, s.overall, s.consistency, s.status AS score_status
          FROM nightly_metrics n LEFT JOIN nightly_scores s ON n.wake_date=s.wake_date
          AND n.derivation_version=s.derivation_version AND s.score_version=:score
          WHERE n.derivation_version=:derive ORDER BY n.wake_date"""),
                {"score": pair.score, "derive": pair.derive},
            )
            .mappings()
            .all()
        )
    return NightRows(pair, rows)


def _bounds(indexed: dict[str, Any], window: Window) -> tuple[date, date]:
    """Relative ranges end at the latest stored wake date; custom endpoints are inclusive."""
    last = date.fromisoformat(max(indexed))
    start, end = date.fromisoformat(min(indexed)), last
    if window.range == "custom":
        assert window.start and window.end
        start, end = window.start, window.end
    elif window.range != "all":
        start = last - timedelta(days=int(window.range) - 1)
    if (end - start).days > 10000:
        raise HTTPException(422, "Range exceeds 10000 days; choose a custom range")
    return start, end


def _days(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _value(row: Any, metric: Metric) -> float | None:
    raw = row[metric.id] if row else None
    value = float(raw) * metric.factor if raw is not None else None
    return value if value is None or math.isfinite(value) else None


def _rolling(
    indexed: dict[str, Any],
    metric: Metric,
    start: date,
    values: list[float | None],
    window: int,
    stats: dict[str, Any],
    normalized: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {"window": window, "minimum": ROLLING_MINIMUM[window]}
    if metric.clock:
        # A plain mean of clock minutes is wrong across midnight; P21 keeps clocks actual-only.
        return {**result, "values": None, "counts": None, "reason": "Not available for clock times"}
    # Early windows may reach before the selected range: those are real stored nights.
    lead = _days(start - timedelta(days=window - 1), start - timedelta(days=1))
    history = [_value(indexed.get(day), metric) for day in lead] + values
    means, counts = rolling_mean(history, window)
    means, counts = means[window - 1 :], counts[window - 1 :]
    reason = None
    if normalized:
        # Same linear transform as the points, so the line stays on the shared z axis.
        if stats["reason"]:
            means, reason = [None] * len(means), stats["reason"]
        else:
            means = [(m - stats["mean"]) / stats["sd"] if m is not None else None for m in means]
    return {**result, "values": means, "counts": counts, "reason": reason}


def series(engine: Engine, selection: Selection) -> dict[str, Any]:
    indexed = _rows(engine)
    if not indexed:
        return {
            "start": None,
            "end": None,
            "dates": [],
            "series": [],
            "versions": indexed.pair.versions,
        }
    start, end = _bounds(indexed, selection)
    dates = _days(start, end)
    output = []
    for key in selection.metrics:
        metric = BY_ID[key]
        values: list[float | None] = []
        details = []
        for day in dates:
            row = indexed.get(day)
            values.append(_value(row, metric))
            count_key = {
                "hr_mean": "hr_n",
                "hrv_mean": "hrv_n",
                "resp_mean": "resp_n",
                "temp_mean": "temp_n",
            }.get(key)
            details.append(
                {
                    "n": row[count_key] if row and count_key else None,
                    **({"hr_quality": hr_quality(row)} if row and key == "hr_mean" else {}),
                    "flags": json.loads(row["flags_json"]) if row else [],
                    "offset_minutes": row[
                        "start_offset_min" if key == "onset_minute" else "end_offset_min"
                    ]
                    if row
                    else None,
                }
            )
        normalized, stats = normalize(values)
        rolling = None
        if selection.rolling != "off":
            rolling = _rolling(
                indexed,
                metric,
                start,
                values,
                int(selection.rolling),
                stats,
                selection.mode == "normalized",
            )
        output.append(
            {
                **asdict(metric),
                "values": normalized if selection.mode == "normalized" else values,
                "raw": values,
                "details": details,
                "normalization": stats,
                "rolling": rolling,
            }
        )
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "dates": dates,
        "series": output,
        "versions": indexed.pair.versions,
    }


def correlation(engine: Engine, pairing: Pairing) -> dict[str, Any]:
    x, y = BY_ID[pairing.x], BY_ID[pairing.y]
    indexed = _rows(engine)
    result: dict[str, Any] = {
        "x": asdict(x),
        "y": asdict(y),
        "method": CORRELATION_METHOD,
        "versions": indexed.pair.versions,
    }
    if not indexed:
        return {
            **result,
            "start": None,
            "end": None,
            "days": 0,
            "pairs": [],
            "n": 0,
            "excluded": {"missing_x": 0, "missing_y": 0, "neither": 0},
            "r": None,
            "fit": None,
            "reason": "Unavailable: no recorded nights",
        }
    start, end = _bounds(indexed, pairing)
    dates = _days(start, end)
    pairs: list[dict[str, Any]] = []
    excluded = {"missing_x": 0, "missing_y": 0, "neither": 0}
    for day in dates:
        row = indexed.get(day)
        xv, yv = _value(row, x), _value(row, y)
        if xv is None and yv is None:
            excluded["neither"] += 1
        elif xv is None:
            excluded["missing_x"] += 1
        elif yv is None:
            excluded["missing_y"] += 1
        else:
            pairs.append({"date": day, "x": xv, "y": yv,
                          **({"hr_quality": hr_quality(row)}
                             if row and "hr_mean" in (pairing.x, pairing.y) else {})})
    xs, ys = [p["x"] for p in pairs], [p["y"] for p in pairs]
    r, reason = pearson(xs, ys)
    return {
        **result,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": len(dates),
        "pairs": pairs,
        "n": len(pairs),
        "excluded": excluded,
        "r": r,
        "fit": least_squares(xs, ys),
        "reason": reason,
    }


def correlation_matrix(engine: Engine, window: Window) -> dict[str, Any]:
    """Pearson r for every pair of non-clock metrics over the same calendar days (U17, F7)."""
    indexed = _rows(engine)
    metrics = [m for m in CATALOG if not m.clock]
    result: dict[str, Any] = {
        "metrics": [{"id": m.id, "label": m.label, "unit": m.unit} for m in metrics],
        "method": CORRELATION_METHOD,
        "versions": indexed.pair.versions,
    }
    if not indexed:
        return {**result, "start": None, "end": None, "days": 0, "cells": []}
    start, end = _bounds(indexed, window)
    dates = _days(start, end)
    values = {m.id: [_value(indexed.get(day), m) for day in dates] for m in metrics}
    cells = []
    for i, a in enumerate(metrics):
        for b in metrics[i + 1 :]:
            paired = [
                (x, y)
                for x, y in zip(values[a.id], values[b.id], strict=True)
                if x is not None and y is not None
            ]
            r, reason = pearson([x for x, _ in paired], [y for _, y in paired])
            cells.append({"x": a.id, "y": b.id, "r": r, "n": len(paired), "reason": reason})
    return {
        **result,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": len(dates),
        "cells": cells,
    }


def router(engine: Engine, data: Path, synthetic: bool = False) -> APIRouter:
    api = APIRouter(prefix="/api/v1")

    @api.get("/metrics/catalog")
    def catalog() -> list[dict[str, Any]]:
        return [asdict(m) for m in CATALOG]

    @api.get("/dashboard")
    def latest(night: date | None = None) -> dict[str, Any]:
        try:
            return dashboard(engine, synthetic, night)
        except NightNotFound:
            raise HTTPException(404, "No sleep was recorded for that night") from None

    @api.post("/analytics/timeseries")
    def timeseries(selection: Selection) -> dict[str, Any]:
        return {**series(engine, selection), "synthetic": synthetic}

    @api.post("/analytics/summary")
    def period_summary(window: Window) -> dict[str, Any]:
        from app.analytics.summary import summary

        return {**summary(engine, window), "synthetic": synthetic}

    @api.post("/analytics/correlation")
    def paired(pairing: Pairing) -> dict[str, Any]:
        return {**correlation(engine, pairing), "synthetic": synthetic}

    @api.post("/analytics/correlation/matrix")
    def pair_grid(window: Window) -> dict[str, Any]:
        return {**correlation_matrix(engine, window), "synthetic": synthetic}

    def read(conn: Any) -> list[dict[str, Any]]:
        value = conn.execute(
            text("SELECT value_json FROM app_settings WHERE key=:key"), {"key": KEY}
        ).scalar()
        items: list[dict[str, Any]] = json.loads(value) if value else []
        for item in items:
            kept = [m for m in item["metrics"] if m not in RETIRED]
            item["metrics"] = kept or ["asleep_s"]
        return items

    @api.get("/presets")
    def presets() -> list[dict[str, Any]]:
        with engine.connect() as conn:
            return read(conn)

    @api.put("/presets/{preset_id}")
    def save(preset_id: str, preset: Preset) -> dict[str, Any]:
        with write_guard(data), engine.begin() as conn:
            items = read(conn)
            old = next((p for p in items if p["id"] == preset_id), None)
            if preset_id != "new" and old is None:
                raise HTTPException(404, "Preset not found")
            if old and old["revision"] != preset.revision:
                raise HTTPException(409, "Preset changed; reload before saving")
            if len(items) >= 100 and not old:
                raise HTTPException(409, "Maximum 100 presets")
            if any(
                p["id"] != preset_id and p["name"].casefold() == preset.name.strip().casefold()
                for p in items
            ):
                raise HTTPException(409, "A preset already has that name")
            result = {
                **preset.model_dump(mode="json"),
                "name": preset.name.strip(),
                "id": old["id"] if old else uuid4().hex,
                "revision": (old["revision"] if old else 0) + 1,
            }
            items = [p for p in items if p["id"] != preset_id]
            if preset.default:
                for item in items:
                    if item["default"]:
                        item["default"] = False
                        item["revision"] += 1
            items.append(result)
            conn.execute(
                text(
                    "INSERT INTO app_settings(key,value_json) VALUES(:key,:value) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
                ),
                {"key": KEY, "value": json.dumps(items)},
            )
            return result

    @api.delete("/presets/{preset_id}")
    def delete(preset_id: str, revision: int) -> dict[str, bool]:
        with write_guard(data), engine.begin() as conn:
            items = read(conn)
            old = next((p for p in items if p["id"] == preset_id), None)
            if not old:
                raise HTTPException(404, "Preset not found")
            if old["revision"] != revision:
                raise HTTPException(409, "Preset changed; reload before deleting")
            conn.execute(
                text("UPDATE app_settings SET value_json=:value WHERE key=:key"),
                {"key": KEY, "value": json.dumps([p for p in items if p["id"] != preset_id])},
            )
        return {"deleted": True}

    return api
