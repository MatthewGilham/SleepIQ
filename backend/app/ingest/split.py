"""Owner-run, local-only: split one large export into monthly files. Prints counts only."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

MAX_INPUT = 512 * 1024 * 1024
MONTH = re.compile(r"^(\d{4}-\d{2})-\d{2}")


def split(export: Path, destination: Path) -> dict[str, int]:
    """Write export-YYYY-MM.json per source-local start month (plus export-other.json).

    Rows are copied unchanged; metric blocks keep their name/units. Nothing is dropped:
    unmapped blocks and rows without a recognisable start go to export-other.json.
    """
    if export.is_symlink() or not export.is_file() or export.stat().st_size > MAX_INPUT:
        raise ValueError("Regular export file within the size limit required")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Destination must be new or empty; nothing is overwritten")
    payload = json.loads(export.read_bytes())
    metrics = payload["data"]["metrics"]
    if not isinstance(metrics, list):
        raise TypeError("Unsupported export shape")
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for block in metrics:
        if not isinstance(block, dict) or not isinstance(block.get("data"), list):
            raise TypeError("Unsupported export shape")
        for row in block["data"]:
            start = row.get("start", row.get("startDate")) if isinstance(row, dict) else None
            match = MONTH.match(start) if isinstance(start, str) else None
            key = match.group(1) if match else "other"
            target = groups.setdefault(key, {})
            name = str(block.get("name"))
            entry = target.setdefault(
                name, {**{k: v for k, v in block.items() if k != "data"}, "data": []}
            )
            entry["data"].append(row)
    destination.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for key, blocks in sorted(groups.items()):
        out = destination / f"export-{key}.json"
        with out.open("x", encoding="utf-8") as stream:
            json.dump({"data": {"metrics": list(blocks.values())}}, stream)
        counts[key] = sum(len(b["data"]) for b in blocks.values())
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        counts = split(args.file, args.out)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print("Split failed; no export contents were printed and nothing was overwritten.")
        return 1
    for key, rows in counts.items():
        print(f"export-{key}.json: {rows} rows")
    print(f"Files: {len(counts)}. Total rows: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
