"""Explicit backup and isolated restore commands; no live restore/overwrite command."""

import argparse
import sqlite3
from datetime import date
from pathlib import Path

from app.db.backup import create_daily, restore_isolated, verify
from app.db.coordinator import write_guard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    daily = commands.add_parser("daily")
    daily.add_argument("--database", type=Path, required=True)
    daily.add_argument("--raw", type=Path, required=True)
    daily.add_argument("--backups", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("snapshot", type=Path)
    restore = commands.add_parser("restore-isolated")
    restore.add_argument("snapshot", type=Path)
    restore.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "daily":
            with write_guard(args.database.parent):
                snapshot = create_daily(args.database, args.raw, args.backups, date.today())
            print(f"Verified daily snapshot: {snapshot.name}")
        elif args.command == "verify":
            verify(args.snapshot)
            print("Snapshot checksums and database integrity verified.")
        else:
            restore_isolated(args.snapshot, args.destination)
            print("Isolated restore verified; existing destinations were not overwritten.")
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        print(f"Operation failed ({type(error).__name__}); inspect selected folders locally.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
