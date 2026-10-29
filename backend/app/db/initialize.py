"""Initialize a new empty data store; refuse all existing databases."""

import argparse
import os
from pathlib import Path

from app.db.engine import open_engine
from app.db.migrate import upgrade


def initialize(data: Path) -> None:
    """Caller verifies Windows directory privacy before invoking this function."""
    if not data.is_dir() or data.is_symlink() or data.is_junction():
        raise ValueError("Provisioned private data directory required")
    database = data / "sleepiq.sqlite3"
    if database.exists():
        raise ValueError("Database already exists; no migration or overwrite performed")
    if any(path.name != "raw" for path in data.iterdir()):
        raise ValueError("Initialization requires an empty data directory")
    raw = data / "raw"
    if raw.exists():
        if raw.is_symlink() or raw.is_junction() or not raw.is_dir() or any(raw.iterdir()):
            raise ValueError("Initialization requires an empty regular raw directory")
    else:
        raw.mkdir()
    descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)
    engine = open_engine(database)
    try:
        upgrade(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    arguments = parser.parse_args()
    initialize(arguments.data_root)
    print("New empty database initialized; no existing database was migrated.")
