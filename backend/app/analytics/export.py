"""CSV export of computed nightly metrics. Never includes raw payloads, sources or secrets."""

import csv
import io
import json
from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import Engine

from app.analytics.api import Window, _bounds, _rows, _value
from app.analytics.catalog import BY_ID, Metric
from app.analytics.quality import hr_quality

HR_COLUMNS = ["hr_method", "hr_n", "hr_eligible_n", "hr_contributing_n", "hr_covered_s",
              "hr_window_s", "hr_coverage", "hr_fallback_reason", "derivation_config_hash"]

BOM = "﻿"  # lets Excel read UTF-8 (for example the degree sign) correctly
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


class ExportRequest(Window):
    model_config = ConfigDict(extra="forbid")
    metrics: list[str] = Field(min_length=1, max_length=15)

    @model_validator(mode="after")
    def supported(self) -> "ExportRequest":
        if len(set(self.metrics)) != len(self.metrics) or any(m not in BY_ID for m in self.metrics):
            raise ValueError("Choose distinct supported metrics")
        return self


def safe_text(value: str) -> str:
    """Neutralise spreadsheet formulas in text cells (numbers are written separately)."""
    return "'" + value if value.startswith(FORMULA_STARTS) else value


def clock(minutes: float) -> str:
    whole = round(minutes) % 1440
    return f"{whole // 60:02d}:{whole % 60:02d}"


def header(metric: Metric) -> str:
    return f"{metric.label} ({'HH:MM source-local' if metric.clock else metric.unit})"


def cell(value: float | None, metric: Metric) -> str:
    # A missing reading stays an empty cell; it is never written as zero.
    if value is None:
        return ""
    return clock(value) if metric.clock else repr(round(value, 6))


def nightly_csv(engine: Engine, request: ExportRequest) -> tuple[str, str, int]:
    """Return (filename, CSV text, night count). Only nights with a stored record are listed."""
    indexed = _rows(engine)
    metrics = [BY_ID[m] for m in request.metrics]
    quality_columns = HR_COLUMNS if "hr_mean" in request.metrics else []
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "wake_date",
            *map(header, metrics),
            *quality_columns,
            "flags",
            "score_status",
            "derivation_version",
            "score_version",
        ]
    )
    rows: list[Any] = []
    start = end = None
    if indexed:
        start, end = _bounds(indexed, request)
        rows = [r for d, r in indexed.items() if start <= date.fromisoformat(d) <= end]
    for row in rows:
        quality = {f"hr_{key}": value for key, value in hr_quality(row).items()}
        quality["derivation_config_hash"] = row.get("derivation_config_hash")
        writer.writerow(
            [
                row["wake_date"],
                *(cell(_value(row, m), m) for m in metrics),
                *(safe_text(str(quality[k])) if quality[k] is not None else "" for k in quality_columns),
                safe_text("; ".join(json.loads(row["flags_json"]))),
                row["score_status"] or "not_computed",
                indexed.pair.derive,
                indexed.pair.score,
            ]
        )
    name = f"sleepiq-nightly-{start}_{end}.csv" if start and end else "sleepiq-nightly-empty.csv"
    return name, BOM + out.getvalue(), len(rows)


def router(engine: Engine) -> APIRouter:
    api = APIRouter(prefix="/api/v1")

    @api.post("/analytics/export")
    def export(request: ExportRequest) -> Response:
        name, body, count = nightly_csv(engine, request)
        return Response(
            body.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "X-SleepIQ-Rows": str(count),
            },
        )

    return api
