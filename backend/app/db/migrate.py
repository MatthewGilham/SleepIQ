"""Explicit migrations; never invoked on importing or starting the browser app."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine


def upgrade(engine: Engine) -> None:
    config = Config()
    scripts = Path(__file__).resolve().parent / "migrations"
    config.set_main_option("script_location", str(scripts).replace("%", "%%"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
