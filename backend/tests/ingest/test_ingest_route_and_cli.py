import secrets
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.db.engine import open_engine
from app.db.migrate import upgrade
from app.ingest import cli
from app.ingest.service import make_handler
from app.transport.probe import create_probe
from factories import new_store, nights_payload
from fastapi.testclient import TestClient
from sqlalchemy import text

TOKEN = secrets.token_hex(32)
AUTH = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}
FIRST = date(2026, 1, 10)


def client(handler) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(
        create_probe(TOKEN, ingest=handler),
        base_url="https://sync.mgilham.online",
        client=("192.168.1.25", 12345),
    )


def count(data: Path, table: str) -> int:
    engine = open_engine(data / "sleepiq.sqlite3")
    try:
        with engine.connect() as conn:
            return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0)
    finally:
        engine.dispose()


def test_authenticated_upload_imports_and_repeat_is_idempotent(scratch: Path) -> None:
    data, engine = new_store(scratch)
    engine.dispose()
    body = nights_payload(FIRST, 2)
    with client(make_handler(data)) as session:
        assert (
            session.post(
                "/api/ingest", content=body, headers={"Content-Type": "application/json"}
            ).status_code
            == 401
        )
        assert count(data, "observations") == 0  # unauthenticated bodies are never parsed
        first = session.post("/api/ingest", content=body, headers=AUTH)
        again = session.post("/api/ingest", content=body, headers=AUTH)
    assert first.status_code == 200 and first.json()["status"] == "imported"
    assert first.json()["new"] > 0 and first.json()["conflicting"] == 0
    assert again.json()["status"] == "duplicate_batch"
    assert count(data, "nightly_metrics") == 2


def test_ingest_stays_disabled_by_default_and_bad_bodies_are_safe(scratch: Path) -> None:
    data, engine = new_store(scratch)
    engine.dispose()
    with client(None) as session:
        assert (
            session.post("/api/ingest", content=nights_payload(FIRST, 1), headers=AUTH).status_code
            == 503
        )
    with client(make_handler(data)) as session:
        bad = session.post("/api/ingest", content=b'{"data": 1}', headers=AUTH)
        assert bad.status_code == 422 and bad.json() == {"detail": "Unsupported export"}
    assert count(data, "import_batches") == 0


def test_unexpected_failure_returns_generic_error_without_leaking(scratch: Path) -> None:
    def failing(_: bytes) -> dict[str, object]:
        raise RuntimeError("secret-looking detail with payload")

    with client(failing) as session:
        response = session.post("/api/ingest", content=b"{}", headers=AUTH)
    assert response.status_code == 500 and "secret" not in response.text


def test_handler_refuses_a_store_that_is_not_at_the_current_schema(scratch: Path) -> None:
    with pytest.raises(ValueError, match="Initialized"):
        make_handler(scratch)


def old_store(scratch: Path) -> tuple[Path, Path]:
    """A Phase 1 store: schema revision 0001 only, as created by setup-data.ps1."""
    from alembic import command
    from alembic.config import Config

    data = scratch / "data"
    (data / "raw").mkdir(parents=True)
    backups = scratch / "backups"
    backups.mkdir()
    engine = open_engine(data / "sleepiq.sqlite3")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(upgrade.__code__.co_filename).parent / "migrations")
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_settings")
    engine.dispose()
    return data, backups


def test_cli_requires_explicit_migrate_then_backs_up_migrates_and_imports(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data, backups = old_store(scratch)
    export = scratch / "export.json"
    export.write_bytes(nights_payload(FIRST, 3))
    arguments = ["--data-root", str(data), "--backups", str(backups), "--file", str(export)]
    import sys

    sys.argv = ["cli", *arguments]
    assert cli.main() == 1  # phase-1 schema: refuses without --migrate
    assert count(data, "app_settings") == 0 and not list(backups.iterdir())
    sys.argv = ["cli", *arguments, "--migrate"]
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "status: imported" in output and "new_observations:" in output
    assert len(list(backups.iterdir())) == 1  # verified snapshot taken before migration
    assert count(data, "nightly_metrics") == 3
    sys.argv = ["cli", *arguments]  # now at head: no flag needed, idempotent
    assert cli.main() == 0 and "duplicate_batch" in capsys.readouterr().out
    assert "Synthetic" not in output  # counts only: no sources, values or timestamps


def test_year_of_nightly_data_imports_and_rebuilds_in_reasonable_time(scratch: Path) -> None:
    data, engine = new_store(scratch)
    body = nights_payload(date(2025, 1, 1), 365)
    started = time.monotonic()
    from app.ingest.store import import_bytes

    result = import_bytes(engine, data, body)
    elapsed = time.monotonic() - started
    assert result.new > 5000
    assert elapsed < 60, elapsed  # generous guard, not a calibrated budget (Phase 5)
    again = import_bytes(engine, data, nights_payload(date(2025, 12, 20), 12))
    assert again.conflicting == 0 and again.new == 0
    assert (date(2025, 1, 1) + timedelta(days=364)).isoformat() == "2025-12-31"
