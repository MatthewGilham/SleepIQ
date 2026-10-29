"""Inspect one explicitly selected export locally. Never emit readings or identifiers."""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024
UNITS = {
    "sleep_analysis": "hr",
    "heart_rate": "count/min",
    "heart_rate_variability": "ms",
    "respiratory_rate": "count/min",
    "resting_heart_rate": "count/min",
    "apple_sleeping_wrist_temperature": "degC",
}
FIELDS = (
    "start",
    "end",
    "startDate",
    "endDate",
    "qty",
    "Avg",
    "Min",
    "Max",
    "source",
    "heartbeatSeries",
    "id",
    "uuid",
    "recordId",
    "updatedAt",
    "modifiedAt",
    "lastModified",
)


@dataclass
class Shape:
    samples: int = 0
    malformed_samples: int = 0
    expected_unit_blocks: int = 0
    unexpected_unit_blocks: int = 0
    field_presence: dict[str, int] = field(default_factory=lambda: dict.fromkeys(FIELDS, 0))
    interval_patterns: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(
            ("point", "positive", "negative", "missing", "invalid_or_unzoned"), 0
        )
    )
    repeated_identity: int = 0
    changed_identity: int = 0


def _instant(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Invalid timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        result = datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
    if result.utcoffset() is None:
        raise ValueError("Unzoned timestamp")
    return result


def _interval(row: dict[str, object]) -> str:
    start = row.get("start", row.get("startDate"))
    end = row.get("end", row.get("endDate"))
    if start is None or end is None:
        return "missing"
    try:
        seconds = (_instant(end) - _instant(start)).total_seconds()
    except (ValueError, TypeError):
        return "invalid_or_unzoned"
    return "point" if seconds == 0 else "positive" if seconds > 0 else "negative"


def diagnose(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise TypeError("Unsupported export shape")
    metrics = payload["data"].get("metrics")
    if not isinstance(metrics, list):
        raise TypeError("Unsupported export shape")
    shapes: dict[str, Shape] = {}
    unknown = malformed = 0
    identities: dict[tuple[str, str, str], str] = {}
    for metric in metrics:
        if not isinstance(metric, dict):
            malformed += 1
            continue
        name = metric.get("name")
        if not isinstance(name, str) or name not in UNITS:
            unknown += 1
            continue
        rows = metric.get("data")
        if not isinstance(rows, list):
            malformed += 1
            continue
        shape = shapes.setdefault(name, Shape())
        if metric.get("units") == UNITS[name]:
            shape.expected_unit_blocks += 1
        else:
            shape.unexpected_unit_blocks += 1
        for row in rows:
            if not isinstance(row, dict):
                shape.malformed_samples += 1
                continue
            shape.samples += 1
            for key in FIELDS:
                shape.field_presence[key] += int(key in row)
            shape.interval_patterns[_interval(row)] += 1
            for key in ("id", "uuid", "recordId"):
                value = row.get(key)
                if isinstance(value, str):
                    identity = (name, key, value)
                    digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                    if identity in identities:
                        shape.repeated_identity += 1
                        shape.changed_identity += int(identities[identity] != digest)
                    identities[identity] = digest
    return {
        "diagnostic_version": 1,
        "metrics": {name: asdict(shape) for name, shape in shapes.items()},
        "unknown_metric_blocks": unknown,
        "malformed_metric_blocks": malformed,
        "delivery_semantics": "not_established_from_single_file",
        "correction_identity": "not_verified_by_presence_alone",
        "measurement_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Explicit local export path; do not upload it")
    args = parser.parse_args()
    try:
        if args.file.is_symlink() or not args.file.is_file():
            raise ValueError("Regular export file required")
        with args.file.open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("Export exceeds diagnostic size limit")
        report = diagnose(json.loads(content))
    except (OSError, ValueError, TypeError, RecursionError):
        print(
            "Diagnostic failed: inaccessible, oversized or unsupported export. No payload printed.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
