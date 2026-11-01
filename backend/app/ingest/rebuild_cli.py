"""Owner-run clean rebuild of derived nights/scores from stored observations (no import)."""

import argparse
import sqlite3
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.db.backup import create_daily
from app.db.coordinator import write_guard
from app.db.engine import open_engine
from app.domain.config import DeriveConfig
from app.domain.rebuild import rebuild, rescore
from app.domain.versions import active_pair, ensure_current


def run(
    data: Path,
    backups: Path,
    today: date,
    derive: DeriveConfig | None = None,
    scores_only: bool = False,
) -> int:
    """Verified snapshot first, then recompute everything; observations are never modified."""
    database = data / "sleepiq.sqlite3"
    engine = open_engine(database)
    try:
        with engine.connect() as conn:
            pair = active_pair(conn)
        if derive is not None and derive.version != pair.derive:
            raise ValueError("Explicit rebuild must match the active pair; use rollout tooling")
        selected = derive or pair.derive_config
        with write_guard(data):
            create_daily(database, data / "raw", backups, today)
        with write_guard(data), engine.begin() as conn:
            ensure_current(conn, pair)
            if scores_only:
                return rescore(conn, selected, pair.score_config)
            rebuild(conn, None, selected, pair.score_config)
            return int(conn.scalar(text("SELECT count(*) FROM nightly_metrics WHERE derivation_version=:v"),
                                   {"v": pair.derive}) or 0)
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
