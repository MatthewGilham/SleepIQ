"""Build the explicit ingest handler for the LAN receiver; absent configuration means disabled."""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text

from app.db.engine import open_engine
from app.ingest.store import import_bytes

HEAD = "0002_health"


def make_handler(data: Path) -> Callable[[bytes], dict[str, object]]:
    """Fail at startup (never mid-request) if the store is missing or not at the current schema."""
    database = data / "sleepiq.sqlite3"
    if not database.is_file():
        raise ValueError("Initialized private data store required")
    engine = open_engine(database)
    with engine.connect() as conn:
        if conn.execute(text("SELECT version_num FROM alembic_version")).scalar() != HEAD:
            raise ValueError(
                "Store is not at the current schema; run the owner import CLI --migrate"
            )

    def handle(body: bytes) -> dict[str, object]:
        result = import_bytes(engine, data, body)
        return {
            "status": result.status,
            "new": result.new,
            "duplicate": result.duplicate,
            "conflicting": result.conflicting,
            "rejected": sum(result.rejected.values()),
            "unmapped_rows": sum(result.unmapped_metrics.values()),
        }

    return handle
