from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.db.engine import open_engine
from app.db.migrate import upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def test_upgrade_is_repeatable_and_preserves_settings(scratch: Path) -> None:
    engine = open_engine(scratch / "synthetic.db")
    try:
        upgrade(engine)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO app_settings VALUES ('theme', '\"dark\"')"))
        upgrade(engine)
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "app_settings",
            "general_metrics",
            "import_batches",
            "nightly_metrics",
            "nightly_scores",
            "observations",
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT value_json FROM app_settings")) == '"dark"'
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_health"
            )
    finally:
        engine.dispose()


def test_failed_transaction_leaves_no_partial_write(scratch: Path) -> None:
    engine = open_engine(scratch / "synthetic.db")
    try:
        upgrade(engine)
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("INSERT INTO app_settings VALUES ('theme', '1')"))
            connection.execute(text("INSERT INTO app_settings VALUES ('theme', '2')"))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM app_settings")) == 0
    finally:
        engine.dispose()


def test_concurrent_connections_keep_committed_changes(scratch: Path) -> None:
    engine = open_engine(scratch / "synthetic.db")
    try:
        upgrade(engine)

        def write(index: int) -> None:
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO app_settings VALUES (:key, '1')"), {"key": f"test-{index}"}
                )

        with ThreadPoolExecutor(max_workers=3) as workers:
            list(workers.map(write, range(12)))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM app_settings")) == 12
    finally:
        engine.dispose()


def test_missing_directory_is_not_created(scratch: Path) -> None:
    with pytest.raises(ValueError):
        open_engine(scratch / "missing" / "synthetic.db")
    assert not (scratch / "missing").exists()
