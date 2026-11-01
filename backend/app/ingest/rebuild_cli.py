"""Owner-run clean rebuild of derived nights/scores from stored observations (no import)."""

import argparse
import sqlite3
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.db.backup import create_daily
from app.db.coordinator import write_guard
from app.db.engine import open_engine
from app.domain.config import DERIVE, DeriveConfig
from app.domain.rebuild import rebuild, rescore


def run(
    data: Path,
    backups: Path,
    today: date,
    derive: DeriveConfig = DERIVE,
    scores_only: bool = False,
) -> int:
    """Verified snapshot first, then recompute everything; observations are never modified."""
    database = data / "sleepiq.sqlite3"
    with write_guard(data):
        create_daily(database, data / "raw", backups, today)
    engine = open_engine(database)
    try:
        with write_guard(data), engine.begin() as conn:
            if scores_only:
                return rescore(conn, derive)
            rebuild(conn, None, derive)
            return int(conn.execute(text("SELECT count(*) FROM nightly_metrics")).scalar() or 0)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Re-score all nights; preserve metrics and previous score versions",
    )
    args = parser.parse_args()
    try:
        nights = run(args.data_root, args.backups, date.today(), scores_only=args.scores_only)
    except (OSError, ValueError, sqlite3.Error, TimeoutError) as error:
        print(f"Rebuild failed ({type(error).__name__}); stored data was not changed.")
        return 1
    print(f"Rebuilt derived data from stored observations: {nights} nights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
