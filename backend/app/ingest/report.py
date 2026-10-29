"""Owner-run, counts-only summary of the private store. Never prints readings or timestamps."""

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from app import certstatus
from app.db.engine import open_engine
from app.ingest.parse import STAGES

# Only these well-known category labels are echoed; anything else is reported as "other".
KNOWN_LABELS = frozenset({"In Bed", "Asleep", "Unspecified", "Sleeping"})


def rejected_stage_labels(raw: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in sorted(raw.glob("*.json")):
        try:
            blocks = json.loads(path.read_bytes())["data"]["metrics"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        for block in blocks:
            if isinstance(block, dict) and block.get("name") == "sleep_analysis":
                for row in block.get("data", []):
                    label = row.get("value") if isinstance(row, dict) else None
                    if label not in STAGES:
                        counts[label if label in KNOWN_LABELS else "other"] += 1
    return counts


def certificate(data: Path) -> dict[str, object] | str:
    """Public expiry only (days, state, last renewal result); never keys or tool output."""
    status = data / "security" / "certificate-status.json"
    return certstatus.read(status) if status.is_file() else "not recorded"


def report(data: Path) -> dict[str, object]:
    engine = open_engine(data / "sleepiq.sqlite3")
    try:
        with engine.connect() as conn:

            def rows(sql: str) -> list[tuple[object, ...]]:
                return [tuple(r) for r in conn.execute(text(sql))]

            return {
                "batches": rows("SELECT count(*) FROM import_batches")[0][0],
                "observations_by_metric_status": {
                    f"{m}/{s}": n
                    for m, s, n in rows(
                        "SELECT metric, status, count(*) FROM observations GROUP BY 1, 2"
                    )
                },
                "nights": rows("SELECT count(*) FROM nightly_metrics")[0][0],
                "night_range": rows("SELECT min(wake_date), max(wake_date) FROM nightly_metrics")[
                    0
                ],
                "scores": {
                    s: n for s, n in rows("SELECT status, count(*) FROM nightly_scores GROUP BY 1")
                },
                "night_flags": dict(
                    Counter(
                        flag
                        for (flags,) in rows("SELECT flags_json FROM nightly_metrics")
                        for flag in json.loads(str(flags))
                    )
                ),
                "nights_missing_hr": rows("SELECT count(*) FROM nightly_metrics WHERE hr_n = 0")[0][
                    0
                ],
                "nights_missing_hrv": rows("SELECT count(*) FROM nightly_metrics WHERE hrv_n = 0")[
                    0
                ][0],
                # Anonymous: no labels are printed, only counts and whether a label mentions a watch.
                "sleep_sources": [
                    {
                        "rows": n,
                        "label_has_apple_watch": "apple watch" in str(label).lower(),
                        "label_has_watch": "watch" in str(label).lower(),
                        "label_empty": not str(label),
                    }
                    for label, n in rows(
                        "SELECT source, count(*) FROM observations "
                        "WHERE metric = 'sleep_analysis' GROUP BY 1 ORDER BY 2 DESC"
                    )
                ],
                "rejected_sleep_labels_in_raw": dict(rejected_stage_labels(data / "raw")),
                "certificate": certificate(data),
            }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        for key, value in report(args.data_root).items():
            print(f"{key}: {value}")
    except Exception as error:  # noqa: BLE001 - generic message; never print store contents
        print(f"Report failed ({type(error).__name__}).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
