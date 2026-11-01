"""Owner-run import of one explicitly chosen export file into a private data store.

Prints counts only; never readings, timestamps, sources or file contents. A verified snapshot is
taken first, and a store that is not at the current schema is migrated only with --migrate.
"""

import argparse
import sqlite3
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.backup import create_daily
from app.db.coordinator import write_guard
from app.db.engine import open_engine
from app.db.migrate import SUPPORTED_HEALTH_REVISIONS, upgrade
from app.ingest.parse import UnsupportedExport
from app.ingest.store import MAX_BYTES, import_bytes


def _revision(database: Path) -> str | None:
    engine = open_engine(database)
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except SQLAlchemyError:
        return None
    finally:
        engine.dispose()


def run(
    data: Path, backups: Path, export: Path, *, migrate: bool, today: date
) -> dict[str, object]:
    database = data / "sleepiq.sqlite3"
    if export.is_symlink() or not export.is_file() or export.stat().st_size > MAX_BYTES:
        raise ValueError("Regular export file within the size limit required")
    if _revision(database) not in SUPPORTED_HEALTH_REVISIONS and not migrate:
        raise ValueError("Store needs the Phase 2 schema; rerun with --migrate after reading docs")
    with write_guard(data):
        create_daily(database, data / "raw", backups, today)
    engine = open_engine(database)
    try:
        if migrate:
            with write_guard(data):
                upgrade(engine)
        result = import_bytes(engine, data, export.read_bytes())
    finally:
        engine.dispose()
    return {
        "status": result.status,
        "new_observations": result.new,
        "exact_duplicates": result.duplicate,
        "flagged_conflicts": result.conflicting,
        "rejected_rows": result.rejected,
        "unmapped_metric_rows": result.unmapped_metrics,
        "rebuilt_from": result.rebuilt_from,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()
    try:
        report = run(
            args.data_root, args.backups, args.file, migrate=args.migrate, today=date.today()
        )
    except (
        OSError,
        ValueError,
        TypeError,
        sqlite3.Error,
        UnsupportedExport,
        TimeoutError,
    ) as error:
        print(f"Import failed ({type(error).__name__}); nothing was partially stored.")
        return 1
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
