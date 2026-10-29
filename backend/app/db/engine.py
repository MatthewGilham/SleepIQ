"""SQLite connections with explicit transaction and integrity behavior."""

import sqlite3
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry


def open_engine(path: Path) -> Engine:
    """Caller must explicitly select an existing data directory; no implicit migration."""
    if not path.parent.is_dir():
        raise ValueError("Database directory must already exist")
    engine = create_engine(
        URL.create("sqlite", database=str(path.resolve())),
        connect_args={"autocommit": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure(connection: sqlite3.Connection, _: ConnectionPoolEntry) -> None:
        # SQLite ignores this pragma inside a transaction.
        connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            if cursor.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise RuntimeError("SQLite foreign-key enforcement unavailable")
        finally:
            cursor.close()
            connection.autocommit = False

    return engine
